#!/bin/sh
# Rotate the tty console and set the correct HDMI resolution for the
# ADNRPi Pad (800x480) or a normal monitor (720p).
#
# The H3 kernel reads the video= mode from armbianEnv.txt at boot; it cannot
# be changed live. When the wrong mode is detected this script updates
# armbianEnv.txt and reboots ONCE (guarded by a flag file on /boot to prevent
# reboot loops). On the next boot the mode is already correct.
#
# Retries for a while because the USB touchscreen settles asynchronously.

TRIES=20
BOOT_CFG="/boot/armbianEnv.txt"
REBOOT_FLAG="/boot/.adnrpi-display-reboot"
PAD_FLAG="/run/adnrpi-pad-detected"
MODE_720P="video=HDMI-A-1:1280x720@60"
MODE_800P="video=HDMI-A-1:800x480@60"

# ── Helpers ──────────────────────────────────────────────────────────────────

current_mode() {
    grep -o 'video=HDMI-A-1:[^[:space:]]*' "${BOOT_CFG}" 2>/dev/null | head -1
}

set_mode() {
    local new="$1"
    if grep -q 'video=HDMI-A-1:' "${BOOT_CFG}" 2>/dev/null; then
        sed -i "s|video=HDMI-A-1:[^[:space:]]*|${new}|" "${BOOT_CFG}"
    elif grep -q '^extraargs=' "${BOOT_CFG}" 2>/dev/null; then
        sed -i "s|^extraargs=\(.*\)|extraargs=\1 ${new}|" "${BOOT_CFG}"
    else
        echo "extraargs=${new}" >> "${BOOT_CFG}"
    fi
}

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
        echo "adnrpipad: font $(basename ${font})"
        return 0
    done
}

do_reboot() {
    local reason="$1"
    touch "${REBOOT_FLAG}"
    echo "adnrpipad: ${reason} — rebooting in 3s..."
    sleep 3
    systemctl reboot
}

# ── Detection loop ────────────────────────────────────────────────────────────

i=0
PAD_FOUND=0
while [ "${i}" -lt "${TRIES}" ]; do
    if [ -w /sys/class/graphics/fbcon/rotate_all ] && /usr/local/bin/adnrpipad-detect.sh; then
        PAD_FOUND=1
        break
    fi
    i=$((i + 1))
    sleep 1
done

# ── Pad found ─────────────────────────────────────────────────────────────────

if [ "${PAD_FOUND}" -eq 1 ]; then
    MODE=$(current_mode)

    if [ "${MODE}" != "${MODE_800P}" ]; then
        # Wrong resolution — switch to 800x480 and reboot (once)
        if [ -f "${REBOOT_FLAG}" ]; then
            echo "adnrpipad: pad found but mode is ${MODE} — armbianEnv write may have failed, skipping reboot"
        else
            set_mode "${MODE_800P}"
            do_reboot "pad detected, switching to native 800x480"
            exit 0
        fi
    fi

    # Mode is already 800x480 — clean up flag and configure console
    rm -f "${REBOOT_FLAG}"

    for n in 1 2 3 4 5 6; do
        : > "/dev/tty${n}" 2>/dev/null || true
    done
    echo 2 > /sys/class/graphics/fbcon/rotate_all
    apply_pad_font
    touch "${PAD_FLAG}"
    echo "adnrpipad: ADNRPi Pad detected — rotated 180°, 800x480, large font"
    exit 0
fi

# ── No pad found ──────────────────────────────────────────────────────────────

MODE=$(current_mode)

if [ "${MODE}" = "${MODE_800P}" ]; then
    # Left in pad mode but no pad connected — switch back to 720p (once)
    if [ -f "${REBOOT_FLAG}" ]; then
        echo "adnrpipad: no pad, mode is 800x480 — skipping reboot (already tried)"
    else
        set_mode "${MODE_720P}"
        do_reboot "no pad detected, restoring 720p"
        exit 0
    fi
fi

rm -f "${REBOOT_FLAG}"
echo "adnrpipad: no ADNRPi Pad screen detected, keeping normal orientation"
exit 0
