#!/usr/bin/env python3
"""
ADNRPi — Assistant vocal
Wake word "hey robot" → capture 5s → Vosk FR batch → commandes locales
"""
import sys, os, json, subprocess, time, threading
import numpy as np

RATE            = 16000
CHUNK           = 4000        # 0.25s
CAPTURE_SECS    = 6           # durée max de capture après wake word
VAD_THRESHOLD   = 100         # silence~55, voix détectable même à distance
SILENCE_SECS    = 1.5         # secondes de silence après parole pour arrêter
MODEL_FR        = "/opt/adnrpi-voice/models/vosk-small-fr"
WAKE_WORDS      = ["hey robot", "hey robo", "ai robot", "a robot"]
REARM_DELAY     = 2.0         # délai avant de ré-armer le wake word après TTS
TTS_WAV         = "/tmp/adnrpi-tts.wav"

# ── TTS ────────────────────────────────────────────────────────────────────────
def tts(texte, to_file=False):
    print(f"[TTS] {texte}")
    if to_file:
        subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-w", TTS_WAV, texte],
                       capture_output=True)
    else:
        subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-a", "150", texte],
                       capture_output=True)

# ── Commandes locales ───────────────────────────────────────────────────────────
def cmd_heure():
    from datetime import datetime
    h = datetime.now()
    return f"Il est {h.hour} heures {h.minute:02d}"

def cmd_temperature():
    try:
        t = int(open("/sys/class/thermal/thermal_zone0/temp").read()) // 1000
        return f"La température du processeur est {t} degrés"
    except Exception:
        return "Capteur température indisponible"

COMMANDES = {
    "heure":        cmd_heure,
    "quelle heure": cmd_heure,
    "température":  cmd_temperature,
    "temp":         cmd_temperature,
}

def router(texte):
    if not texte:
        print("(rien compris)")
        return
    print(f">>> {texte}")
    for mot, action in COMMANDES.items():
        if mot in texte:
            reponse = action()
            tts(reponse)
            return

# ── Stream micro continu ────────────────────────────────────────────────────────
def open_mic():
    return subprocess.Popen(
        ["arecord", "-D", "plughw:0,0", "-f", "S16_LE",
         "-r", str(RATE), "-c", "1", "--buffer-size=8192"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )

def read_chunk(proc):
    return proc.stdout.read(CHUNK * 2)

# ── Wake word — grammar restreinte, Reset() entre chaque tour ───────────────────
_wake_rec = None

def init_wake_rec(model):
    global _wake_rec
    from vosk import KaldiRecognizer
    _wake_rec = KaldiRecognizer(model, RATE, json.dumps(WAKE_WORDS))

def wait_wake_word(proc):
    _wake_rec.Reset()
    print("[PRÊT] En écoute... dites 'hey robot'")
    while True:
        chunk = read_chunk(proc)
        if _wake_rec.AcceptWaveform(chunk):
            text = json.loads(_wake_rec.Result()).get("text", "")
            for w in WAKE_WORDS:
                if w in text:
                    print("[WAKE] Hey robot détecté !")
                    return

# ── Capture + transcription streaming simultanés ───────────────────────────────
def capture_adaptive(proc, max_seconds=CAPTURE_SECS):
    """Capture adaptative : lecture seule (rapide), VAD énergie, s'arrête au silence."""
    max_chunks    = int(max_seconds * RATE / CHUNK)
    silence_limit = int(SILENCE_SECS * RATE / CHUNK)
    frames, speech_seen, silence_cnt = [], False, 0

    sys.stdout.write("[ÉCOUTE] ")
    sys.stdout.flush()

    for _ in range(max_chunks):
        chunk = read_chunk(proc)
        frames.append(chunk)
        lv = float(np.abs(np.frombuffer(chunk, dtype=np.int16)).mean())

        if lv > VAD_THRESHOLD:
            speech_seen = True
            silence_cnt = 0
            sys.stdout.write("█")
        else:
            sys.stdout.write("·")
            if speech_seen:
                silence_cnt += 1
        sys.stdout.flush()

        if speech_seen and silence_cnt >= silence_limit:
            break

    sys.stdout.write("\n")
    return b"".join(frames)

def transcribe(audio_bytes, model):
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(model, RATE)
    rec.AcceptWaveform(audio_bytes)
    return json.loads(rec.FinalResult()).get("text", "").lower().strip()

def transcribe_animated(audio_bytes, model):
    result = [None]
    def _work(): result[0] = transcribe(audio_bytes, model)
    t = threading.Thread(target=_work, daemon=True)
    t.start()
    sp = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
    i = 0
    while t.is_alive():
        sys.stdout.write(f"\r{sp[i%len(sp)]} Analyse...")
        sys.stdout.flush()
        i += 1
        time.sleep(0.1)
    sys.stdout.write("\r               \r")
    return result[0]

def capture_and_transcribe(proc, model, seconds=CAPTURE_SECS):
    audio = capture_adaptive(proc, max_seconds=seconds)
    return transcribe_animated(audio, model)

# ── Tests ───────────────────────────────────────────────────────────────────────
def test_mic():
    print("[TEST MIC] Enregistrement 3 secondes — parlez...")
    proc = open_mic()
    frames = [read_chunk(proc) for _ in range(int(3 * RATE / CHUNK))]
    proc.terminate()
    lv = np.abs(np.frombuffer(b"".join(frames), dtype=np.int16)).mean()
    print(f"Niveau moyen : {lv:.0f}")
    if lv < 50:    print("ATTENTION : niveau très faible")
    elif lv < 200: print("Faible — parler plus fort ou s'approcher")
    else:          print("Micro OK")

def test_tts():
    print("[TEST TTS]")
    tts("Bonjour, je suis l'assistant vocal du SmartPi.", to_file=True)
    if os.path.exists(TTS_WAV):
        print(f"OK — {TTS_WAV}")
    else:
        print("ERREUR")

def test_vosk():
    if not os.path.isdir(MODEL_FR):
        print(f"Modèle absent : {MODEL_FR}"); return
    from vosk import Model
    print("[INIT] Chargement modèle...")
    model = Model(MODEL_FR)
    proc = open_mic()
    try:
        texte = capture_and_transcribe(proc, model, seconds=5)
        print(f">>> {texte if texte else '(rien compris)'}")
    finally:
        proc.terminate()

# ── Main ────────────────────────────────────────────────────────────────────────
def main():
    if not os.path.isdir(MODEL_FR):
        print(f"Modèle absent : {MODEL_FR}"); sys.exit(1)
    from vosk import Model
    print("[INIT] Chargement modèle Vosk...")
    model = Model(MODEL_FR)
    init_wake_rec(model)
    proc = open_mic()
    print("[PRÊT] Assistant vocal ADNRPi — dites 'hey robot'")
    try:
        while True:
            wait_wake_word(proc)
            texte = capture_and_transcribe(proc, model, seconds=CAPTURE_SECS)
            router(texte)
            time.sleep(REARM_DELAY)
            # Drainer le buffer micro accumulé pendant TTS + délai
            drained = int((REARM_DELAY + 1) * RATE / CHUNK)
            for _ in range(drained):
                proc.stdout.read(CHUNK * 2)
    except KeyboardInterrupt:
        pass
    finally:
        proc.terminate()

if __name__ == "__main__":
    if "--test-mic"   in sys.argv: test_mic()
    elif "--test-tts"  in sys.argv: test_tts()
    elif "--test-vosk" in sys.argv: test_vosk()
    else: main()
