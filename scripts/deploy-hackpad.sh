#!/bin/bash
# deploy-hackpad.sh — Déploie HackPad + outils pentest sur SmartPi via SSH/SCP
#
# Usage: bash scripts/deploy-hackpad.sh [IP] [USER] [PASSWORD]
# Défauts: 192.168.1.89 / root / pi

set -e

DEVICE_IP="${1:-192.168.1.89}"
DEVICE_USER="${2:-root}"
DEVICE_PASS="${3:-pi}"
OVERLAY_DIR="$(dirname "$0")/../userpatches/overlay"

# Vérification que plink/pscp sont accessibles (PuTTY) ou ssh/scp natifs
if command -v sshpass &>/dev/null; then
    SSH="sshpass -p ${DEVICE_PASS} ssh -o StrictHostKeyChecking=no"
    SCP="sshpass -p ${DEVICE_PASS} scp -o StrictHostKeyChecking=no"
elif command -v plink.exe &>/dev/null; then
    SSH="plink.exe -batch -pw ${DEVICE_PASS}"
    SCP="pscp.exe -batch -pw ${DEVICE_PASS}"
else
    echo "ERREUR: installe sshpass (Linux) ou ajoute plink.exe/pscp.exe au PATH"
    exit 1
fi

TARGET="${DEVICE_USER}@${DEVICE_IP}"
echo "==> Déploiement HackPad sur ${TARGET}"

# ─── 1. Préparation des répertoires sur le device ────────────────────────────
$SSH $TARGET "mkdir -p /tmp/overlay/hackpad"

# ─── 2. Envoi des fichiers overlay ───────────────────────────────────────────
echo "==> Copie des fichiers overlay..."
$SCP -r "${OVERLAY_DIR}/hackpad/" "${TARGET}:/tmp/overlay/"
$SCP "${OVERLAY_DIR}/99-adnrpi-hackpad.conf" "${TARGET}:/tmp/overlay/"
$SCP "${OVERLAY_DIR}/adnrpi-hackpad.service" "${TARGET}:/tmp/overlay/"
$SCP "${OVERLAY_DIR}/adnrpi-hackpad.desktop" "${TARGET}:/tmp/overlay/"

echo "==> Fichiers copiés."

# ─── 3. Script d'installation exécuté sur le device ─────────────────────────
$SSH $TARGET bash <<'REMOTE'
set -e
log() { echo "[$(date '+%H:%M:%S')] $*"; }

log "=== Installation outils pentest ==="
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

# hashid (pip seulement, pas dans Debian)
pip3 install hashid --break-system-packages 2>/dev/null || true

# Wordlists
mkdir -p /usr/share/wordlists
ln -sf /usr/share/dirb/wordlists/common.txt /usr/share/wordlists/common.txt 2>/dev/null || true
if [ ! -f /usr/share/wordlists/rockyou.txt ]; then
    log "Téléchargement rockyou-75.txt..."
    curl -L --max-time 120 \
        "https://github.com/danielmiessler/SecLists/raw/master/Passwords/Leaked-Databases/rockyou-75.txt" \
        -o /usr/share/wordlists/rockyou.txt || \
        log "AVERTISSEMENT: rockyou.txt non téléchargé — ajouter manuellement"
fi

log "=== Installation HackPad (Kivy + Xorg) ==="

# Kivy + SDL2
apt-get install -y --no-install-recommends \
    python3-kivy \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
    libgles2 libgbm1 libegl-mesa0 libdrm2 libmtdev1

# Xorg (backend SDL2 via modesetting + Lima — kmsdrm absent sur Bookworm ARM)
apt-get install -y --no-install-recommends \
    xserver-xorg-core xserver-xorg-video-fbdev \
    xserver-xorg-input-evdev xserver-xorg-input-libinput \
    xinit x11-xserver-utils

# Polices
apt-get install -y --no-install-recommends \
    fonts-noto fonts-noto-color-emoji fonts-dejavu-core

# XFCE (mode desktop optionnel)
apt-get install -y --no-install-recommends \
    xfce4 xfce4-terminal lightdm
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

log "=== Installation terminée ==="
log "Redémarrage dans 5 secondes pour lancer HackPad..."
sleep 5
reboot
REMOTE

echo ""
echo "==> Déploiement terminé. Le SmartPi redémarre."
echo "==> HackPad se lancera automatiquement au démarrage."
