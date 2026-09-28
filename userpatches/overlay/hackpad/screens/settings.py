import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

from screens.keyboard import make_field_button

SETTINGS_FILE = "/etc/adnrpi-hackpad/settings.conf"

FIELDS = [
    ("Target IP",  "target_ip",  "192.168.1.1",                      False),
    ("Interface",  "interface",  "eth0",                              False),
    ("Wordlist",   "wordlist",   "/usr/share/wordlists/rockyou.txt",  False),
    ("Output dir", "output_dir", "/tmp",                              False),
]


def _load_settings():
    s = {}
    try:
        with open(SETTINGS_FILE) as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    s[k.strip()] = v.strip()
    except Exception:
        pass
    return s


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Charger les valeurs persistées — sinon les defaults
        saved = _load_settings()
        self._values = {key: saved.get(key, default) for _, key, default, _ in FIELDS}
        self._btns = {}

        root = BoxLayout(orientation="vertical", spacing=4)

        # ── Header ───────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=52, padding=(8, 6), spacing=8)
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda i, v: setattr(rect, "pos", v),
                    size=lambda i, v: setattr(rect, "size", v))

        btn_back = Button(
            text="<", font_size="22sp",
            size_hint=(None, None), size=(50, 40),
            background_color=(0.2, 0.2, 0.2, 1),
        )
        btn_back.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))
        header.add_widget(btn_back)
        header.add_widget(Label(
            text="[b]Settings[/b]", markup=True,
            font_size="18sp", color=(0.2, 0.8, 0.2, 1),
            halign="left", valign="middle",
        ))

        # ── Champs (valeurs depuis settings.conf au démarrage) ────────────────
        fields_box = GridLayout(
            cols=2, spacing=3, padding=(10, 6),
            size_hint_y=None, height=len(FIELDS) * 56,
        )

        for label_txt, key, default, pwd in FIELDS:
            fields_box.add_widget(Label(
                text=label_txt, font_size="13sp",
                size_hint_y=None, height=52,
                halign="right", valign="middle",
                color=(0.7, 0.7, 0.7, 1),
            ))

            def _make_confirm(k):
                def confirm(val):
                    self._values[k] = val
                return confirm

            current_val = self._values[key]
            btn = make_field_button(label_txt, current_val, _make_confirm(key),
                                    height=52, password=pwd, hint=default)
            self._btns[key] = btn
            fields_box.add_widget(btn)

        # ── Sauvegarder ───────────────────────────────────────────────────────
        btn_save = Button(
            text="Save", font_size="15sp",
            size_hint_y=None, height=50,
            background_color=(0.10, 0.45, 0.10, 1),
            background_normal="",
        )
        btn_save.bind(on_press=self._save)

        root.add_widget(header)
        root.add_widget(fields_box)
        root.add_widget(btn_save)
        self.add_widget(root)

    def _save(self, *args):
        os.makedirs("/etc/adnrpi-hackpad", exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            for _, key, _, _ in FIELDS:
                f.write(f"{key}={self._values[key]}\n")
            f.flush()
            os.fsync(f.fileno())   # force écriture disque — survit à une coupure
