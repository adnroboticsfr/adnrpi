#!/bin/bash
# Wrapper de lancement HackPad.
#
# Détecte l'écran connecté :
#   - Écran 5 pouces 800x480 (pentest nomade) → force 800x480, Kivy plein écran
#   - Moniteur externe (développement/bureau)  → garde la résolution native,
#     Kivy s'adapte à la taille réelle de l'écran
#
# Aucun xrandr n'est appelé si la résolution est déjà correcte → pas de flash.

SMALL_W=800
SMALL_H=480

# Premier output connecté
OUTPUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')

if [ -z "$OUTPUT" ]; then
    echo "[launch] aucun output détecté, démarrage sans xrandr"
    exec python3 /opt/adnrpi-hackpad/main.py
fi

# Mode préféré de cet output (marqué '+' dans la liste)
PREFERRED=$(xrandr 2>/dev/null | awk "
    /^${OUTPUT} connected/{found=1; next}
    found && /\+/{print \$1; exit}
")

# Résolution actuellement active (marquée '*')
CURRENT=$(xrandr 2>/dev/null | awk "
    /^${OUTPUT} connected/{found=1; next}
    found && /\*/{gsub(/\*.*/, \"\", \$1); print \$1; exit}
")

echo "[launch] output=${OUTPUT}  preferred=${PREFERRED}  current=${CURRENT}"

if [ "$PREFERRED" = "${SMALL_W}x${SMALL_H}" ]; then
    # ── Écran 5 pouces 800x480 ──────────────────────────────────────────────
    # N'appelle xrandr QUE si la résolution actuelle est différente
    if [ "$CURRENT" != "${SMALL_W}x${SMALL_H}" ]; then
        echo "[launch] forçage ${SMALL_W}x${SMALL_H} sur ${OUTPUT}"
        xrandr --output "$OUTPUT" --mode "${SMALL_W}x${SMALL_H}" 2>/dev/null || true
    fi
    export HACKPAD_W=${SMALL_W}
    export HACKPAD_H=${SMALL_H}
else
    # ── Moniteur externe (préféré ≠ 800x480) ───────────────────────────────
    # Laisser la résolution native — on lit la taille réelle pour Kivy
    NATIVE=$(echo "$PREFERRED" | tr 'x' ' ')
    W=$(echo "$NATIVE" | awk '{print $1}')
    H=$(echo "$NATIVE" | awk '{print $2}')
    echo "[launch] moniteur externe détecté (${PREFERRED}), Kivy s'adapte"
    export HACKPAD_W=${W:-800}
    export HACKPAD_H=${H:-480}
fi

exec python3 /opt/adnrpi-hackpad/main.py
