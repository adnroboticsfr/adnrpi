#!/usr/bin/env python3
"""
ADNRPi Oscilloscope — interface Kivy tactile pour SmartPi One.
Backends : microphone ALSA, Pi Pico USB serial, générateur synthétique.
"""
import os
import sys

# ── Xorg via DISPLAY (lancé par launch.sh sous xinit) ────────────────────────
# Si pas de DISPLAY, tenter SDL2 x11 de toute façon — pas de KMS sur Bookworm armhf

_W = os.environ.get("HACKPAD_W", "800")
_H = os.environ.get("HACKPAD_H", "480")

from kivy.config import Config
Config.set("graphics", "width",        _W)
Config.set("graphics", "height",       _H)
Config.set("graphics", "fullscreen",   "0")
Config.set("graphics", "borderless",   "1")
Config.set("graphics", "position",     "custom")
Config.set("graphics", "left",         "0")
Config.set("graphics", "top",          "0")
Config.set("graphics", "show_cursor",  "1")
Config.set("kivy",     "log_level",    "warning")
Config.set("input",    "mouse",        "mouse,disable_multitouch")
Config.set("kivy",     "keyboard_mode", "")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, NoTransition
from kivy.core.window import Window
import settings_manager as _SM
_SM.load()
Window.clearcolor = _SM.get_palette()["BG"]

from scope_screen import ScopeScreen
from meter_screen import MeterScreen
from settings_screen import SettingsScreen
from i2c_screen import I2CScreen
from uart_screen import UartScreen


class OscilloApp(App):
    title = "ADNRPi Oscilloscope"

    def build(self):
        sm = ScreenManager(transition=NoTransition())
        sm.add_widget(ScopeScreen(name="scope"))
        sm.add_widget(MeterScreen(name="meter"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(I2CScreen(name="i2c"))
        sm.add_widget(UartScreen(name="uart"))
        return sm


if __name__ == "__main__":
    OscilloApp().run()
