# deploy-hackpad.ps1 — Déploie HackPad + outils pentest sur SmartPi via plink/pscp
#
# Usage: .\scripts\deploy-hackpad.ps1 [-IP 192.168.1.89] [-User root] [-Password pi]
# Nécessite PuTTY (plink.exe + pscp.exe) dans PATH ou C:\Program Files\PuTTY\

param(
    [string]$IP       = "192.168.1.89",
    [string]$User     = "root",
    [string]$Password = "pi"
)

$ErrorActionPreference = "Stop"

# Localise plink/pscp
$puttyPaths = @(
    "C:\Program Files\PuTTY",
    "C:\Program Files (x86)\PuTTY",
    "$env:LOCALAPPDATA\Programs\PuTTY"
)
$plink = (Get-Command "plink.exe" -ErrorAction SilentlyContinue)?.Source
$pscp  = (Get-Command "pscp.exe"  -ErrorAction SilentlyContinue)?.Source
foreach ($p in $puttyPaths) {
    if (-not $plink -and (Test-Path "$p\plink.exe")) { $plink = "$p\plink.exe" }
    if (-not $pscp  -and (Test-Path "$p\pscp.exe"))  { $pscp  = "$p\pscp.exe"  }
}
if (-not $plink -or -not $pscp) {
    Write-Error "plink.exe/pscp.exe introuvables. Installe PuTTY: https://www.putty.org"
    exit 1
}

$target     = "${User}@${IP}"
$overlayDir = Join-Path $PSScriptRoot "..\userpatches\overlay"
$overlayDir = (Resolve-Path $overlayDir).Path

Write-Host "==> Déploiement HackPad sur $target" -ForegroundColor Cyan
Write-Host "==> Overlay: $overlayDir"

# ─── 1. Prépare les répertoires distants ─────────────────────────────────────
Write-Host "`n==> Préparation des répertoires distants..."
& $plink -batch -pw $Password $target "mkdir -p /tmp/overlay/hackpad/screens /tmp/overlay/hackpad/tools"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Connexion SSH échouée. Vérifier IP/user/password et accepter la clé hôte d'abord."
    exit 1
}

# ─── 2. Copie des fichiers overlay ───────────────────────────────────────────
Write-Host "`n==> Copie des fichiers overlay..."

# Dossier hackpad complet
& $pscp -batch -pw $Password -r "$overlayDir\hackpad\*" "${target}:/tmp/overlay/hackpad/"

# Fichiers de config
foreach ($f in @("99-adnrpi-hackpad.conf", "adnrpi-hackpad.service", "adnrpi-hackpad.desktop")) {
    $src = Join-Path $overlayDir $f
    if (Test-Path $src) {
        & $pscp -batch -pw $Password $src "${target}:/tmp/overlay/"
    }
}

Write-Host "==> Fichiers copiés OK."

# ─── 3. Script d'installation distant ────────────────────────────────────────
$installScript = @'
#!/bin/bash
set -e
log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Installation outils pentest ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update -q

# Network
apt-get install -y --no-install-recommends \
    nmap masscan netdiscover arp-scan \
    net-tools iputils-ping traceroute whois dnsutils

# WiFi
apt-get install -y --no-install-recommends \
    aircrack-ng iw rfkill

# Web
apt-get install -y --no-install-recommends \
    nikto sqlmap gobuster dirb curl wget

# Passwords
apt-get install -y --no-install-recommends \
    john hydra crunch smbclient

# Recon
apt-get install -y --no-install-recommends \
    dnsrecon

# Capture
apt-get install -y --no-install-recommends \
    tcpdump tshark ngrep netcat-traditional socat

# Utilitaires
apt-get install -y --no-install-recommends \
    python3 python3-pip git vim tmux screen openssh-server ufw xsel

# hashid (pas dans Debian)
pip3 install hashid --break-system-packages 2>/dev/null || true

# Wordlists
mkdir -p /usr/share/wordlists
ln -sf /usr/share/dirb/wordlists/common.txt /usr/share/wordlists/common.txt 2>/dev/null || true
if [ ! -f /usr/share/wordlists/rockyou.txt ]; then
    log "Téléchargement rockyou-75.txt..."
    curl -L --max-time 120 \
        "https://github.com/danielmiessler/SecLists/raw/master/Passwords/Leaked-Databases/rockyou-75.txt" \
        -o /usr/share/wordlists/rockyou.txt || \
        log "AVERTISSEMENT: rockyou.txt echec — ajouter manuellement"
fi

log "=== Installation HackPad (Kivy + Xorg) ==="

# Kivy + SDL2
apt-get install -y --no-install-recommends \
    python3-kivy \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
    libgles2 libgbm1 libegl-mesa0 libdrm2 libmtdev1

# Xorg
apt-get install -y --no-install-recommends \
    xserver-xorg-core xserver-xorg-video-fbdev \
    xserver-xorg-input-evdev xserver-xorg-input-libinput \
    xinit x11-xserver-utils

# Polices + clipboard
apt-get install -y --no-install-recommends \
    fonts-noto fonts-noto-color-emoji fonts-dejavu-core xsel

# XFCE (mode desktop optionnel)
apt-get install -y --no-install-recommends xfce4 xfce4-terminal lightdm
systemctl disable lightdm 2>/dev/null || true

# Config Xorg 800x480
mkdir -p /etc/X11/xorg.conf.d
cp -v /tmp/overlay/99-adnrpi-hackpad.conf /etc/X11/xorg.conf.d/

# App HackPad
APPDIR="/opt/adnrpi-hackpad"
mkdir -p "${APPDIR}"
cp -rv /tmp/overlay/hackpad/* "${APPDIR}/"
chmod +x "${APPDIR}/main.py"
chmod +x "${APPDIR}/launch.sh"
chmod +x "${APPDIR}/adnrpi-switch-mode"
ln -sf "${APPDIR}/adnrpi-switch-mode" /usr/local/bin/adnrpi-switch-mode

# Service systemd
cp -v /tmp/overlay/adnrpi-hackpad.service /etc/systemd/system/
chmod 644 /etc/systemd/system/adnrpi-hackpad.service
systemctl daemon-reload
systemctl enable adnrpi-hackpad.service

# Config par défaut
mkdir -p /etc/adnrpi-hackpad
cat > /etc/adnrpi-hackpad/settings.conf <<'CONF'
target_ip=
interface=eth0
wordlist=/usr/share/wordlists/rockyou.txt
output_dir=/tmp
CONF

# Config Kivy pré-générée
mkdir -p /root/.kivy/logs
cat > /root/.kivy/config.ini <<'KIVYCONF'
[kivy]
log_level = warning
log_enable = 1
log_dir = /root/.kivy/logs
log_name = kivy_%y-%m-%d_%_.txt
log_maxfiles = 5
keyboard_mode =

[graphics]
width = 800
height = 480
fullscreen = 0
borderless = 1
position = custom
left = 0
top = 0
minimum_width = 0
minimum_height = 0
show_cursor = 0

[input]
mouse = mouse,disable_multitouch

[postproc]
double_tap_time = 250
double_tap_distance = 20

[widgets]
scroll_timeout = 55
scroll_distance = 10
KIVYCONF

# Desktop XFCE
mkdir -p /usr/share/applications
cp -v /tmp/overlay/adnrpi-hackpad.desktop /usr/share/applications/ 2>/dev/null || true

# Nettoyage
rm -rf /tmp/overlay

log "=== Installation terminee ==="
log "Redemarrage dans 5 secondes..."
sleep 5
reboot
'@

# Sauvegarde le script en local puis l'envoie
$tmpScript = [System.IO.Path]::GetTempFileName() + ".sh"
# Forcer encodage Unix (LF)
$installScript -replace "`r`n", "`n" | Set-Content -Path $tmpScript -Encoding utf8 -NoNewline

Write-Host "`n==> Envoi du script d'installation..."
& $pscp -batch -pw $Password $tmpScript "${target}:/tmp/install-hackpad.sh"
Remove-Item $tmpScript

Write-Host "`n==> Lancement de l'installation (peut prendre 5-15 min)..."
Write-Host "    Surveiller la progression dans cette fenêtre." -ForegroundColor Yellow
& $plink -batch -pw $Password $target "chmod +x /tmp/install-hackpad.sh && bash /tmp/install-hackpad.sh"

Write-Host "`n==> Déploiement terminé !" -ForegroundColor Green
Write-Host "    Le SmartPi redémarre. HackPad se lancera automatiquement."
