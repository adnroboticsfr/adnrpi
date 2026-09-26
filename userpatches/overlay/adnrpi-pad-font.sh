#!/bin/sh
# Re-apply large console font on ADNRPi Pad at every TTY login.
# The flag file is created by adnrpipad-console-rotate.service at boot
# and lives in /run/ (cleared on reboot) so this never runs on a normal monitor.
[ -f /run/adnrpi-pad-detected ] || return 0
[ -t 1 ] || return 0
for font in \
    /usr/share/consolefonts/Uni2-Terminus32x16.psf.gz \
    /usr/share/consolefonts/Uni2-Terminus28x14.psf.gz \
    /usr/share/consolefonts/Uni2-Terminus24x12.psf.gz \
    /usr/share/consolefonts/Uni2-Terminus22x11.psf.gz \
    /usr/share/consolefonts/Uni2-Fixed18.psf.gz; do
    [ -f "${font}" ] || continue
    setfont "${font}" 2>/dev/null || true
    break
done
