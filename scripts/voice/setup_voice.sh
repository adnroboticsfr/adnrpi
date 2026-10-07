#!/bin/bash
# ADNRPi — Installation assistant vocal
set -e
GRN='\033[0;32m' CYN='\033[0;36m' NC='\033[0m'
ok()   { echo -e "${GRN}[ OK ]${NC} $*"; }
info() { echo -e "${CYN}[INFO]${NC} $*"; }

mkdir -p /opt/adnrpi-voice/models

# Vosk modèle FR small
MODEL_DIR="/opt/adnrpi-voice/models/vosk-small-fr"
if [ ! -d "$MODEL_DIR" ]; then
    info "Téléchargement modèle Vosk FR small (~41MB)..."
    wget -q --show-progress -O /tmp/vosk-fr.zip \
        "https://alphacephei.com/vosk/models/vosk-model-small-fr-0.22.zip"
    unzip -q /tmp/vosk-fr.zip -d /opt/adnrpi-voice/models/
    mv /opt/adnrpi-voice/models/vosk-model-small-fr-0.22 "$MODEL_DIR"
    rm /tmp/vosk-fr.zip
    ok "Modèle Vosk FR installé"
else
    ok "Modèle Vosk FR déjà présent"
fi

# pip packages
info "Installation packages Python..."
pip3 install --quiet vosk pocketsphinx pyttsx3 2>/dev/null || \
pip3 install --quiet --break-system-packages vosk pocketsphinx pyttsx3
ok "Packages Python installés"

# Script principal
cp "$(dirname "$0")/voice_assistant.py" /opt/adnrpi-voice/
chmod +x /opt/adnrpi-voice/voice_assistant.py

echo ""
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GRN}  Assistant vocal installé${NC}"
echo -e "${GRN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  Test micro  : ${CYN}python3 /opt/adnrpi-voice/voice_assistant.py --test-mic${NC}"
echo -e "  Test TTS    : ${CYN}python3 /opt/adnrpi-voice/voice_assistant.py --test-tts${NC}"
echo -e "  Test Vosk   : ${CYN}python3 /opt/adnrpi-voice/voice_assistant.py --test-vosk${NC}"
echo -e "  Lancer      : ${CYN}python3 /opt/adnrpi-voice/voice_assistant.py${NC}"
