#!/usr/bin/env python3
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

STEPS = [
    ("weather", None),
    ("weather", "cloud"),
    ("weather", "cloud"),
    ("weather", "cloud"),
    ("weather", "sun"),
    ("weather", "cloud"),
    ("weather", "storm"),
    ("weather", "cloud"),
    ("weather", "snow"),
    ("weather", "cloud"),
    ("weather", None),
    ("weather", "cloud"),
]

class CloudTestApp(App):
    def build(self):
        Window.size = (800, 480)
        Window.clearcolor = (0, 0, 0, 1)
        self.face = FaceEngine(size_hint=(None, None), size=(800, 480), pos=(0, 0))
        self._i = 0
        Clock.schedule_interval(self._next, 2.8)
        return self.face

    def _next(self, dt):
        kind, val = STEPS[self._i % len(STEPS)]
        print(f"[{self._i}] {kind} = {val}", flush=True)
        if kind == "weather":
            self.face.set_weather(val)
        self._i += 1

CloudTestApp().run()
