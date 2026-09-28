#!/bin/bash
# Wrapper de lancement HackPad — force la résolution 800x480 avant Kivy.
# Nécessaire car Xorg/modesetting peut choisir 1280x720 si EDID non disponible.
set -e

TARGET_W=800
TARGET_H=480

# Trouver le premier output connecté
OUTPUT=$(xrandr 2>/dev/null | awk '/ connected/{print $1; exit}')

if [ -n "$OUTPUT" ]; then
    CURRENT=$(xrandr 2>/dev/null | awk "/^${OUTPUT} connected/{found=1} found && /\*/{print \$1; exit}")
    if [ "$CURRENT" != "${TARGET_W}x${TARGET_H}" ]; then
        echo "[launch] forcing ${TARGET_W}x${TARGET_H} on ${OUTPUT} (was ${CURRENT:-unknown})"
        xrandr --output "$OUTPUT" --mode "${TARGET_W}x${TARGET_H}" 2>/dev/null || true
    fi
fi

exec python3 /opt/adnrpi-hackpad/main.py
