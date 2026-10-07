#!/bin/bash
# install-hackpad.sh — installe HackPad + outils pentest sur un ADNRPi
# qui tourne déjà (image bookworm-server sans hackpad).
# À lancer en root via SSH : sudo bash install-hackpad.sh

set -e
REPO="https://raw.githubusercontent.com/adnroboticsfr/adnrpi/develop"
OVERLAY="${REPO}/userpatches/overlay"
APP_DIR="/opt/adnrpi-hackpad"

log() { echo -e "\033[1;36m[hackpad]\033[0m $*"; }
ok()  { echo -e "\033[1;32m  ✓\033[0m $*"; }
err() { echo -e "\033[1;31m  ✗\033[0m $*"; exit 1; }

[[ $EUID -ne 0 ]] && err "Lancer en root : sudo bash install-hackpad.sh"

log "=== Installation HackPad + Pentest ADNRPi ==="

# ── 1. Pentest tools ──────────────────────────────────────────────────────────
log "Outils pentest..."
apt-get update -q
apt-get install -y --no-install-recommends \
    nmap masscan netdiscover arp-scan net-tools iputils-ping traceroute whois dnsutils \
    aircrack-ng iw rfkill \
    nikto sqlmap gobuster dirb curl wget \
    john hydra crunch smbclient \
    dnsrecon \
    tcpdump tshark ngrep netcat-traditional socat \
    xsel python3 python3-pip git vim tmux screen openssh-server ufw
pip3 install hashid --break-system-packages 2>/dev/null || true
mkdir -p /usr/share/wordlists
ln -sf /usr/share/dirb/wordlists/common.txt /usr/share/wordlists/common.txt 2>/dev/null || true
ok "Outils pentest installés"

# ── 2. Kivy + Xorg ───────────────────────────────────────────────────────────
log "Kivy + Xorg..."
apt-get install -y --no-install-recommends \
    python3-kivy \
    libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0 \
    libgles2 libgbm1 libegl-mesa0 libdrm2 libmtdev1 \
    xserver-xorg-core xserver-xorg-video-fbdev \
    xserver-xorg-input-evdev xserver-xorg-input-libinput \
    xinit x11-xserver-utils \
    fonts-noto fonts-noto-color-emoji fonts-dejavu-core \
    xfce4 xfce4-terminal lightdm \
    x11vnc xinput
systemctl disable lightdm 2>/dev/null || true
ok "Kivy + Xorg installés"

# ── 3. Téléchargement des fichiers HackPad depuis le repo ────────────────────
log "Téléchargement des fichiers HackPad..."
mkdir -p "${APP_DIR}/screens" "${APP_DIR}/tools"

for f in main.py launch.sh adnrpi-switch-mode adnrpi-vnc \
          screens/home_screen.py screens/scan_screen.py screens/wifi_screen.py \
          screens/password_screen.py screens/web_screen.py screens/settings_screen.py \
          screens/vnc_screen.py screens/info_screen.py screens/tools_screen.py \
          tools/__init__.py tools/run_tool.py; do
    dir=$(dirname "${APP_DIR}/${f}")
    mkdir -p "${dir}"
    curl -fsSL "${OVERLAY}/hackpad/${f}" -o "${APP_DIR}/${f}" 2>/dev/null || \
        echo "  WARN: ${f} non trouvé (ignoré)"
done

# Fichiers de config overlay
curl -fsSL "${OVERLAY}/99-adnrpi-hackpad.conf" \
    -o /etc/X11/xorg.conf.d/99-adnrpi-hackpad.conf 2>/dev/null && \
    ok "Xorg config 800x480" || echo "  WARN: 99-adnrpi-hackpad.conf manquant"

curl -fsSL "${OVERLAY}/adnrpi-hackpad.service" \
    -o /etc/systemd/system/adnrpi-hackpad.service 2>/dev/null && \
    ok "service hackpad" || err "adnrpi-hackpad.service manquant"

curl -fsSL "${OVERLAY}/adnrpi-hackpad.desktop" \
    -o /usr/share/applications/adnrpi-hackpad.desktop 2>/dev/null || true

curl -fsSL "${OVERLAY}/adnrpi-vnc.service" \
    -o /etc/systemd/system/adnrpi-vnc.service 2>/dev/null || true

curl -fsSL "${OVERLAY}/20-adnrpi-pentest" \
    -o /etc/update-motd.d/20-adnrpi-pentest 2>/dev/null && \
    chmod 755 /etc/update-motd.d/20-adnrpi-pentest || true

curl -fsSL "${OVERLAY}/getty@tty1.service.d/hackpad.conf" \
    -o /etc/systemd/system/getty@tty1.service.d/hackpad.conf 2>/dev/null && \
    ok "getty override" || echo "  WARN: getty override manquant"

chmod +x "${APP_DIR}/main.py" "${APP_DIR}/launch.sh" \
         "${APP_DIR}/adnrpi-switch-mode" "${APP_DIR}/adnrpi-vnc" 2>/dev/null || true
ln -sf "${APP_DIR}/adnrpi-switch-mode" /usr/local/bin/adnrpi-switch-mode
ln -sf "${APP_DIR}/adnrpi-vnc"         /usr/local/bin/adnrpi-vnc

# ── 4. Config Kivy ───────────────────────────────────────────────────────────
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
show_cursor = 1

[input]
mouse = mouse,disable_multitouch

[postproc]
double_tap_time = 250
double_tap_distance = 20

[widgets]
scroll_timeout = 55
scroll_distance = 10
KIVYCONF

# ── 5. Settings HackPad ──────────────────────────────────────────────────────
mkdir -p /etc/adnrpi-hackpad
cat > /etc/adnrpi-hackpad/settings.conf <<'CONF'
target_ip=
interface=eth0
wordlist=/usr/share/wordlists/rockyou.txt
output_dir=/tmp
CONF

# Xorg touch input
mkdir -p /etc/X11/xorg.conf.d
cat > /etc/X11/xorg.conf.d/99-adnrpi-touch.conf <<'TOUCHEOF'
Section "InputClass"
    Identifier "touchscreen"
    MatchIsTouchscreen "on"
    Driver "libinput"
    Option "Tapping" "on"
    Option "CalibrationMatrix" "1 0 0 0 1 0 0 0 1"
EndSection
TOUCHEOF

# ── 6. Boot quiet ────────────────────────────────────────────────────────────
if [ -f /boot/armbianEnv.txt ]; then
    if grep -q "^extraargs=" /boot/armbianEnv.txt; then
        if ! grep -q "quiet" /boot/armbianEnv.txt; then
            sed -i 's/^extraargs=\(.*\)/extraargs=\1 quiet loglevel=1 vt.global_cursor_default=0/' \
                /boot/armbianEnv.txt
        fi
    else
        echo "extraargs=quiet loglevel=1 vt.global_cursor_default=0" >> /boot/armbianEnv.txt
    fi
fi

# ── 7. Activer le service et créer setup.conf ─────────────────────────────────
systemctl daemon-reload
systemctl enable adnrpi-hackpad.service
ok "adnrpi-hackpad.service activé"

mkdir -p /etc/adnrpi
cat > /etc/adnrpi/setup.conf <<'SETUPEOF'
# ADNRPi Setup — applied via install-hackpad.sh
SETUP_VERSION=1
SETUPEOF
chmod 600 /etc/adnrpi/setup.conf
ok "setup.conf créé → HackPad démarrera au prochain boot"

log "=== Installation terminée ==="
echo ""
echo "  Reboot pour démarrer HackPad automatiquement :"
echo "  sudo reboot"
echo ""
echo "  Ou lancer manuellement maintenant :"
echo "  sudo systemctl start adnrpi-hackpad.service"
