#!/usr/bin/env python3
"""
ADNRPi — Assistant vocal mode console (sans Kivy)
"""
import os, sys, json, subprocess, threading, time
import numpy as np
from vosk import Model as VoskModel, KaldiRecognizer

RATE           = 16000
CHUNK          = 4000
VAD_THRESHOLD  = 100
SILENCE_SECS   = 1.5
CAPTURE_SECS   = 6
MODEL_FR       = "/opt/adnrpi-voice/models/vosk-small-fr"
WAKE_WORDS     = ["robot", "robo", "rob"]
RESULT_DISPLAY = 5.0
REARM_DELAY    = 0.3

def cmd_heure():
    from datetime import datetime
    h = datetime.now()
    return f"Il est {h.hour}h{h.minute:02d}"

def cmd_temperature():
    try:
        t = int(open("/sys/class/thermal/thermal_zone0/temp").read()) // 1000
        return f"CPU : {t}°C"
    except Exception:
        return "Capteur indisponible"

COMMANDES = {
    "heure":        cmd_heure,
    "quelle heure": cmd_heure,
    "température":  cmd_temperature,
    "temp":         cmd_temperature,
}

def router(texte):
    if not texte:
        return ""
    for mot, action in COMMANDES.items():
        if mot in texte:
            return action()
    return ""

def tts(texte):
    subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-a", "150", texte],
                   capture_output=True)

def open_mic():
    proc = subprocess.Popen(
        ["arecord", "-D", "plughw:0,0", "-f", "S16_LE",
         "-r", str(RATE), "-c", "1", "--buffer-size=8192"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.4)
    if proc.poll() is not None:
        err = proc.stderr.read().decode().strip()
        raise RuntimeError(f"arecord: {err}")
    return proc

def init_wake_rec(model):
    grammar = json.dumps(["robot", "robo", "au robot", "oh robot", "le robot",
                          "un robot", "mon robot", "hey robot", "[unk]"])
    return KaldiRecognizer(model, RATE, grammar)

def wait_wake_word(proc, wake_rec):
    wake_rec.Reset()
    print("[écoute] en attente du mot clé...", flush=True)
    cnt = 0
    while True:
        chunk = proc.stdout.read(CHUNK * 2)
        cnt += 1
        lv = float(np.abs(np.frombuffer(chunk, dtype=np.int16)).mean()) if chunk else 0
        if cnt % 10 == 0:
            print(f"  level={lv:.0f}", flush=True)
        if wake_rec.AcceptWaveform(chunk):
            text = json.loads(wake_rec.Result()).get("text", "").strip()
            if text:
                print(f"  vosk: {repr(text)}", flush=True)
        else:
            text = json.loads(wake_rec.PartialResult()).get("partial", "").strip()
            if text:
                print(f"  partial: {repr(text)}", flush=True)
        for w in WAKE_WORDS:
            if w in text:
                print(f"[wake] DÉTECTÉ: {repr(w)}", flush=True)
                return

def capture_adaptive(proc):
    max_chunks    = int(CAPTURE_SECS * RATE / CHUNK)
    silence_limit = int(SILENCE_SECS * RATE / CHUNK)
    frames, speech_seen, silence_cnt = [], False, 0
    for _ in range(max_chunks):
        chunk = proc.stdout.read(CHUNK * 2)
        frames.append(chunk)
        lv = float(np.abs(np.frombuffer(chunk, dtype=np.int16)).mean())
        if lv > VAD_THRESHOLD:
            speech_seen = True; silence_cnt = 0
        elif speech_seen:
            silence_cnt += 1
        if speech_seen and silence_cnt >= silence_limit:
            break
    return b"".join(frames)

def transcribe(audio_bytes, model):
    rec = KaldiRecognizer(model, RATE)
    rec.AcceptWaveform(audio_bytes)
    return json.loads(rec.FinalResult()).get("text", "").lower().strip()

def main():
    if not os.path.isdir(MODEL_FR):
        print(f"[erreur] modèle absent: {MODEL_FR}", flush=True)
        sys.exit(1)

    print("[init] chargement modèle Vosk...", flush=True)
    model    = VoskModel(MODEL_FR)
    wake_rec = init_wake_rec(model)
    print("[init] modèle chargé", flush=True)

    proc = open_mic()
    print(f"[init] micro ouvert (arecord PID={proc.pid})", flush=True)
    print("=" * 50, flush=True)

    try:
        while True:
            wait_wake_word(proc, wake_rec)

            print("[écoute] je vous écoute...", flush=True)
            time.sleep(0.15)
            audio = capture_adaptive(proc)

            print("[transcription] analyse...", flush=True)
            texte   = transcribe(audio, model)
            reponse = router(texte) if texte else ""

            print(f"\n>>> TRANSCRIT : {repr(texte)}", flush=True)
            if reponse:
                print(f">>> RÉPONSE   : {reponse}", flush=True)
                tts(reponse)
            else:
                print(">>> (aucune commande reconnue)", flush=True)
            print("=" * 50, flush=True)

            time.sleep(REARM_DELAY)
            for _ in range(int(REARM_DELAY * RATE / CHUNK) + 1):
                proc.stdout.read(CHUNK * 2)

    except KeyboardInterrupt:
        print("\n[arrêt]", flush=True)
    finally:
        proc.terminate()

if __name__ == "__main__":
    main()
