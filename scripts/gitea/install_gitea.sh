#!/bin/bash
# =============================================================================
# ADNRPi — Installation Gitea sur SmartPi One H3 (Armbian Bookworm)
#
# Usage :
#   sudo bash install_gitea.sh
#
# Ce script :
#   1. Télécharge le binaire Gitea ARM7 (H3 = Cortex-A7 = ARMv7)
#   2. Crée l'utilisateur git et les répertoires
#   3. Installe le script de sélection SD/USB
#   4. Crée les services systemd (stockage + gitea)
#   5. Configure Gitea (app.ini)
#   6. Active et démarre tout
#
# Après installation :
#   Interface web → http://192.168.1.89:3000
#   SSH git       → git@192.168.1.89:user/repo.git
# =============================================================================

set -e

# ── Configuration ─────────────────────────────────────────────────────────────
# Gitea a abandonné arm-7 à partir de v28 — arm-6 fonctionne sur H3 (ARMv7 compatible)
GITEA_VERSION="28.0.0"
GITEA_BIN_URL="https://github.com/go-gitea/gitea/releases/download/v${GITEA_VERSION}/gitea-${GITEA_VERSION}-linux-arm-6"
GITEA_BIN="/usr/local/bin/gitea"
GITEA_HOME="/opt/gitea"
GITEA_USER="git"
GITEA_PORT="3000"
GITEA_SSH_PORT="2222"       # Port SSH Gitea (distinct de SSH système sur 22)
GITEA_DOMAIN="$(hostname -I | awk '{print $1}')"   # IP locale auto

# ── Couleurs terminal ─────────────────────────────────────────────────────────
GRN='\033[0;32m' CYN='\033[0;36m' YEL='\033[1;33m' RED='\033[0;31m' NC='\033[0m'
info()  { echo -e "${CYN}[INFO]${NC} $*"; }
ok()    { echo -e "${GRN}[ OK ]${NC} $*"; }
warn()  { echo -e "${YEL}[WARN]${NC} $*"; }
die()   { echo -e "${RED}[ERR ]${NC} $*"; exit 1; }

[ "$(id -u)" = "0" ] || die "Lancer en root : sudo bash install_gitea.sh"

# ── 1. Dépendances ────────────────────────────────────────────────────────────
info "Mise à jour des paquets..."
apt-get update -qq
apt-get install -y --no-install-recommends git curl wget sqlite3 >/dev/null
ok "Dépendances OK"

# ── 2. Utilisateur git ────────────────────────────────────────────────────────
if ! id "$GITEA_USER" &>/dev/null; then
    adduser --system --shell /bin/bash \
            --gecos "Gitea Git Hosting" \
            --group --disabled-password \
            --home "$GITEA_HOME" "$GITEA_USER"
    ok "Utilisateur '$GITEA_USER' créé"
else
    ok "Utilisateur '$GITEA_USER' existant"
fi

# ── 3. Répertoires ────────────────────────────────────────────────────────────
for d in "$GITEA_HOME" \
          "$GITEA_HOME/data-sd" \
          "$GITEA_HOME/custom" \
          "$GITEA_HOME/log" \
          "$GITEA_HOME/tmp" \
          "/mnt/gitea-usb"; do
    mkdir -p "$d"
done
chown -R "$GITEA_USER:$GITEA_USER" "$GITEA_HOME"
chmod 750 "$GITEA_HOME"
ok "Répertoires créés"

# ── 4. Binaire Gitea (ARM7) ───────────────────────────────────────────────────
if [ ! -f "$GITEA_BIN" ] || [ "$1" = "--upgrade" ]; then
    info "Téléchargement Gitea v${GITEA_VERSION} (ARM7)..."
    wget -q --show-progress -O "$GITEA_BIN" "$GITEA_BIN_URL"
    chmod +x "$GITEA_BIN"
    ok "Gitea binaire installé : $(gitea --version 2>/dev/null | head -1)"
else
    ok "Gitea déjà installé : $($GITEA_BIN --version 2>/dev/null | head -1)"
fi

# ── 5. Script sélection stockage ──────────────────────────────────────────────
cp "$(dirname "$0")/select-storage.sh" /opt/gitea/select-storage.sh
chmod +x /opt/gitea/select-storage.sh
ok "Script sélection stockage installé"

# Exécuter une première fois pour créer le symlink
/opt/gitea/select-storage.sh
STORAGE_PATH="$(readlink /opt/gitea/storage)"
info "Stockage actif : $STORAGE_PATH"

# ── 6. Configuration Gitea (app.ini) ─────────────────────────────────────────
CONF_DIR="$GITEA_HOME/custom/conf"
mkdir -p "$CONF_DIR"

cat > "$CONF_DIR/app.ini" << EOF
APP_NAME = ADNRPi Gitea
RUN_USER = $GITEA_USER
RUN_MODE = prod
WORK_PATH = $GITEA_HOME

[repository]
ROOT = /opt/gitea/storage/repos

[server]
DOMAIN           = $GITEA_DOMAIN
HTTP_PORT        = $GITEA_PORT
ROOT_URL         = http://$GITEA_DOMAIN:$GITEA_PORT/
SSH_DOMAIN       = $GITEA_DOMAIN
START_SSH_SERVER = true
SSH_PORT         = $GITEA_SSH_PORT
APP_DATA_PATH    = /opt/gitea/storage/data
LFS_START_SERVER = false

[database]
DB_TYPE  = sqlite3
PATH     = /opt/gitea/storage/gitea.db

[log]
ROOT_PATH = $GITEA_HOME/log
LEVEL     = warn
MODE      = file

[security]
INSTALL_LOCK        = false
SECRET_KEY          = $(head -c 32 /dev/urandom | base64 | tr -d '=+/' | head -c 32)
INTERNAL_TOKEN      = $(head -c 64 /dev/urandom | base64 | tr -d '=+/' | head -c 64)

[service]
DISABLE_REGISTRATION       = false
REQUIRE_SIGNIN_VIEW        = false
DEFAULT_KEEP_EMAIL_PRIVATE = true
ENABLE_NOTIFY_MAIL         = false

[mailer]
ENABLED = false

[cache]
ADAPTER = memory
INTERVAL = 60

[session]
PROVIDER        = file
PROVIDER_CONFIG = /opt/gitea/storage/sessions

[picture]
DISABLE_GRAVATAR = true

[other]
SHOW_FOOTER_VERSION = false
EOF

chown -R "$GITEA_USER:$GITEA_USER" "$GITEA_HOME/custom"
ok "Configuration app.ini générée"

# ── 7. Services systemd ───────────────────────────────────────────────────────

# Service 1 : sélection du stockage (s'exécute avant Gitea)
cat > /etc/systemd/system/gitea-storage.service << EOF
[Unit]
Description=Gitea — Sélection stockage SD/USB
Before=gitea.service
DefaultDependencies=no

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/opt/gitea/select-storage.sh
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Service 2 : Gitea
cat > /etc/systemd/system/gitea.service << EOF
[Unit]
Description=Gitea — Self-hosted Git (ADNRPi)
After=network.target gitea-storage.service
Requires=gitea-storage.service

[Service]
Type=simple
User=$GITEA_USER
Group=$GITEA_USER
WorkingDirectory=$GITEA_HOME
ExecStart=$GITEA_BIN web --config $CONF_DIR/app.ini
Restart=always
RestartSec=5
Environment=USER=$GITEA_USER HOME=$GITEA_HOME GITEA_WORK_DIR=$GITEA_HOME
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable gitea-storage.service gitea.service
ok "Services systemd installés et activés"

# ── 8. Démarrage ─────────────────────────────────────────────────────────────
info "Démarrage Gitea..."
systemctl start gitea-storage.service
sleep 1
systemctl start gitea.service
sleep 3

if systemctl is-active --quiet gitea.service; then
    ok "Gitea démarré !"
    echo ""
    echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GRN}  Gitea installé sur SmartPi H3${NC}"
    echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "  Interface web : ${CYN}http://$GITEA_DOMAIN:$GITEA_PORT${NC}"
    echo -e "  SSH git       : ${CYN}git@$GITEA_DOMAIN -p $GITEA_SSH_PORT${NC}"
    echo -e "  Stockage      : ${YEL}$STORAGE_PATH${NC}"
    echo -e "  Log stockage  : /opt/gitea/storage-select.log"
    echo ""
    echo -e "  ${YEL}Première visite → créer le compte admin dans le navigateur${NC}"
    echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
else
    warn "Gitea pas encore actif — vérifier : journalctl -u gitea -n 30"
fi
