#!/bin/bash
# Wrapper de lancement HackPad.
#
# Détecte l'écran connecté :
#   - Écran 5 pouces (EDID contient 848x480) → injecte modeline 800x480, Kivy 800x480
#   - Moniteur externe                        → résolution native active, Kivy s'adapte
#
# Détection basée sur les modes EDID disponibles, pas sur le marqueur '+' qui
# est absent de certains écrans bon marché (ex: 848x480 présent mais pas 800x480).

SMALL_W=800
SMALL_H=480

# Premier output connecté
OUTPUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')

if [ -z "$OUTPUT" ]; then
    echo "[launch] aucun output détecté, démarrage sans xrandr"
    export HACKPAD_W=${SMALL_W}
    export HACKPAD_H=${SMALL_H}
    exec python3 /opt/adnrpi-hackpad/main.py
fi

# Résolution actuellement active (marquée '*')
CURRENT=$(xrandr 2>/dev/null | awk "
    /^${OUTPUT} connected/{found=1; next}
    found && /\*/{gsub(/\*.*/, \"\", \$1); print \$1; exit}
")

# Détection mini écran : 848x480 OU 800x480 dans les modes EDID disponibles
# (mawk Debian ne supporte pas \s — utilisation de grep)
IS_SMALL=$(xrandr 2>/dev/null | grep -E "^ +(848x480|800x480)" | head -1)

echo "[launch] output=${OUTPUT}  current=${CURRENT}  small=${IS_SMALL:-no}"

if [ -n "${IS_SMALL}" ]; then
    # ── Écran 5 pouces 800x480 ──────────────────────────────────────────────
    # Injecte un modeline 800x480 si absent, puis force la résolution
    if ! xrandr 2>/dev/null | grep -q "^\s*800x480"; then
        echo "[launch] ajout modeline 800x480"
        xrandr --newmode "800x480" 29.50 800 824 896 988 480 483 493 500 -hsync +vsync 2>/dev/null || true
        xrandr --addmode "$OUTPUT" "800x480" 2>/dev/null || true
    fi
    if [ "$CURRENT" != "${SMALL_W}x${SMALL_H}" ]; then
        echo "[launch] forçage ${SMALL_W}x${SMALL_H} sur ${OUTPUT}"
        xrandr --output "$OUTPUT" --mode "${SMALL_W}x${SMALL_H}" 2>/dev/null || true
    fi
    export HACKPAD_W=${SMALL_W}
    export HACKPAD_H=${SMALL_H}
else
    # ── Moniteur externe ─────────────────────────────────────────────────────
    # Utilise la résolution active — fenêtre Kivy plein écran
    W=$(echo "$CURRENT" | awk -F'x' '{print $1}')
    H=$(echo "$CURRENT" | awk -F'x' '{print $2}')
    echo "[launch] moniteur externe (${CURRENT}), Kivy ${W:-800}x${H:-480}"
    export HACKPAD_W=${W:-800}
    export HACKPAD_H=${H:-480}
fi

exec python3 /opt/adnrpi-hackpad/main.py
