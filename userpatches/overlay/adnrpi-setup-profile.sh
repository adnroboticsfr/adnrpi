#!/bin/bash
# /etc/profile.d/adnrpi-setup.sh
# Launches the setup wizard on every login until configuration is complete.
# After an OS update, prompts the user to review new options.

SETUP_VERSION=1   # must match adnrpi-setup
SETUP_CONF="/etc/adnrpi/setup.conf"

# Only in interactive shells
[[ $- != *i* ]] && return
[[ -z "$PS1" ]] && return

# Only for root (setup requires root)
[[ $EUID -ne 0 ]] && return

if [[ ! -f "${SETUP_CONF}" ]]; then
    # ── First boot: setup has never run ──────────────────────────────────────
    echo ""
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │  Welcome to ADNRPi!                         │"
    echo "  │  Initial setup is required.                 │"
    echo "  └─────────────────────────────────────────────┘"
    echo ""
    echo "  Starting setup wizard in 3 seconds…"
    echo "  (Press Ctrl+C to skip and run 'adnrpi-setup' later)"
    echo ""
    sleep 3
    adnrpi-setup
else
    # ── Check for OS update with new options ─────────────────────────────────
    installed_ver=$(grep "^SETUP_VERSION=" "${SETUP_CONF}" 2>/dev/null | cut -d= -f2)
    if [[ "${installed_ver:-0}" -lt "${SETUP_VERSION}" ]]; then
        echo ""
        echo "  ADNRPi: New configuration options are available after this update."
        echo "  Run 'adnrpi-setup' to review and apply them."
        echo ""
    fi
fi
