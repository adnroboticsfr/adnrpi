# deploy-scope.ps1 — Déploie l'oscilloscope sur SmartPi One (192.168.1.89)
# Usage : .\scripts\deploy-scope.ps1

$HOST = "192.168.1.89"
$USER = "root"
$PASS = "pi"
$SCOPE_DIR = "/opt/adnrpi-scope"
$SRC = "$PSScriptRoot\scope"

Write-Host "=== Deploy ADNRPi Scope ===" -ForegroundColor Cyan

# Fonctions SSH/SCP via plink/pscp (PuTTY) ou ssh/scp natif
function SSH($cmd) {
    & ssh -o StrictHostKeyChecking=no "${USER}@${HOST}" $cmd
}
function SCP($src, $dst) {
    & scp -o StrictHostKeyChecking=no $src "${USER}@${HOST}:${dst}"
}

# 1. Arrêter HackPad si actif
Write-Host "`n[1] Arrêt HackPad..." -ForegroundColor Yellow
SSH "systemctl stop adnrpi-hackpad.service 2>/dev/null; killall xinit 2>/dev/null; true"
Start-Sleep -Seconds 2

# 2. Créer le répertoire scope
Write-Host "[2] Création /opt/adnrpi-scope..." -ForegroundColor Yellow
SSH "mkdir -p $SCOPE_DIR"

# 3. Copier les fichiers
Write-Host "[3] Copie des fichiers..." -ForegroundColor Yellow
foreach ($f in @("main.py", "scope_screen.py", "audio_capture.py", "launch.sh")) {
    $src_path = Join-Path $SRC $f
    if (Test-Path $src_path) {
        SCP $src_path "$SCOPE_DIR/$f"
        Write-Host "  -> $f" -ForegroundColor Gray
    } else {
        Write-Host "  MANQUANT: $f" -ForegroundColor Red
    }
}
SSH "chmod +x $SCOPE_DIR/launch.sh $SCOPE_DIR/main.py"

# 4. Installer les dépendances Python
Write-Host "`n[4] Installation dépendances Python..." -ForegroundColor Yellow
SSH "pip3 install --quiet sounddevice numpy 2>&1 | tail -3"
SSH "apt-get install -y --quiet libportaudio2 python3-numpy 2>&1 | tail -3"

# 5. Vérifier les devices audio
Write-Host "`n[5] Devices audio disponibles :" -ForegroundColor Yellow
SSH "python3 -c 'import sounddevice as sd; [print(d) for d in sd.query_devices()]' 2>/dev/null || arecord -l 2>/dev/null || echo 'sounddevice non disponible'"

# 6. Lancer l'oscilloscope via xinit
Write-Host "`n[6] Lancement oscilloscope sur l'écran..." -ForegroundColor Yellow
SSH "rm -f /tmp/.X0-lock /tmp/.X11-unix/X0; nohup xinit $SCOPE_DIR/launch.sh -- :0 vt1 -nolisten tcp > /tmp/scope.log 2>&1 &"
Start-Sleep -Seconds 3
Write-Host "  Log: ssh root@$HOST 'tail -f /tmp/scope.log'"

Write-Host "`n=== Deploy terminé ===" -ForegroundColor Green
Write-Host "Pour voir les logs : ssh root@$HOST 'tail -20 /tmp/scope.log'" -ForegroundColor Cyan
Write-Host "Pour arrêter      : ssh root@$HOST 'killall xinit'" -ForegroundColor Cyan
Write-Host "Pour redémarrer HackPad : ssh root@$HOST 'systemctl start adnrpi-hackpad.service'" -ForegroundColor Cyan
