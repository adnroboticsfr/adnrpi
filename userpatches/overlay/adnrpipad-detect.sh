#!/bin/sh
# ADNRPi Pad screen detection
# The ADNRPi Pad is a 4.3" 800x480 HDMI panel with a USB touchscreen.
# Detection uses ONLY EDID (what the screen natively advertises) — NOT the
# kernel framebuffer size, which reflects the forced cmdline mode (720p or
# 800p) and would give false positives on normal monitors.
#
# Exit 0 if ADNRPi Pad detected, 1 otherwise.
# Usage: adnrpipad-detect.sh              full check (touchscreen + EDID)
#        adnrpipad-detect.sh --screen-only  EDID only (no USB dependency)

ADNRPIPAD_RES="800x480"

has_touchscreen() {
    for dev in /dev/input/event*; do
        [ -e "${dev}" ] || continue
        udevadm info --query=property --name="${dev}" 2>/dev/null \
            | grep -q "^ID_INPUT_TOUCHSCREEN=1" && return 0
    done
    return 1
}

has_adnrpipad_resolution() {
    # Check EDID-reported modes from every connected DRM output.
    # This list comes from what the screen itself advertises — it is NOT
    # affected by the video= kernel cmdline override.
    # Standard monitors/TVs never advertise 800x480 in their EDID.
    for conn in /sys/class/drm/card*-*; do
        [ -f "${conn}/status" ] || continue
        [ "$(cat "${conn}/status")" = "connected" ] || continue
        grep -q "^${ADNRPIPAD_RES}$" "${conn}/modes" 2>/dev/null && return 0
    done
    return 1
    # NOTE: the fb0/virtual_size fallback was intentionally removed — it
    # reflected the forced kernel cmdline mode, not the screen's EDID, and
    # caused false positives (rotation on normal monitors when armbianEnv.txt
    # still had 800x480 from a previous pad session).
}

if [ "$1" = "--screen-only" ]; then
    has_adnrpipad_resolution
else
    has_touchscreen && has_adnrpipad_resolution
fi
