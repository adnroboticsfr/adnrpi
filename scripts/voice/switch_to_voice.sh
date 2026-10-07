#!/bin/bash
# Bascule l'app vers voice_ui et tue scope proprement
echo voice > /opt/adnrpi-launcher/startup-app
echo "startup-app = $(cat /opt/adnrpi-launcher/startup-app)"

# Tuer scope
SCOPE_PID=$(pgrep -f 'adnrpi-scope/main.py' | head -1)
if [ -n "$SCOPE_PID" ]; then
    echo "Arret scope PID $SCOPE_PID"
    kill "$SCOPE_PID"
    sleep 2
fi

# Vérifier
echo "Processus apres kill:"
ps aux | grep -E 'scope|voice_ui' | grep -v grep || echo "(aucun)"
echo "Done"
