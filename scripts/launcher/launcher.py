"""
ADNRPi Launcher — choix de l'application au premier demarrage.
Ecrit le choix dans /tmp/adnrpi-next, puis quitte.
run.sh lit le fichier et sauvegarde la config.
"""
import os
from kivy.config import Config

_W = os.environ.get("HACKPAD_W", "800")
_H = os.environ.get("HACKPAD_H", "480")
Config.set("graphics", "width",       _W)
Config.set("graphics", "height",      _H)
Config.set("graphics", "fullscreen",  "0")
Config.set("graphics", "borderless",  "1")
Config.set("graphics", "position",    "custom")
Config.set("graphics", "left",        "0")
Config.set("graphics", "top",         "0")
Config.set("graphics", "show_cursor", "1")
Config.set("kivy",     "log_level",   "warning")
Config.set("input",    "mouse",       "mouse,disable_multitouch")
Config.set("kivy",     "keyboard_mode", "")

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window

Window.clearcolor = (0.04, 0.04, 0.04, 1)

_NEXT_FILE = "/tmp/adnrpi-next"

APPS = [
    {
        "key":   "scope",
        "label": "SCOPE",
        "desc":  "Oscilloscope  Multimetre  I2C",
        "color": (0.10, 0.35, 0.10, 1),
        "avail": True,
    },
    {
        "key":   "hackpad",
        "label": "HACKPAD",
        "desc":  "Interface robot  Telecommande",
        "color": (0.10, 0.18, 0.35, 1),
        "avail": os.path.exists("/opt/adnrpi-hackpad/main.py"),
    },
]


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *a: setattr(rect, "pos", widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )


def _choose(key):
    try:
        with open(_NEXT_FILE, "w") as f:
            f.write(key)
    except Exception:
        pass
    App.get_running_app().stop()


class LauncherApp(App):
    title = "ADNRPi"

    def build(self):
        root = BoxLayout(orientation="vertical", padding=[40, 30], spacing=16)
        _bg(root, (0.04, 0.04, 0.04, 1))

        # En-tête
        root.add_widget(Label(
            text="ADNRPi",
            font_size="42sp", bold=True,
            color=(0.20, 1.0, 0.40, 1),
            size_hint=(1, None), height=58,
            halign="center", valign="middle"))

        root.add_widget(Label(
            text="Choisir l'application par defaut",
            font_size="15sp",
            color=(0.65, 0.65, 0.65, 1),
            size_hint=(1, None), height=24,
            halign="center", valign="middle"))

        root.add_widget(Label(
            text="Ce choix s'appliquera a chaque demarrage.",
            font_size="13sp",
            color=(0.38, 0.38, 0.38, 1),
            size_hint=(1, None), height=20,
            halign="center", valign="middle"))

        root.add_widget(Widget(size_hint=(1, None), height=8))

        # Boutons de choix
        btn_area = BoxLayout(orientation="horizontal",
                              size_hint=(1, 1), spacing=24)
        for app in APPS:
            col = BoxLayout(orientation="vertical", spacing=6)
            btn = Button(
                text=app["label"],
                font_size="30sp", bold=True,
                background_color=app["color"] if app["avail"] else (0.14, 0.14, 0.14, 1),
                background_normal="",
                disabled=not app["avail"],
                size_hint=(1, 1))
            desc = Label(
                text=app["desc"],
                font_size="12sp",
                color=(0.48, 0.48, 0.48, 1),
                size_hint=(1, None), height=20,
                halign="center", valign="middle")
            key = app["key"]
            btn.bind(on_press=lambda *a, k=key: _choose(k))
            col.add_widget(btn)
            col.add_widget(desc)
            btn_area.add_widget(col)

        root.add_widget(btn_area)

        root.add_widget(Widget(size_hint=(1, None), height=8))

        # Bouton éteindre (discret, en bas à droite)
        btn_off = Button(
            text="Eteindre",
            font_size="14sp",
            background_color=(0.22, 0.07, 0.07, 1),
            background_normal="",
            size_hint=(None, None), height=38, width=130)
        btn_off.bind(on_press=lambda *a: _choose("poweroff"))
        off_row = BoxLayout(size_hint=(1, None), height=38)
        off_row.add_widget(Widget())
        off_row.add_widget(btn_off)
        root.add_widget(off_row)

        return root


if __name__ == "__main__":
    LauncherApp().run()
