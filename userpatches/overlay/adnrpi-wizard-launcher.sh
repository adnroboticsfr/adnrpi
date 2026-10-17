#!/bin/bash
# Lanceur du wizard premier boot — exécuté directement sur tty1 par systemd.
# Pas de getty, pas de login shell, pas de profile.d — connexion directe au TTY.

# Montrer le curseur (vt.global_cursor_default=0 l'a masqué)
printf '\033[?25h'
clear

exec /usr/local/bin/adnrpi-setup
