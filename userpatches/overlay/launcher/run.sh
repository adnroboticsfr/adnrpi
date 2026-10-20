#!/bin/bash
# ADNRPi Launcher — affiche le menu à chaque démarrage, lance l'app choisie.
# Après que l'app choisie se termine (ou crash), le launcher réapparaît.

LAUNCHER_DIR="/opt/adnrpi-launcher"
SCOPE_DIR="/opt/adnrpi-scope"
HACKPAD_DIR="/opt/adnrpi-hackpad"
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

# ── Boucle principale : launcher → app → launcher ────────────────────────────
while true; do
    rm -f "$NEXT_FILE"
    python3 "${LAUNCHER_DIR}/launcher.py"

    CHOSEN=$(cat "$NEXT_FILE" 2>/dev/null)

    case "$CHOSEN" in
        poweroff)
            poweroff
            break
            ;;
        scope)
            rm -rf "${SCOPE_DIR}/__pycache__" 2>/dev/null
            python3 "${SCOPE_DIR}/main.py"
            ;;
        hackpad)
            python3 "${HACKPAD_DIR}/main.py"
            ;;
        *)
            sleep 1
            ;;
    esac
    # L'app vient de quitter → retour au launcher automatiquement
done
