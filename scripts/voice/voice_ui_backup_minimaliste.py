#!/usr/bin/env python3
"""
ADNRPi — Interface visuelle assistant vocal  800×480
Visage réaliste animé : clignement, regard mobile, bouche réactive
"""
import os, sys, json, subprocess, threading, time, math, random
import numpy as np

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
from kivy.uix.widget      import Widget
from kivy.graphics        import Color, Ellipse, Rectangle, Line, RoundedRectangle
from kivy.clock           import Clock
from kivy.core.window     import Window

# ── Constantes ─────────────────────────────────────────────────────────────────
RATE          = 16000
CHUNK         = 4000
VAD_THRESHOLD = 100
SILENCE_SECS  = 1.5
CAPTURE_SECS  = 6
MODEL_FR      = "/opt/adnrpi-voice/models/vosk-small-fr"
WAKE_WORDS    = ["hey robot", "hey robo", "ai robot", "a robot"]
REARM_DELAY   = 2.0

S_INIT, S_IDLE, S_WAKE, S_LISTENING, S_PROCESSING, S_RESULT = (
    "init", "idle", "wake", "listening", "processing", "result")

_state = {"s": S_INIT, "text": "", "response": "", "level": 0.0}
_lock  = threading.Lock()

def set_state(s, text="", response="", level=0.0):
    with _lock:
        _state["s"]        = s
        _state["text"]     = text
        _state["response"] = response
        _state["level"]    = level

def get_state():
    with _lock:
        return dict(_state)

# ── TTS ────────────────────────────────────────────────────────────────────────
def tts(texte):
    subprocess.run(["espeak-ng", "-v", "fr", "-s", "150", "-a", "150", texte],
                   capture_output=True)

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

def open_mic():
    return subprocess.Popen(
        ["arecord", "-D", "plughw:0,0", "-f", "S16_LE",
         "-r", str(RATE), "-c", "1", "--buffer-size=8192"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

def read_chunk(proc):
    return proc.stdout.read(CHUNK * 2)

_wake_rec = None

def init_wake_rec(model):
    global _wake_rec
    from vosk import KaldiRecognizer
    _wake_rec = KaldiRecognizer(model, RATE, json.dumps(WAKE_WORDS))

def wait_wake_word(proc):
    _wake_rec.Reset()
    set_state(S_IDLE)
    while True:
        chunk = read_chunk(proc)
        if _wake_rec.AcceptWaveform(chunk):
            text = json.loads(_wake_rec.Result()).get("text", "")
            for w in WAKE_WORDS:
                if w in text:
                    return

def capture_adaptive(proc):
    max_chunks    = int(CAPTURE_SECS * RATE / CHUNK)
    silence_limit = int(SILENCE_SECS * RATE / CHUNK)
    frames, speech_seen, silence_cnt = [], False, 0
    for _ in range(max_chunks):
        chunk = read_chunk(proc)
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
    from vosk import KaldiRecognizer
    rec = KaldiRecognizer(model, RATE)
    rec.AcceptWaveform(audio_bytes)
    return json.loads(rec.FinalResult()).get("text", "").lower().strip()

def voice_loop():
    if not os.path.isdir(MODEL_FR):
        set_state(S_RESULT, text="Modèle absent"); return
    from vosk import Model
    set_state(S_INIT, text="Chargement...")
    model = Model(MODEL_FR)
    init_wake_rec(model)
    proc  = open_mic()
    try:
        while True:
            wait_wake_word(proc)
            set_state(S_WAKE, text="Hey robot !")
            time.sleep(0.4)
            audio = capture_adaptive(proc)
            set_state(S_PROCESSING, text="...")
            texte   = transcribe(audio, model)
            reponse = router(texte) if texte else ""
            set_state(S_RESULT, text=texte or "(rien compris)", response=reponse)
            if reponse:
                tts(reponse)
            time.sleep(REARM_DELAY)
            drained = int((REARM_DELAY + 1) * RATE / CHUNK)
            for _ in range(drained):
                proc.stdout.read(CHUNK * 2)
    except Exception as e:
        set_state(S_RESULT, text=f"Erreur: {e}")
    finally:
        proc.terminate()

# ── Widget visage animé ─────────────────────────────────────────────────────────
class FaceWidget(Widget):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._t           = 0.0
        self._blink       = 0.0
        self._blink_timer = 3.0
        self._mouth       = 0.0
        self._eye_dx      = 0.0
        self._eye_dy      = 0.0
        self._look_timer  = 4.0
        self._scan_y      = 460.0

    def update(self, dt, s, lv):
        self._t += dt

        # ── Clignement naturel ────────────────────────────────────────────────
        if s not in (S_LISTENING, S_PROCESSING):
            self._blink_timer -= dt
            if self._blink_timer < 0:
                self._blink += dt * 14
                if self._blink >= 1.0:
                    self._blink -= dt * 14
                    if self._blink <= 0:
                        self._blink = 0.0
                        self._blink_timer = 2.0 + random.random() * 3.0
            else:
                self._blink = max(self._blink - dt * 6, 0.0)
        else:
            self._blink = max(self._blink - dt * 8, 0.0)

        # ── Regard mobile ────────────────────────────────────────────────────
        self._look_timer -= dt
        if self._look_timer <= 0:
            if s == S_IDLE:
                self._eye_dx = (random.random() - 0.5) * 0.6
                self._eye_dy = (random.random() - 0.5) * 0.3
                self._look_timer = 1.5 + random.random() * 4.0
            else:
                self._eye_dx = 0.0
                self._eye_dy = 0.05
                self._look_timer = 0.8

        # ── Bouche réactive ───────────────────────────────────────────────────
        if s == S_LISTENING:
            target_m = min(lv / 180.0, 1.0)
        elif s == S_WAKE:
            target_m = 0.65 + 0.2 * abs(math.sin(self._t * 8))
        elif s == S_PROCESSING:
            target_m = 0.25 + 0.25 * abs(math.sin(self._t * 5))
        elif s == S_RESULT:
            target_m = 0.15 + 0.08 * abs(math.sin(self._t * 2))
        else:
            target_m = 0.0
        self._mouth += (target_m - self._mouth) * min(dt * 12, 1.0)

        # Scan line descend
        spd = {S_IDLE: 35, S_WAKE: 100, S_LISTENING: 80,
               S_PROCESSING: 60, S_RESULT: 45}.get(s, 30)
        self._scan_y -= spd * dt
        if self._scan_y < -4:
            self._scan_y = 484.0

        self._draw(s, lv)

    def _draw(self, s, lv):
        cx, cy = 190, 255
        pulse  = 0.5 + 0.5 * math.sin(self._t * 1.8)
        pulse2 = 0.5 + 0.5 * math.sin(self._t * 5.0)
        breath = 0.5 + 0.5 * math.sin(self._t * 1.2)
        blink  = min(max(self._blink, 0.0), 1.0)

        if s == S_IDLE:        sc = (0.0,  0.85, 0.95)
        elif s == S_WAKE:       sc = (0.0,  1.0,  0.5)
        elif s == S_LISTENING:  sc = (1.0,  0.55, 0.0)
        elif s == S_PROCESSING: sc = (0.7,  0.2,  1.0)
        elif s == S_RESULT:     sc = (0.0,  1.0,  0.55)
        else:                    sc = (0.25, 0.35, 0.55)
        r, g, b = sc

        fw = int(212 + 4 * breath)
        fh = int(178 + 3 * breath)
        fx = cx - fw // 2
        fy = cy - fh // 2

        eye_lx = cx - 44
        eye_rx = cx + 44
        eye_y  = cy + 10
        er     = 19

        self.canvas.clear()
        with self.canvas:
            # ── Fond noir ─────────────────────────────────────────────────────
            Color(0.0, 0.0, 0.0, 1)
            Rectangle(pos=(0, 0), size=(380, 480))

            # ── Halo état (double anneau) ──────────────────────────────────────
            Color(r, g, b, 0.12 + 0.08 * pulse)
            Ellipse(pos=(fx - 30, fy - 30), size=(fw + 60, fh + 60))
            Color(r, g, b, 0.06 + 0.04 * pulse2)
            Ellipse(pos=(fx - 55, fy - 55), size=(fw + 110, fh + 110))

            # ── Ombre portée sous le visage ────────────────────────────────────
            Color(r * 0.25, g * 0.25, b * 0.25, 0.30)
            Ellipse(pos=(fx + 5, fy - 8), size=(fw, fh))

            # ── Visage : ovale blanc arrondi ───────────────────────────────────
            Color(0.96, 0.96, 0.97, 1)
            Ellipse(pos=(fx, fy), size=(fw, fh))
            # Ombre interne bas (volume)
            Color(0.82, 0.82, 0.85, 0.45)
            Ellipse(pos=(fx + 8, fy - 4), size=(fw - 16, fh * 0.30))
            # Highlight haut (brillance)
            Color(1.0, 1.0, 1.0, 0.55)
            Ellipse(pos=(fx + int(fw * 0.22), fy + int(fh * 0.62)),
                    size=(int(fw * 0.56), int(fh * 0.22)))

            # ── YEUX ──────────────────────────────────────────────────────────
            for ex in (eye_lx, eye_rx):
                ex_g = int(ex + self._eye_dx * 10)
                ey_g = int(eye_y + self._eye_dy * 6)

                if s == S_RESULT:
                    # Yeux contents : croissant vers le haut
                    bsc = max(1.0 - blink * 1.2, 0.0)
                    if bsc > 0.05:
                        Color(0.08, 0.08, 0.10, bsc)
                        ah = int(er * 1.4 * bsc)
                        Line(ellipse=(ex_g - er, ey_g - ah // 2,
                                      er * 2, ah,
                                      200, 340), width=5.0)

                elif s == S_PROCESSING:
                    # Yeux spinner (arc tournant)
                    bsc = max(1.0 - blink * 1.2, 0.0)
                    if bsc > 0.05:
                        ang = (self._t * 300) % 360
                        Color(0.08, 0.08, 0.10, bsc)
                        Line(ellipse=(ex_g - er, ey_g - int(er * bsc),
                                      er * 2, int(er * 2 * bsc),
                                      ang, ang + 230), width=4.5)
                        Color(r, g, b, 0.50 * bsc)
                        Line(ellipse=(ex_g - er + 3, ey_g - int((er - 3) * bsc),
                                      (er - 3) * 2, int((er - 3) * 2 * bsc),
                                      ang + 115, ang + 345), width=2.5)

                elif s == S_WAKE:
                    # Yeux époustouflés : cercle + anneau coloré
                    bsc = max(1.0 - blink * 1.2, 0.0)
                    if bsc > 0.05:
                        eye_h = int(er * bsc)
                        Color(0.08, 0.08, 0.10, bsc)
                        Ellipse(pos=(ex_g - er, ey_g - eye_h),
                                size=(er * 2, eye_h * 2))
                        Color(r, g, b, 0.55 * bsc * (0.7 + 0.3 * pulse2))
                        Line(ellipse=(ex_g - er - 3, ey_g - eye_h - 3,
                                      er * 2 + 6, eye_h * 2 + 6), width=2.5)

                else:
                    # Yeux normaux : cercles noirs avec catchlight
                    eye_h = int(er * (1.0 - blink))
                    if eye_h > 1:
                        Color(0.08, 0.08, 0.10, 1)
                        Ellipse(pos=(ex_g - er, ey_g - eye_h),
                                size=(er * 2, eye_h * 2))
                        # Catchlight blanc
                        if blink < 0.45:
                            bsc = 1.0 - blink * 2.0
                            Color(1.0, 1.0, 1.0, 0.82 * bsc)
                            Ellipse(pos=(ex_g - int(er * 0.25),
                                         ey_g + int(eye_h * 0.15)),
                                    size=(int(er * 0.50),
                                          int(er * 0.50 * bsc)))
                        # Réactivité audio (S_LISTENING)
                        if s == S_LISTENING:
                            lv_n = min(lv / 200.0, 1.0)
                            if lv_n > 0.05:
                                Color(r, g, b, 0.35 * lv_n)
                                d = int(5 * lv_n)
                                Ellipse(pos=(ex_g - er - d,
                                             ey_g - eye_h - d),
                                        size=(er * 2 + d * 2,
                                              eye_h * 2 + d * 2))

            # ── BOUCHE ────────────────────────────────────────────────────────
            mouth_y = fy + int(fh * 0.22)
            m_open  = self._mouth

            if m_open > 0.02:
                mw = int(60 + 22 * m_open)
                mh = int(8 + 30 * m_open)
                # Fond bouche
                Color(0.10, 0.08, 0.10, 1)
                Ellipse(pos=(cx - mw // 2, mouth_y - mh // 2),
                        size=(mw, mh))
                # Dents
                if m_open > 0.30:
                    Color(0.93, 0.91, 0.90, 1)
                    Ellipse(pos=(cx - mw // 2 + 6, mouth_y),
                            size=(mw - 12, mh // 2))
                # Reflet lèvre bas
                Color(0.80, 0.78, 0.82, 0.30)
                Ellipse(pos=(cx - mw // 2 + 10,
                              mouth_y - mh // 2 + 3),
                        size=(mw - 20, 5))
            elif s in (S_IDLE, S_RESULT):
                # Petite ligne neutre / sourire
                Color(0.55, 0.53, 0.58, 0.55)
                dy = -3 if s == S_RESULT else 0
                Line(points=[cx - 20, mouth_y + dy,
                              cx,      mouth_y - 2 + dy,
                              cx + 20, mouth_y + dy], width=2.5)

            # ── SCAN LINE ─────────────────────────────────────────────────────
            Color(r, g, b, 0.20 + 0.12 * pulse2)
            Rectangle(pos=(0, self._scan_y), size=(380, 2))
            Color(r, g, b, 0.05)
            Rectangle(pos=(0, self._scan_y - 4), size=(380, 10))

            # ── BORDURE LUMINEUSE ─────────────────────────────────────────────
            Color(r, g, b, 0.38 + 0.20 * pulse)
            Line(rectangle=(2, 2, 376, 476), width=2.0)

            # ── COINS HUD ─────────────────────────────────────────────────────
            Color(r, g, b, 0.80)
            Line(points=[4, 4,    4,  20, 20, 20],  width=1.5)
            Line(points=[376, 4, 376,  20, 360, 20], width=1.5)
            Line(points=[4, 476,  4,  460, 20, 460], width=1.5)
            Line(points=[376, 476, 376, 460, 360, 460], width=1.5)

            # ── LED ÉTAT (bas centre) ─────────────────────────────────────────
            Color(r, g, b, 0.20)
            Ellipse(pos=(cx - 14, 5), size=(28, 16))
            Color(r, g, b, 1.0)
            Ellipse(pos=(cx - 6, 7), size=(12, 12))

            # ── BARRE AUDIO ───────────────────────────────────────────────────
            if s == S_LISTENING:
                bar_w = min(370 * lv / 300.0, 370)
                Color(r * 0.15, g * 0.15, b * 0.15, 0.9)
                Rectangle(pos=(5, 26), size=(370, 8))
                Color(r, g, b, 0.95)
                Rectangle(pos=(5, 26), size=(max(bar_w, 2), 8))


# ── Panel info droit ────────────────────────────────────────────────────────────
STATE_LABELS = {
    S_INIT:       ("DÉMARRAGE",  [0.40, 0.40, 0.50, 1]),
    S_IDLE:       ("EN VEILLE",  [0.00, 0.85, 0.95, 1]),
    S_WAKE:       ("WAKE WORD",  [0.00, 1.00, 0.50, 1]),
    S_LISTENING:  ("ÉCOUTE",     [1.00, 0.55, 0.00, 1]),
    S_PROCESSING: ("ANALYSE",    [0.70, 0.20, 1.00, 1]),
    S_RESULT:     ("RÉSULTAT",   [0.00, 1.00, 0.55, 1]),
}


class VoiceUI(FloatLayout):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._t = 0.0

        # Fond global
        with self.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            Rectangle(pos=(0, 0), size=(800, 480))

        # Visage animé (moitié gauche)
        self.face = FaceWidget(
            size_hint=(None, None), size=(380, 480), pos=(0, 0))
        self.add_widget(self.face)

        # Séparateur
        sep = Widget(size_hint=(None, None), size=(2, 480), pos=(382, 0))
        with sep.canvas:
            Color(0.0, 0.85, 0.95, 0.3)
            Rectangle(pos=(382, 0), size=(2, 480))
        self.add_widget(sep)

        # Panel fond
        panel = Widget(size_hint=(None, None), size=(416, 480), pos=(384, 0))
        with panel.canvas:
            Color(0.03, 0.03, 0.06, 1)
            Rectangle(pos=(384, 0), size=(416, 480))
        self.add_widget(panel)

        # Titre
        self.add_widget(Label(
            text="ADN ROBOTICS",
            font_size="21sp", bold=True,
            color=[0.0, 0.85, 0.95, 0.85],
            pos_hint={"x": 0.485, "top": 0.98},
            size_hint=(0.51, None), height=30,
            halign="center", text_size=(410, None)))

        # Badge fond dynamique
        self.badge_bg = Widget(size_hint=(None, None), size=(200, 36), pos=(491, 393))
        self.add_widget(self.badge_bg)

        # Label état
        self.lbl_state = Label(
            text="DÉMARRAGE",
            font_size="17sp", bold=True, color=[0.4, 0.4, 0.5, 1],
            pos_hint={"x": 0.485, "top": 0.90},
            size_hint=(0.51, None), height=30,
            halign="center", text_size=(410, None))
        self.add_widget(self.lbl_state)

        # Sous-titre entendu
        self.add_widget(Label(
            text="Entendu :",
            font_size="13sp", color=[0.4, 0.5, 0.6, 0.7],
            pos_hint={"x": 0.485, "top": 0.72},
            size_hint=(0.51, None), height=18,
            halign="left", text_size=(400, None)))

        # Texte transcription
        self.lbl_text = Label(
            text="", font_size="16sp", color=[0.85, 0.95, 1.0, 1],
            pos_hint={"x": 0.485, "top": 0.65},
            size_hint=(0.51, None), height=90,
            halign="left", valign="top", text_size=(400, None))
        self.add_widget(self.lbl_text)

        # Réponse
        self.lbl_resp = Label(
            text="", font_size="19sp", bold=True, color=[0.0, 1.0, 0.55, 1],
            pos_hint={"x": 0.485, "top": 0.38},
            size_hint=(0.51, None), height=60,
            halign="center", text_size=(400, None))
        self.add_widget(self.lbl_resp)

        # Hint bas
        self.lbl_hint = Label(
            text='dites "hey robot"',
            font_size="14sp", color=[0.2, 0.55, 0.65, 0.65],
            pos_hint={"x": 0.485, "y": 0.03},
            size_hint=(0.51, None), height=22,
            halign="center")
        self.add_widget(self.lbl_hint)

        # Coins HUD panel droit
        hud = Widget(size_hint=(None, None), size=(416, 480), pos=(384, 0))
        with hud.canvas:
            Color(0.0, 0.85, 0.95, 0.22)
            Line(points=[387, 10, 387, 32, 407, 32],  width=1.2)
            Line(points=[795, 10, 795, 32, 775, 32],  width=1.2)
            Line(points=[387, 470, 387, 448, 407, 448], width=1.2)
            Line(points=[795, 470, 795, 448, 775, 448], width=1.2)
        self.add_widget(hud)

        Clock.schedule_interval(self.tick, 1 / 25.0)

    def tick(self, dt):
        self._t += dt
        st = get_state()
        s  = st["s"]
        lv = st["level"]

        self.face.update(dt, s, lv)

        label, col = STATE_LABELS.get(s, ("?", [1, 1, 1, 1]))
        self.lbl_state.text  = label
        self.lbl_state.color = col

        r, g, b = col[0], col[1], col[2]
        self.badge_bg.canvas.clear()
        with self.badge_bg.canvas:
            Color(r * 0.10, g * 0.10, b * 0.10, 1)
            RoundedRectangle(pos=(491, 393), size=(200, 36), radius=[8])
            Color(r, g, b, 0.40)
            Line(rounded_rectangle=[491, 393, 200, 36, 8], width=1.2)

        if s == S_PROCESSING:
            dots = "." * (int(self._t * 3) % 4)
            self.lbl_text.text = f"Transcription{dots}"
            self.lbl_resp.text = ""
        elif s == S_RESULT:
            self.lbl_text.text = st["text"]
            self.lbl_resp.text = st["response"]
        elif s == S_INIT:
            self.lbl_text.text = st["text"]
            self.lbl_resp.text = ""
        else:
            self.lbl_text.text = ""
            self.lbl_resp.text = ""

        self.lbl_hint.text = 'dites "hey robot"' if s == S_IDLE else ""


class VoiceApp(App):
    def build(self):
        Window.size       = (800, 480)
        Window.clearcolor = (0.05, 0.05, 0.08, 1)
        self.title        = "ADNRPi Voice"
        threading.Thread(target=voice_loop, daemon=True).start()
        return VoiceUI()


if __name__ == "__main__":
    VoiceApp().run()
