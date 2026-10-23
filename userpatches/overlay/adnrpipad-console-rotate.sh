#!/bin/sh
# ADNRPi Pad console rotation
#
# Detects the ADNRPi Pad at boot and rotates the console 180° + applies a
# large font for the 4.3" 800x480 panel.
# On a normal HDMI monitor (pad not detected) it explicitly resets rotation
# to 0 so a previous pad session does not leave the screen upside-down.
#
# Resolution is NOT changed here. Use  adnrpi-display-mode [pad|hdmi]
# to switch armbianEnv.txt and reboot when you change screen type.
#
# Retries for a while because the USB touchscreen settles asynchronously.

TRIES=10
PAD_FLAG="/run/adnrpi-pad-detected"

# ── Font helper ───────────────────────────────────────────────────────────────

apply_pad_font() {
    for font in \
        /usr/share/consolefonts/Uni2-Terminus32x16.psf.gz \
        /usr/share/consolefonts/Uni2-Terminus28x14.psf.gz \
        /usr/share/consolefonts/Uni2-Terminus24x12.psf.gz \
        /usr/share/consolefonts/Uni2-Terminus22x11.psf.gz \
        /usr/share/consolefonts/Uni2-Fixed18.psf.gz; do
        [ -f "${font}" ] || continue
        for n in 1 2 3 4 5 6; do
            setfont "${font}" -C "/dev/tty${n}" 2>/dev/null || true
        done
        echo "adnrpipad: font $(basename "${font}")"
        return 0
    done
}

# ── Detection loop ────────────────────────────────────────────────────────────

i=0
PAD_FOUND=0
while [ "${i}" -lt "${TRIES}" ]; do
    if [ -w /sys/class/graphics/fbcon/rotate_all ] && \
       /usr/local/bin/adnrpipad-detect.sh; then
        PAD_FOUND=1
        break
    fi
    i=$((i + 1))
    sleep 1
done

# ── Apply or reset ────────────────────────────────────────────────────────────

if [ "${PAD_FOUND}" -eq 1 ]; then
    echo 2 > /sys/class/graphics/fbcon/rotate_all
    apply_pad_font
    touch "${PAD_FLAG}"
    echo "adnrpipad: ADNRPi Pad detected — rotated 180°, large font applied"
elif [ -f "${PAD_FLAG}" ]; then
    # Pad était présent à un boot précédent — remettre la rotation à 0.
    # On n'écrit rotate_all que si on sait qu'il y avait une rotation active,
    # pour ne pas effacer la console sur un écran HDMI normal.
    echo 0 > /sys/class/graphics/fbcon/rotate_all 2>/dev/null || true
    rm -f "${PAD_FLAG}"
    echo "adnrpipad: Pad retiré — rotation remise à 0°"
else
    echo "adnrpipad: aucun ADNRPi Pad détecté"
fi

exit 0
