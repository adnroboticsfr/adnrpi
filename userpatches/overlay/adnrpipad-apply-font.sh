#!/bin/sh
# Re-apply large Terminus font after systemd-vconsole-setup runs.
# Called via a drop-in ExecStartPost= so this fires every time vconsole-setup
# runs (boot, udev retrigger, keyboard hotplug...) and ensures the large font
# is always the final result when the ADNRPi Pad is connected.
[ -f /run/adnrpi-pad-detected ] || exit 0
for f in \
    /usr/share/consolefonts/Uni2-Terminus32x16.psf.gz \
    /usr/share/consolefonts/Uni2-Terminus28x14.psf.gz \
    /usr/share/consolefonts/Uni2-Terminus24x12.psf.gz \
    /usr/share/consolefonts/Uni2-Terminus22x11.psf.gz \
    /usr/share/consolefonts/Uni2-Fixed18.psf.gz; do
    [ -f "$f" ] || continue
    for n in 1 2 3 4 5 6; do
        setfont "$f" -C "/dev/tty${n}" 2>/dev/null || true
    done
    exit 0
done
