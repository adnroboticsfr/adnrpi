#!/bin/bash
# =============================================================================
# ADNRPi — Installation serveur web complet
#
# Installe :
#   - Cockpit  (admin système, port 9090)
#   - nginx    (hub d'accueil port 80, reverse proxy vers tous les services)
#   - filebrowser (gestionnaire de fichiers web, port 8081)
#   - stats_api.py (mini API JSON pour hub.html, port 8079)
#
# Accès final depuis le réseau local :
#   http://192.168.1.89/          → Hub ADNRPi (page d'accueil)
#   http://192.168.1.89/admin/    → Cockpit
#   http://192.168.1.89/git/      → Gitea
#   http://192.168.1.89/files/    → Gestionnaire fichiers
#   http://192.168.1.89/api/stats → Stats JSON (pour hub)
# =============================================================================

set -e

GRN='\033[0;32m' CYN='\033[0;36m' YEL='\033[1;33m' RED='\033[0;31m' NC='\033[0m'
info() { echo -e "${CYN}[INFO]${NC} $*"; }
ok()   { echo -e "${GRN}[ OK ]${NC} $*"; }
die()  { echo -e "${RED}[ERR ]${NC} $*"; exit 1; }

[ "$(id -u)" = "0" ] || die "Lancer en root : sudo bash install_server.sh"

IP=$(hostname -I | awk '{print $1}')
SCRIPT_DIR="$(dirname "$(realpath "$0")")"

# ── 1. Cockpit ────────────────────────────────────────────────────────────────
info "Installation Cockpit..."
apt-get update -qq
apt-get install -y --no-install-recommends cockpit cockpit-storaged >/dev/null
systemctl enable --now cockpit.socket
ok "Cockpit installé → https://$IP:9090"

# ── 2. nginx ──────────────────────────────────────────────────────────────────
info "Installation nginx..."
apt-get install -y --no-install-recommends nginx >/dev/null

# Page d'accueil hub
mkdir -p /var/www/adnrpi
cp "$SCRIPT_DIR/hub.html" /var/www/adnrpi/index.html

# Config nginx
cat > /etc/nginx/sites-available/adnrpi << 'NGINX'
server {
    listen 80 default_server;
    server_name _;
    charset utf-8;

    # ── Hub (page d'accueil) ──────────────────────────────────────────────────
    location = / {
        root /var/www/adnrpi;
        try_files /index.html =404;
    }

    # ── API stats (mini Python) ───────────────────────────────────────────────
    location /api/stats {
        proxy_pass http://127.0.0.1:8079;
        proxy_set_header Host $host;
        add_header Cache-Control "no-store";
    }

    # ── Cockpit ───────────────────────────────────────────────────────────────
    location /admin/ {
        proxy_pass https://127.0.0.1:9090/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_ssl_verify off;
    }

    # ── Gitea ─────────────────────────────────────────────────────────────────
    location /git/ {
        proxy_pass http://127.0.0.1:3000/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;
    }

    # ── Gestionnaire fichiers ─────────────────────────────────────────────────
    location /files/ {
        proxy_pass http://127.0.0.1:8081/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # ── Scope logs (optionnel) ────────────────────────────────────────────────
    location /scope/ {
        alias /tmp/;
        autoindex off;
        # servira scope.log si on crée un endpoint dédié plus tard
        return 200 '<pre id="log"></pre><script>setInterval(()=>fetch("/api/scope-log").then(r=>r.text()).then(t=>{document.getElementById("log").textContent=t}),2000)</script>';
        add_header Content-Type text/html;
    }
}
NGINX

rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/adnrpi /etc/nginx/sites-enabled/adnrpi
nginx -t && systemctl enable --now nginx && systemctl reload nginx
ok "nginx configuré → http://$IP/"

# ── 3. File Browser ───────────────────────────────────────────────────────────
info "Installation File Browser..."
FB_BIN="/usr/local/bin/filebrowser"
if [ ! -f "$FB_BIN" ]; then
    # Binary ARM pour H3
    FB_URL="https://github.com/filebrowser/filebrowser/releases/latest/download/linux-armv7-filebrowser.tar.gz"
    wget -q --show-progress -O /tmp/fb.tar.gz "$FB_URL"
    tar -xzf /tmp/fb.tar.gz -C /tmp/
    mv /tmp/filebrowser "$FB_BIN"
    chmod +x "$FB_BIN"
    rm -f /tmp/fb.tar.gz
fi

# Config filebrowser
mkdir -p /opt/filebrowser
cat > /opt/filebrowser/config.json << 'EOF'
{
  "port": 8081,
  "baseURL": "/files",
  "address": "127.0.0.1",
  "root": "/",
  "database": "/opt/filebrowser/db.db",
  "log": "stdout",
  "noauth": false
}
EOF

# Service systemd
cat > /etc/systemd/system/filebrowser.service << 'EOF'
[Unit]
Description=ADNRPi File Browser
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/filebrowser --config /opt/filebrowser/config.json
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now filebrowser.service
ok "File Browser installé → http://$IP/files/"

# ── 4. Stats API ──────────────────────────────────────────────────────────────
info "Installation Stats API..."
cp "$SCRIPT_DIR/stats_api.py" /opt/adnrpi-stats-api.py
chmod +x /opt/adnrpi-stats-api.py

cat > /etc/systemd/system/adnrpi-stats.service << 'EOF'
[Unit]
Description=ADNRPi Stats API
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 /opt/adnrpi-stats-api.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now adnrpi-stats.service
ok "Stats API démarrée → http://127.0.0.1:8079"

# ── 5. Mise à jour Gitea pour le sous-chemin /git/ ───────────────────────────
GITEA_INI="/opt/gitea/custom/conf/app.ini"
if [ -f "$GITEA_INI" ]; then
    info "Mise à jour Gitea ROOT_URL pour /git/..."
    sed -i "s|ROOT_URL.*|ROOT_URL = http://$IP/git/|" "$GITEA_INI"
    systemctl restart gitea 2>/dev/null || true
    ok "Gitea ROOT_URL mis à jour"
fi

# ── Résumé ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GRN}  ADNRPi Serveur Web — Installation terminée${NC}"
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Hub accueil    : ${CYN}http://$IP/${NC}"
echo -e "  Administration : ${CYN}http://$IP/admin/${NC}  (user: root)"
echo -e "  Gitea          : ${CYN}http://$IP/git/${NC}"
echo -e "  Fichiers       : ${CYN}http://$IP/files/${NC}  (user: admin / pass: admin)"
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${YEL}Changer le mot de passe File Browser après première connexion${NC}"
echo ""
