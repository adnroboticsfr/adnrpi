#!/usr/bin/env python3
"""
Test reconnaissance vocale — mode console, sans Kivy.
Lance arecord, affiche le niveau audio, puis teste Vosk.
"""
import sys, os, json, subprocess, time
import numpy as np

RATE  = 16000
CHUNK = 4000
MODEL = "/opt/adnrpi-voice/models/vosk-small-fr"
WAKE_WORDS = ["hey robot", "hey robo", "ai robot", "a robot", "robot"]

def open_mic():
    """Ouvre arecord et retourne le process."""
    cmd = ["arecord", "-D", "plughw:0,0", "-f", "S16_LE",
           "-r", str(RATE), "-c", "1", "--buffer-size=8192"]
    print(f"[mic] commande: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(0.5)
    ret = proc.poll()
    if ret is not None:
        err = proc.stderr.read().decode()
        print(f"[mic] ERREUR arecord (code {ret}): {err}")
        sys.exit(1)
    print(f"[mic] arecord démarré PID={proc.pid}")
    return proc

def read_chunk(proc):
    data = proc.stdout.read(CHUNK * 2)
    if len(data) == 0:
        err = proc.stderr.read(200).decode()
        print(f"[mic] chunk vide! arecord stderr: {err}")
    return data

# ── 1. Test niveau audio ──────────────────────────────────────────────────────
print("=== TEST NIVEAU AUDIO (5 secondes) ===")
proc = open_mic()
max_lv = 0
for i in range(20):
    chunk = read_chunk(proc)
    if len(chunk) == 0:
        print("[mic] aucun audio — arrêt")
        proc.terminate()
        sys.exit(1)
    arr = np.frombuffer(chunk, dtype=np.int16)
    lv = float(np.abs(arr).mean())
    peak = int(np.abs(arr).max())
    max_lv = max(max_lv, lv)
    bar = "#" * int(lv / 100)
    print(f"  chunk {i+1:02d} | level={lv:6.0f} peak={peak:5d} |{bar}")
proc.terminate()

print(f"\n  Niveau max: {max_lv:.0f}")
if max_lv < 50:
    print("  ⚠ Niveau très bas — micro non connecté ou gain trop faible")
elif max_lv < 500:
    print("  ⚠ Niveau bas — bruit de fond, essaie de parler fort")
else:
    print("  ✓ Signal audio détecté")

# ── 2. Test Vosk reconnaissance ───────────────────────────────────────────────
print("\n=== TEST RECONNAISSANCE VOCALE ===")
print(f"Chargement modèle {MODEL} ...")
from vosk import Model, KaldiRecognizer
model = Model(MODEL)
rec   = KaldiRecognizer(model, RATE)
print("Modèle chargé. Parle maintenant (30 secondes) — dis 'hey robot' plusieurs fois...\n")

proc = open_mic()
deadline = time.time() + 30
detected = []
while time.time() < deadline:
    chunk = read_chunk(proc)
    if not chunk: break
    if rec.AcceptWaveform(chunk):
        text = json.loads(rec.Result()).get("text", "").strip()
        if text:
            print(f"  → TRANSCRIT: {repr(text)}")
            for w in WAKE_WORDS:
                if w in text:
                    print(f"  ✓ WAKE WORD '{w}' DÉTECTÉ !")
                    detected.append(w)
    else:
        partial = json.loads(rec.PartialResult()).get("partial", "").strip()
        if partial:
            print(f"  … partial: {partial}", end="\r")

proc.terminate()
print("\n")
if detected:
    print(f"✓ Reconnaissance OK — détecté: {detected}")
else:
    print("✗ Aucun wake word détecté sur 15s")
    print("  Transcriptions reçues ci-dessus (vide = micro muet ou gain trop bas)")
