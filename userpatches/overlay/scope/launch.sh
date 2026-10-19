#!/bin/bash
# Lance l'oscilloscope via Xorg sur vt1.
# Utilisé directement pour le test (pas via systemd).

SCOPE_DIR="/opt/adnrpi-scope"

# Attendre les périphériques d'entrée
for i in $(seq 1 10); do
    [ "$(ls /dev/input/event* 2>/dev/null | wc -l)" -gt 0 ] && break
    sleep 1
done

# Détection écran (même logique que HackPad)
SMALL_W=800; SMALL_H=480
OUTPUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')
CURRENT=$(xrandr 2>/dev/null | awk "/^${OUTPUT} connected/{found=1;next} found && /\*/{gsub(/\*.*/, \"\", \$1); print \$1; exit}")
IS_SMALL=$(xrandr 2>/dev/null | grep -E "^ +(848x480|800x480)" | head -1)

if [ -n "${IS_SMALL}" ]; then
    if ! xrandr 2>/dev/null | grep -qE "^ +800x480"; then
        xrandr --newmode "800x480" 29.50 800 824 896 988 480 483 493 500 -hsync +vsync 2>/dev/null || true
        xrandr --addmode "$OUTPUT" "800x480" 2>/dev/null || true
    fi
    xrandr --output "$OUTPUT" --mode "800x480" 2>/dev/null || true
    export HACKPAD_W=800; export HACKPAD_H=480
else
    W=$(echo "$CURRENT" | awk -F'x' '{print $1}')
    H=$(echo "$CURRENT" | awk -F'x' '{print $2}')
    export HACKPAD_W=${W:-800}; export HACKPAD_H=${H:-480}
fi

exec python3 "${SCOPE_DIR}/main.py"
