#!/usr/bin/env python3
import os
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
from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image as KivyImage
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Line
from kivy.core.window import Window

class T(App):
    def build(self):
        Window.size = (800, 480)
        Window.clearcolor = (0.05, 0.05, 0.08, 1)
        root = FloatLayout()
        with root.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            Rectangle(pos=(0, 0), size=(800, 480))
        root.add_widget(KivyImage(
            source="/opt/adnrpi-voice/face.jpg",
            size_hint=(None, None), size=(380, 480), pos=(0, 0),
            allow_stretch=True, keep_ratio=False))
        sep = FloatLayout(size_hint=(None, None), size=(2, 480), pos=(383, 0))
        with sep.canvas:
            Color(0.0, 0.85, 0.95, 0.4)
            Rectangle(pos=(383, 0), size=(2, 480))
        root.add_widget(sep)
        root.add_widget(Label(
            text="ADN ROBOTICS",
            font_size="24sp", bold=True, color=[0, 0.9, 1, 1],
            pos_hint={"x": 0.49, "top": 0.97},
            size_hint=(0.51, None), height=32,
            halign="center", text_size=(410, None)))
        root.add_widget(Label(
            text="EN VEILLE",
            font_size="20sp", bold=True, color=[0, 0.85, 0.95, 1],
            pos_hint={"x": 0.49, "top": 0.85},
            size_hint=(0.51, None), height=28,
            halign="center"))
        root.add_widget(Label(
            text='dites "hey robot"',
            font_size="16sp", color=[0.25, 0.6, 0.7, 0.7],
            pos_hint={"x": 0.49, "y": 0.05},
            size_hint=(0.51, None), height=24,
            halign="center"))
        print("BUILD OK - fenetre ouverte", flush=True)
        return root

T().run()
print("APP EXITED", flush=True)
