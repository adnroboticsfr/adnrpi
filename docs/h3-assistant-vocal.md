# Assistant vocal H3 — Architecture hybride

SmartPi One H3 · micro embarqué actif · sortie jack 3.5mm · Armbian Bookworm

**Principe :** rester léger en permanence, déclencher le lourd seulement quand nécessaire.  
**État :** ⬜ À coder — architecture documentée, pas encore implémenté

---

## Comparatif moteurs de reconnaissance

| | PocketSphinx | Vosk small | Whisper tiny |
| --- | --- | --- | --- |
| RAM | ~10 MB | ~40 MB | ~200 MB |
| CPU H3 | Très léger | Léger | Lourd |
| Temps réel | ✓ | ✓ | ✗ (~4x) |
| Français | Possible (modèle limité) | ✓ Bon | ✓ Excellent |
| Reconnaissance libre | Limité | ✓ | ✓ |
| Commandes fixes | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| Offline total | ✓ | ✓ | ✓ |

---

## Architecture retenue

```
Micro SmartPi (/dev/snd)
        │
        ▼
Détection niveau sonore (VAD léger)
        │  silence → ignore
        ▼
PocketSphinx — écoute le wake word uniquement
        │  pas le bon mot → ignore
        ▼  "hey adn" / "hey robot" / mot choisi
Capture phrase complète (1-5 secondes)
        │
        ├─── Commande locale reconnue par Vosk ?
        │         │ OUI → exécution locale (contrôle scope, GPIO, etc.)
        │         │ NON ↓
        │    Internet disponible ?
        │         │ OUI → ChatGPT API → réponse TTS → haut-parleur
        │         │ NON → réponse fallback locale ("pas de connexion")
        │
        ▼
TTS (pyttsx3 ou espeak) → sortie jack
```

---

## Couches logicielles

### Couche 1 — VAD (Voice Activity Detection)
Détection d'énergie sonore simple avant de réveiller PocketSphinx.  
Évite de tourner le moteur sur le silence.

```python
import pyaudio, numpy as np

THRESHOLD = 500   # ajuster selon micro
def has_voice(data):
    arr = np.frombuffer(data, dtype=np.int16)
    return np.abs(arr).mean() > THRESHOLD
```

### Couche 2 — Wake word (PocketSphinx)

```bash
pip install pocketsphinx
```

```python
from pocketsphinx import LiveSpeech

speech = LiveSpeech(
    lm=False,
    keyphrase="hey adn",   # mot d'activation personnalisable
    kws_threshold=1e-20,
    verbose=False
)
for phrase in speech:
    print("Wake word détecté !")
    capture_and_process()
```

Modèles FR disponibles : `fr-FR` dans le dépôt PocketSphinx.

### Couche 3 — Reconnaissance commande (Vosk)

```bash
pip install vosk pyaudio
# Télécharger : https://alphacephei.com/vosk/models → vosk-model-small-fr-0.22
```

```python
from vosk import Model, KaldiRecognizer
import pyaudio, json, wave

def transcribe_phrase(seconds=5, rate=16000):
    model = Model("models/vosk-small-fr")
    rec   = KaldiRecognizer(model, rate)
    mic   = pyaudio.PyAudio()
    stream = mic.open(format=pyaudio.paInt16, channels=1,
                      rate=rate, input=True, frames_per_buffer=8000)
    frames = []
    for _ in range(int(rate / 8000 * seconds)):
        frames.append(stream.read(8000))
    stream.stop_stream()
    for f in frames:
        rec.AcceptWaveform(f)
    result = json.loads(rec.FinalResult())
    return result.get("text", "")
```

### Couche 4 — Routeur de commandes

```python
COMMANDES_LOCALES = {
    "allume la lumière":   lambda: gpio_relay(on=True),
    "éteins la lumière":   lambda: gpio_relay(on=False),
    "démarre le scope":    lambda: os.system("systemctl start adnrpi-scope"),
    "quelle heure est-il": lambda: tts(datetime.now().strftime("%H heures %M")),
    "température":         lambda: tts(f"{lire_bmp280():.1f} degrés"),
}

def router(texte):
    for cmd, action in COMMANDES_LOCALES.items():
        if cmd in texte.lower():
            action()
            return
    # Pas de commande locale → ChatGPT
    if internet_ok():
        reponse = chatgpt(texte)
        tts(reponse)
    else:
        tts("Je n'ai pas compris et je n'ai pas de connexion.")
```

### Couche 5 — ChatGPT API (optionnel, nécessite internet)

```python
from openai import OpenAI

client = OpenAI(api_key="sk-...")

def chatgpt(question, historique=[]):
    historique.append({"role": "user", "content": question})
    r = client.chat.completions.create(
        model="gpt-4o-mini",   # le moins cher, suffisant
        messages=[{"role": "system", "content": "Tu es un assistant compact sur SmartPi."}]
                 + historique[-6:],   # 3 échanges max en contexte
        max_tokens=150
    )
    rep = r.choices[0].message.content
    historique.append({"role": "assistant", "content": rep})
    return rep
```

### Couche 6 — TTS (Text to Speech)

```bash
# Option A : espeak (léger, robotique mais fonctionne offline)
apt install espeak-ng
espeak-ng -v fr "Bonjour" -a 100

# Option B : pyttsx3 (wrapper espeak, API Python)
pip install pyttsx3

# Option C : Google TTS (nécessite internet, meilleure qualité)
pip install gtts
```

```python
import pyttsx3
engine = pyttsx3.init()
engine.setProperty('voice', 'fr')   # voix française
engine.setProperty('rate', 160)
def tts(texte):
    engine.say(texte)
    engine.runAndWait()
```

---

## Consommation mémoire estimée (tout actif)

| Service | RAM |
| --- | --- |
| OS Armbian + nginx + Gitea | ~300 MB |
| PocketSphinx (écoute wake word) | ~15 MB |
| Vosk small chargé | ~60 MB |
| pyttsx3 + espeak | ~10 MB |
| Script principal Python | ~20 MB |
| **Total** | **~405 MB** |

Reste ~550 MB libre sur 1GB → confortable.

---

## Backlog implémentation

| # | Tâche | Priorité |
| --- | --- | --- |
| V1-1 | VAD + PocketSphinx wake word FR | Haute |
| V1-2 | Vosk commandes locales (5-10 commandes) | Haute |
| V1-3 | TTS espeak-ng FR | Haute |
| V1-4 | Routeur commandes locales | Haute |
| V1-5 | Intégration ChatGPT API (gpt-4o-mini) | Moyenne |
| V1-6 | Commandes GPIO (relais, LEDs) | Moyenne |
| V1-7 | Commandes scope (démarrer, arrêter) | Basse |
| V2-1 | Wake word personnalisé entraîné | Basse |
| V2-2 | Mémoire courte conversation (contexte ChatGPT) | Basse |
| V2-3 | TTS qualité supérieure (Google TTS ou Piper) | Basse |

---

## Prérequis matériels

- Micro embarqué SmartPi déjà actif (`overlay analog-codec` activé)
- Sortie jack 3.5mm SmartPi pour le son
- Connexion internet pour la couche ChatGPT (optionnelle)

## Prérequis logiciels

```bash
apt install espeak-ng python3-pyaudio portaudio19-dev
pip install pocketsphinx vosk pyttsx3 openai numpy
# Modèle Vosk FR : télécharger vosk-model-small-fr-0.22 dans /opt/adnrpi-voice/models/
```
