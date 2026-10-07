#!/bin/bash
# ADNRPi — Script de démarrage principal (lancé par xinit/systemd)
#
# Premier démarrage : affiche le launcher pour choisir l'app par défaut.
# Démarrages suivants : lance directement l'app choisie (scope/voice/hackpad).
# Pour rechoisir : supprimer /opt/adnrpi-launcher/startup-app

LAUNCHER_DIR="/opt/adnrpi-launcher"
SCOPE_DIR="/opt/adnrpi-scope"
HACKPAD_DIR="/opt/adnrpi-hackpad"
STARTUP_FILE="${LAUNCHER_DIR}/startup-app"
NEXT_FILE="/tmp/adnrpi-next"

# ── Setup xrandr ──────────────────────────────────────────────────────────────
for i in $(seq 1 10); do
    [ "$(ls /dev/input/event* 2>/dev/null | wc -l)" -gt 0 ] && break
    sleep 1
done

OUTPUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')
IS_SMALL=$(xrandr 2>/dev/null | grep -E "^ +(848x480|800x480)" | head -1)

if [ -n "${IS_SMALL}" ]; then
    if ! xrandr 2>/dev/null | grep -qE "^ +800x480"; then
        xrandr --newmode "800x480" 29.50 800 824 896 988 480 483 493 500 \
               -hsync +vsync 2>/dev/null || true
        xrandr --addmode "$OUTPUT" "800x480" 2>/dev/null || true
    fi
    xrandr --output "$OUTPUT" --mode "800x480" 2>/dev/null || true
    export HACKPAD_W=800
    export HACKPAD_H=480
else
    CURRENT=$(xrandr 2>/dev/null | awk "/^${OUTPUT} connected/{found=1;next} \
        found && /\*/{gsub(/\*.*/, \"\", \$1); print \$1; exit}")
    W=$(echo "$CURRENT" | awk -F'x' '{print $1}')
    H=$(echo "$CURRENT" | awk -F'x' '{print $2}')
    export HACKPAD_W=${W:-800}
    export HACKPAD_H=${H:-480}
fi

# ── Premier démarrage : choisir l'app ────────────────────────────────────────
if [ ! -f "$STARTUP_FILE" ]; then
    echo "Premier demarrage — affichage du choix" >&2
    python3 "${LAUNCHER_DIR}/launcher.py"

    CHOSEN=$(cat "$NEXT_FILE" 2>/dev/null)

    if [ -n "$CHOSEN" ] && [ "$CHOSEN" != "poweroff" ]; then
        echo "$CHOSEN" > "$STARTUP_FILE"
        echo "App par defaut : $CHOSEN" >&2
    else
        [ "$CHOSEN" = "poweroff" ] && poweroff
        exit 0
    fi
fi

# ── Boucle principale : lance l'app choisie, redémarre si crash ───────────────
while true; do
    STARTUP=$(cat "$STARTUP_FILE" 2>/dev/null || echo scope)
    echo "Demarrage : $STARTUP" >&2

    case "$STARTUP" in
        scope)
            rm -rf "${SCOPE_DIR}/__pycache__" 2>/dev/null
            python3 "${SCOPE_DIR}/main.py"
            ;;
        voice)
            DISPLAY=:0 python3 /opt/adnrpi-voice/voice_ui.py > /tmp/voice_ui.log 2>&1
            ;;
        hackpad)
            python3 "${HACKPAD_DIR}/main.py"
            ;;
        *)
            sleep 3
            continue
            ;;
    esac

    # L'app vient de quitter — vérifier si changement d'app demandé
    NEXT=$(cat "$NEXT_FILE" 2>/dev/null)
    case "$NEXT" in
        poweroff)
            poweroff
            break
            ;;
        change_app)
            rm -f "$STARTUP_FILE"
            python3 "${LAUNCHER_DIR}/launcher.py"
            CHOSEN=$(cat "$NEXT_FILE" 2>/dev/null)
            if [ -n "$CHOSEN" ] && [ "$CHOSEN" != "poweroff" ] && [ "$CHOSEN" != "change_app" ]; then
                echo "$CHOSEN" > "$STARTUP_FILE"
            fi
            ;;
        *)
            # Crash ou quit normal → redémarrer après 1s
            sleep 1
            ;;
    esac
done
