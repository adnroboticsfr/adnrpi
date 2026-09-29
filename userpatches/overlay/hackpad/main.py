#!/usr/bin/env python3
"""
ADNRPi HackPad — touchscreen pentesting interface.
Runs on framebuffer (server mode) or X11/XFCE (desktop mode).
"""

import os
import sys

# Framebuffer / KMS backend when no display server is running
if "DISPLAY" not in os.environ and "WAYLAND_DISPLAY" not in os.environ:
    os.environ.setdefault("KIVY_WINDOW", "sdl2")
    os.environ.setdefault("SDL_VIDEODRIVER", "kmsdrm")
    os.environ.setdefault("KIVY_GL_BACKEND", "sdl2")

# Taille de la fenêtre : définie par launch.sh selon l'écran détecté.
# HACKPAD_W/H = 800/480 sur l'écran 5 pouces, résolution native sur moniteur externe.
_W = os.environ.get("HACKPAD_W", "800")
_H = os.environ.get("HACKPAD_H", "480")

from kivy.config import Config
Config.set("graphics", "width",      _W)
Config.set("graphics", "height",     _H)
Config.set("graphics", "fullscreen", "0")
Config.set("graphics", "borderless", "1")
Config.set("graphics", "position",   "custom")
Config.set("graphics", "left",       "0")
Config.set("graphics", "top",        "0")
Config.set("kivy",     "log_level",  "warning")
Config.set("graphics", "show_cursor", "1")
Config.set("input",    "mouse",      "mouse,disable_multitouch")
Config.set("kivy",     "keyboard_mode", "")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.lang import Builder
from kivy.core.window import Window
from kivy.core.text import LabelBase

_EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
import os as _os
if _os.path.exists(_EMOJI_FONT):
    LabelBase.register("NotoEmoji", _EMOJI_FONT)

from screens.home     import HomeScreen
from screens.category import CategoryScreen
from screens.tool     import ToolScreen
from screens.settings import SettingsScreen
from screens.mode     import ModeScreen

Window.clearcolor = (0.08, 0.08, 0.08, 1)


class HackPadApp(App):
    title = "ADNRPi HackPad"

    def build(self):
        sm = ScreenManager(transition=SlideTransition())
        sm.add_widget(HomeScreen(name="home"))
        sm.add_widget(CategoryScreen(name="category"))
        sm.add_widget(ToolScreen(name="tool"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(ModeScreen(name="mode"))
        return sm


if __name__ == "__main__":
    HackPadApp().run()
