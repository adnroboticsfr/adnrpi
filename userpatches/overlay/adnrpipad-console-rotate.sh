#!/bin/sh
# Rotate the tty console 180 degrees when the ADNRPi Pad screen is detected.
# Retries for a while because DRM and USB touch devices settle asynchronously
# during boot. On a normal monitor this simply times out and does nothing.

TRIES=20

i=0
while [ "${i}" -lt "${TRIES}" ]; do
    if [ -w /sys/class/graphics/fbcon/rotate_all ] && /usr/local/bin/adnrpipad-detect.sh; then
        # Pre-allocate the standard VTs first: rotate_all only rotates
        # already-allocated consoles, later ones would stay unrotated
        for n in 1 2 3 4 5 6; do
            : > "/dev/tty${n}" 2>/dev/null || true
        done
        echo 2 > /sys/class/graphics/fbcon/rotate_all
        echo "adnrpipad-console-rotate: ADNRPi Pad screen detected, console rotated 180 degrees"
        exit 0
    fi
    i=$((i + 1))
    sleep 1
done

echo "adnrpipad-console-rotate: no ADNRPi Pad screen detected, keeping normal orientation"
exit 0
