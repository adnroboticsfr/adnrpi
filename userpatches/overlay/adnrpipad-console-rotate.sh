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
        fname="$(basename "${font}" .psf.gz)"
        for n in 1 2 3 4 5 6; do
            setfont "${font}" -C "/dev/tty${n}" 2>/dev/null || true
        done
        # Write font into vconsole.conf so that systemd-vconsole-setup
        # re-applies OUR large font instead of the default small one when
        # it re-triggers via udev (USB touchscreen settling at boot).
        KEYMAP="$(grep '^KEYMAP=' /etc/vconsole.conf 2>/dev/null | cut -d= -f2)"
        printf 'FONT=%s\nKEYMAP=%s\n' "${fname}" "${KEYMAP}" > /etc/vconsole.conf
        echo "adnrpipad: font ${fname} (written to /etc/vconsole.conf)"
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
    # Pad was present on a previous boot — reset rotation to 0.
    echo 0 > /sys/class/graphics/fbcon/rotate_all 2>/dev/null || true
    rm -f "${PAD_FLAG}"
    # Restore vconsole.conf to default (remove FONT line so the system default is used)
    KEYMAP="$(grep '^KEYMAP=' /etc/vconsole.conf 2>/dev/null | cut -d= -f2)"
    if [ -n "${KEYMAP}" ]; then
        printf 'KEYMAP=%s\n' "${KEYMAP}" > /etc/vconsole.conf
    else
        rm -f /etc/vconsole.conf
    fi
    echo "adnrpipad: pad removed — rotation reset to 0°, vconsole.conf restored"
else
    echo "adnrpipad: aucun ADNRPi Pad détecté"
fi

exit 0
