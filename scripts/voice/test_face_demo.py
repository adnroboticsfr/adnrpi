#!/usr/bin/env python3
"""
Demo FaceEngine — toutes les animations. pkill pour arrêter.
"""
import os, sys
os.environ.setdefault("DISPLAY", ":0")

from kivy.config import Config
Config.set("graphics", "width",      "800")
Config.set("graphics", "height",     "480")
Config.set("graphics", "fullscreen", "0")
Config.set("graphics", "borderless", "1")
Config.set("graphics", "position",   "custom")
Config.set("graphics", "left",       "0")
Config.set("graphics", "top",        "0")
Config.set("kivy",     "log_level",  "warning")

sys.path.insert(0, "/opt/adnrpi-voice")
from face_engine import FaceEngine

from kivy.app         import App
from kivy.clock       import Clock
from kivy.core.window import Window

SEQUENCE = [
    # Expressions de base
    ("expression", "neutral"),
    ("jump",       None),
    ("expression", "happy"),
    ("excited",    None),
    ("expression", "surprised"),
    ("jump",       None),
    ("expression", "love"),
    ("spin",       None),
    ("expression", "angry"),
    ("shake",      None),
    ("expression", "curious"),
    ("nod",        None),
    ("expression", "sad"),
    ("jump",       None),
    ("expression", "tired"),
    # Nouvelles animations de rotation/flip
    ("expression", "happy"),
    ("roll",       None),
    ("expression", "excited"),
    ("somersault", None),
    ("expression", "surprised"),
    ("backflip",   None),
    ("expression", "neutral"),
    ("flip_v",     None),
    # Types d'yeux
    ("eye_type",   "stars"),
    ("expression", "excited"),
    ("eye_type",   "bars"),
    ("expression", "thinking"),
    ("eye_type",   "dots"),
    ("expression", "neutral"),
    ("eye_type",   "normal"),
    # Peek
    ("peek",       "right"),
    ("expression", "surprised"),
    ("peek",       "left"),
    ("expression", "neutral"),
    # Météo (cross-fade formes)
    ("weather",    "sun"),
    ("expression", "happy"),
    ("jump",       None),
    ("weather",    "cloud"),
    ("expression", "thinking"),
    ("weather",    "snow"),
    ("expression", "curious"),
    ("weather",    "storm"),
    ("expression", "surprised"),
    ("weather",    "none"),
    ("expression", "happy"),
    # Couleurs
    ("color",      (0.8, 0.9, 1.0)),
    ("spin",       None),
    ("color",      (1.0, 0.88, 0.82)),
    ("expression", "love"),
    ("jump",       None),
    ("color",      (0.96, 0.96, 0.97)),
    ("expression", "neutral"),
]

class DemoApp(App):
    def build(self):
        Window.size       = (800, 480)
        Window.clearcolor = (0, 0, 0, 1)
        self.face  = FaceEngine(size_hint=(None, None), size=(800, 480), pos=(0, 0))
        self._step = 0
        Clock.schedule_interval(self._next, 2.2)
        return self.face

    def _next(self, dt):
        if self._step >= len(SEQUENCE):
            self._step = 0  # boucle
        kind, val = SEQUENCE[self._step]
        print(f"[{self._step}] {kind} {val}", flush=True)
        if kind == "expression":
            self.face.set_expression(val)
        elif kind == "jump":
            self.face.animate_jump()
        elif kind == "spin":
            self.face.animate_spin()
        elif kind == "shake":
            self.face.animate_shake()
        elif kind == "excited":
            self.face.animate_excited()
        elif kind == "nod":
            self.face.animate_nod()
        elif kind == "eye_type":
            self.face.set_eye_type(val)
        elif kind == "weather":
            self.face.set_weather(val)
        elif kind == "color":
            self.face.set_head_color(*val)
        elif kind == "peek":
            self.face.animate_peek(val)
        elif kind == "roll":
            self.face.animate_roll()
        elif kind == "somersault":
            self.face.animate_somersault()
        elif kind == "backflip":
            self.face.animate_backflip()
        elif kind == "flip_v":
            self.face.animate_flip_vertical()
        self._step += 1

DemoApp().run()
