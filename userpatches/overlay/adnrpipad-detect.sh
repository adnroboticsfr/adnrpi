#!/bin/sh
# ADNRPi Pad screen detection
# The ADNRPi Pad built-in screen is a 4.3" HDMI 800x480 panel with a USB touchscreen.
# A plain HDMI monitor never matches both criteria, so rotation is only applied
# on a real ADNRPi Pad.
# Exit 0 if the ADNRPi Pad screen is detected, 1 otherwise.
#
# Usage: adnrpipad-detect.sh              full check (resolution + touchscreen)
#        adnrpipad-detect.sh --screen-only  resolution check only (instant, no
#                                          dependency on USB touch enumeration)

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
    # 800x480 anywhere in the mode list of a connected DRM output. Not just the
    # first entry: the video= mode forced on the kernel command line (720p, for
    # 4K screen compatibility) is inserted at the head of the list, but the
    # panel's native 800x480 stays in it. No regular monitor or TV advertises
    # 800x480, so scanning the whole list is just as discriminating.
    for conn in /sys/class/drm/card*-*; do
        [ -f "${conn}/status" ] || continue
        [ "$(cat "${conn}/status")" = "connected" ] || continue
        grep -q "^${ADNRPIPAD_RES}$" "${conn}/modes" 2>/dev/null && return 0
    done
    # Fallback when no DRM connector info is available: framebuffer size
    if [ -f /sys/class/graphics/fb0/virtual_size ]; then
        grep -q "^800,480$" /sys/class/graphics/fb0/virtual_size && return 0
    fi
    return 1
}

if [ "$1" = "--screen-only" ]; then
    has_adnrpipad_resolution
else
    has_touchscreen && has_adnrpipad_resolution
fi
