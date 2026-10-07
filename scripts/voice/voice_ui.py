#!/usr/bin/env python3
"""
ADNRPi — Interface visuelle assistant vocal  800x480
"""
import os, sys, json, subprocess, threading, time, math, random
import fcntl
import numpy as np

# ── Fichier d'état partagé entre les deux processus (parent voix / enfant Kivy) ─
_STATE_FILE = "/tmp/adnrpi_state.json"
_LOCK_PATH  = "/tmp/adnrpi_voice.lock"
_LOCK_FH    = None

# ── Nettoyage des fichiers temporaires du run précédent ────────────────────────
for _f in (_STATE_FILE, _LOCK_PATH):
    try: os.remove(_f)
    except OSError: pass

os.environ.setdefault("DISPLAY", ":0")
from kivy.config import Config
Config.set("graphics", "width",        "800")
Config.set("graphics", "height",       "480")
Config.set("graphics", "fullscreen",   "0")
Config.set("graphics", "borderless",   "1")
Config.set("graphics", "position",     "custom")
Config.set("graphics", "left",         "0")
Config.set("graphics", "top",          "0")
Config.set("graphics", "show_cursor",  "0")
Config.set("kivy",     "log_level",    "warning")
Config.set("input",    "mouse",        "mouse,disable_multitouch")
Config.set("kivy",     "keyboard_mode", "")

from kivy.app             import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label       import Label
from kivy.clock           import Clock
from kivy.core.window     import Window
from kivy.graphics        import Color, Line
from face_engine          import FaceEngine

# Import vosk au niveau module (avant que Kivy ne monopolise le GIL)
from vosk import Model as VoskModel, KaldiRecognizer

# ── Constantes ──────────────────────────────────────────────────────────────────
RATE           = 16000
CHUNK          = 4000
VAD_THRESHOLD  = 100
SILENCE_SECS   = 1.5
CAPTURE_SECS   = 6
MODEL_FR       = "/opt/adnrpi-voice/models/vosk-small-fr"
WAKE_WORDS     = ["robot", "robo", "rob"]
RESULT_DISPLAY = 15.0
REARM_DELAY    = 0.3

S_INIT, S_IDLE, S_WAKE, S_LISTENING, S_PROCESSING, S_RESULT = (
    "init", "idle", "wake", "listening", "processing", "result")

# ── État en mémoire (processus parent uniquement) ───────────────────────────────
_state = {"s": S_INIT, "text": "", "response": "", "level": 0.0, "speaking": False}
_lock  = threading.Lock()

def _write_state():
    """Écrit l'état dans le fichier partagé (lecture par le processus enfant Kivy)."""
    try:
        tmp = _STATE_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(_state, f)
        os.replace(tmp, _STATE_FILE)
    except Exception:
        pass

def set_state(s, text="", response="", level=0.0):
    with _lock:
        _state["s"]        = s
        _state["text"]     = text
        _state["response"] = response
        _state["level"]    = level
    _write_state()

def get_state():
    """Lit depuis le fichier partagé — fonctionne dans les deux processus."""
    try:
        with open(_STATE_FILE) as f:
            return json.load(f)
    except Exception:
        with _lock:
            return dict(_state)

# ── TTS ─────────────────────────────────────────────────────────────────────────
def tts(texte):
    with _lock: _state["speaking"] = True
    _write_state()
    subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-a", "150", texte],
                   capture_output=True)
    with _lock: _state["speaking"] = False
    _write_state()

# ── Commandes ───────────────────────────────────────────────────────────────────
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

# ── Audio ────────────────────────────────────────────────────────────────────────
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

_wake_rec = None

def init_wake_rec(model):
    global _wake_rec
    grammar = json.dumps(["robot", "robo", "au robot", "oh robot", "le robot",
                          "un robot", "mon robot", "hey robot", "[unk]"])
    _wake_rec = KaldiRecognizer(model, RATE, grammar)

def wait_wake_word(proc):
    _wake_rec.Reset()
    set_state(S_IDLE)
    _cnt = 0
    while True:
        chunk = proc.stdout.read(CHUNK * 2)
        _cnt += 1
        lv = float(np.abs(np.frombuffer(chunk, dtype=np.int16)).mean()) if chunk else 0
        if _cnt % 10 == 0:
            print(f"[audio] level={lv:.0f}", flush=True)
        if _wake_rec.AcceptWaveform(chunk):
            text = json.loads(_wake_rec.Result()).get("text", "").strip()
            if text:
                print(f"[vosk-final] {repr(text)}", flush=True)
        else:
            text = json.loads(_wake_rec.PartialResult()).get("partial", "").strip()
            if text:
                print(f"[vosk-partial] {repr(text)}", flush=True)
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
        set_state(S_LISTENING, level=lv)
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

# ── Boucle vocale ────────────────────────────────────────────────────────────────
def voice_loop():
    global _LOCK_FH
    # Un seul processus gère la voix (le parent prend le verrou avant le fork Kivy)
    try:
        _LOCK_FH = open(_LOCK_PATH, "w")
        fcntl.flock(_LOCK_FH, fcntl.LOCK_EX | fcntl.LOCK_NB)
        _LOCK_FH.write(str(os.getpid()) + "\n")
        _LOCK_FH.flush()
    except IOError:
        print("[voice] verrou occupé — ce processus ne gère pas la voix", flush=True)
        return

    print("[voice] démarrage (PID=%d)" % os.getpid(), flush=True)
    if not os.path.isdir(MODEL_FR):
        set_state(S_RESULT, text="Modele absent")
        return
    proc = None
    try:
        print("[voice] chargement modèle...", flush=True)
        set_state(S_INIT)
        model = VoskModel(MODEL_FR)
        print("[voice] modèle chargé", flush=True)
        init_wake_rec(model)
        proc = open_mic()
        print(f"[voice] micro ouvert PID={proc.pid}", flush=True)
        while True:
            wait_wake_word(proc)
            set_state(S_WAKE, text="Hey robot !")
            time.sleep(0.15)
            audio = capture_adaptive(proc)
            set_state(S_PROCESSING)
            texte   = transcribe(audio, model)
            reponse = router(texte) if texte else ""
            print(f"[voice] texte={repr(texte)} rep={repr(reponse)}", flush=True)
            set_state(S_RESULT, text=texte or "(rien compris)", response=reponse)
            if reponse:
                tts(reponse)
            time.sleep(RESULT_DISPLAY)
            time.sleep(REARM_DELAY)
            for _ in range(int(REARM_DELAY * RATE / CHUNK) + 1):
                proc.stdout.read(CHUNK * 2)
    except RuntimeError as e:
        print(f"[voice] exit: {e}", flush=True)
    except Exception as e:
        import traceback
        print(f"[voice] ERREUR: {e}\n{traceback.format_exc()}", flush=True)
        set_state(S_RESULT, text=f"Erreur: {e}")
    finally:
        if proc:
            try: proc.terminate()
            except: pass


# ── Interface Kivy ───────────────────────────────────────────────────────────────
class VoiceUI(FloatLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._t      = 0.0
        self._prev_s = None

        # Visage
        self.face = FaceEngine(size_hint=(None, None), size=(800, 480), pos=(0, 0))
        self.add_widget(self.face)
        self.face.pause()  # libère le CPU pendant le chargement du modèle

        # Labels état normal (bas de l'écran)
        self.lbl_text = Label(
            text="", font_size="20sp", color=[0.88, 0.96, 1.0, 1],
            size=(760, 60), halign="center", valign="middle",
            text_size=(760, 60))
        self.add_widget(self.lbl_text)

        self.lbl_resp = Label(
            text="", font_size="24sp", bold=True, color=[0.0, 1.0, 0.55, 1],
            size=(760, 56), halign="center", valign="middle",
            text_size=(760, 56))
        self.add_widget(self.lbl_resp)

        # Labels écran de chargement
        self.lbl_loading = Label(
            text="", font_size="26sp", bold=True, color=[0.55, 0.75, 1.0, 1],
            size_hint=(None, None), size=(800, 70),
            pos_hint={"center_x": 0.5, "center_y": 0.66},
            halign="center", valign="middle", text_size=(800, 70))
        self.add_widget(self.lbl_loading)

        self.lbl_load_sub = Label(
            text="", font_size="17sp", color=[0.45, 0.55, 0.65, 0.9],
            size_hint=(None, None), size=(800, 44),
            pos_hint={"center_x": 0.5, "center_y": 0.54},
            halign="center", valign="middle", text_size=(800, 44))
        self.add_widget(self.lbl_load_sub)

        # Spinner de chargement (arc rotatif sous le texte)
        with self.canvas:
            self._spin_color = Color(0.3, 0.55, 1.0, 0.0)
            self._spin_line  = Line(circle=(400, 148, 34, 0, 260), width=4, cap="round")

        # 5 fps pendant le chargement, 25 fps après
        self._tick_ev = Clock.schedule_interval(self.tick, 1 / 5.0)

    # ── Positionnement labels normaux ────────────────────────────────────────────
    def _place_labels_bottom(self):
        """Texte fixe en bas — toujours sous la tête (face bottom ≈ y=130)."""
        self.lbl_resp.pos = (20, 10)
        self.lbl_text.pos = (20, 68)

    def _place_labels_center(self, has_response):
        """Texte centré — pendant S_RESULT (tête cachée)."""
        if has_response:
            self.lbl_resp.pos = (20, 262)
            self.lbl_text.pos = (20, 178)
        else:
            self.lbl_resp.pos = (20, 10)
            self.lbl_text.pos = (20, 210)

    # ── Changement d'état ────────────────────────────────────────────────────────
    def _on_state_enter(self, s):
        if s == S_INIT:
            return
        self.face.resume()
        self.face.set_state(s)
        if s == S_WAKE:
            self.face.set_eye_type("stars")
            self.face.animate_jump()
            Clock.schedule_once(lambda _: self.face.animate_excited(), 0.35)
        elif s == S_LISTENING:
            self.face.set_eye_type("normal")
            self.face.animate_nod()
        elif s == S_PROCESSING:
            self.face.set_eye_type("normal")
            self.face.animate_spin()
        elif s == S_RESULT:
            self.face.set_eye_type("normal")
            self.face.pause()  # face cachée pendant l'affichage du résultat
        elif s == S_IDLE:
            self.face.set_eye_type("normal")

    # ── Tick ────────────────────────────────────────────────────────────────────
    def tick(self, dt):
        self._t += dt
        st = get_state()
        s  = st["s"]

        if s != self._prev_s:
            self._on_state_enter(s)
            self._prev_s = s
            if s != S_INIT:
                self._tick_ev.cancel()
                self._tick_ev = Clock.schedule_interval(self.tick, 1 / 25.0)

        # ── Chargement ──────────────────────────────────────────────────────────
        if s == S_INIT:
            self.face.opacity      = 0
            self.lbl_text.text     = ""
            self.lbl_resp.text     = ""
            self.lbl_loading.text  = "Chargement du modele vocal..."
            self.lbl_load_sub.text = "Veuillez patienter"
            a = (self._t * 240) % 360
            self._spin_line.circle = (400, 148, 34, a, a + 260)
            self._spin_color.a     = 0.85
            return

        self.lbl_loading.text  = ""
        self.lbl_load_sub.text = ""
        self._spin_color.a     = 0.0

        # ── Résultat : tête cachée, texte centré en grand ───────────────────────
        if s == S_RESULT:
            self.face.opacity = 0
            rep = st.get("response", "")
            trs = st.get("text", "")
            self._place_labels_center(bool(rep))
            self.lbl_resp.text = rep
            self.lbl_text.text = trs
            return

        # ── Interface normale ────────────────────────────────────────────────────
        self.face.opacity = 1
        self.face.speak(st.get("speaking", False))
        self._place_labels_bottom()

        if s == S_PROCESSING:
            dots = "." * (int(self._t * 3) % 4)
            self.lbl_text.text = ""
            self.lbl_resp.text = f"Analyse en cours{dots}"
        else:
            self.lbl_text.text = ""
            self.lbl_resp.text = ""


class VoiceApp(App):
    def build(self):
        Window.size       = (800, 480)
        Window.clearcolor = (0, 0, 0, 1)
        self.title        = "ADNRPi Voice"
        return VoiceUI()


if __name__ == "__main__":
    # voice_loop démarre AVANT Kivy → le parent prend le verrou avant le fork
    threading.Thread(target=voice_loop, daemon=True).start()
    VoiceApp().run()
