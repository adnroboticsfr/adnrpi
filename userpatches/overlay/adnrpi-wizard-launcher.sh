#!/bin/bash
# Lanceur du wizard premier boot — exécuté directement sur tty1 par systemd.
# Pas de getty, pas de login shell, pas de profile.d — connexion directe au TTY.

# Initialiser la discipline de ligne du terminal (indispensable quand systemd
# ouvre le TTY directement — sans ça, pas de saut de ligne, echo à côté, etc.)
stty sane
stty cols 80 rows 24

# Montrer le curseur (vt.global_cursor_default=0 l'a masqué)
printf '\033[?25h'
clear

exec /usr/local/bin/adnrpi-setup
