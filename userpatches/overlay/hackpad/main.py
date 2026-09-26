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
    os.environ.setdefault("SDL_RENDERDRIVER", "opengles2")
    os.environ.setdefault("KIVY_GL_BACKEND", "sdl2")

from kivy.config import Config
Config.set("graphics", "width",  "800")
Config.set("graphics", "height", "480")
Config.set("graphics", "fullscreen", "auto")
Config.set("kivy", "log_level", "warning")
Config.set("input", "mouse", "mouse,disable_multitouch")

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, SlideTransition
from kivy.lang import Builder
from kivy.core.window import Window

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
