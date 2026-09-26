import subprocess
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle

SETTINGS_FILE = "/etc/adnrpi-hackpad/settings.conf"


def _get_ifaces():
    try:
        out = subprocess.check_output(["ip", "-o", "link", "show"], text=True)
        ifaces = [line.split(":")[1].strip() for line in out.splitlines() if "lo" not in line]
        return ", ".join(ifaces)
    except Exception:
        return "eth0, wlan0"


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical")

        # ── Header ───────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=52, padding=(8, 6), spacing=8)
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda i, v: setattr(rect, "pos", v),
                    size=lambda i, v: setattr(rect, "size", v))

        btn_back = Button(
            text="◀", font_size="20sp",
            size_hint=(None, None), size=(50, 40),
            background_color=(0.2, 0.2, 0.2, 1)
        )
        btn_back.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))
        header.add_widget(btn_back)
        header.add_widget(Label(
            text="[b]Settings[/b]", markup=True,
            font_size="18sp", color=(0.2, 0.8, 0.2, 1),
            halign="left", valign="middle"
        ))

        # ── Fields ───────────────────────────────────────────────────────────
        scroll = ScrollView()
        grid = GridLayout(cols=2, spacing=6, padding=(10, 6), size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        ifaces = _get_ifaces()

        self._fields = [
            ("Default target IP", "target_ip", "192.168.1.1", f"Detected interfaces: {ifaces}"),
            ("Default interface",  "interface", "eth0",        ifaces),
            ("Default wordlist",   "wordlist",  "/usr/share/wordlists/rockyou.txt", "path"),
            ("Output directory",   "output_dir","/tmp",        "where captures are saved"),
        ]

        self._inputs = {}
        for label_txt, key, default, hint in self._fields:
            grid.add_widget(Label(
                text=label_txt, font_size="13sp",
                size_hint_y=None, height=40,
                halign="right", valign="middle",
                color=(0.7, 0.7, 0.7, 1)
            ))
            ti = TextInput(
                text=default, multiline=False, font_size="13sp",
                size_hint_y=None, height=40,
                background_color=(0.15, 0.15, 0.15, 1),
                foreground_color=(1, 1, 1, 1),
                hint_text=hint
            )
            self._inputs[key] = ti
            grid.add_widget(ti)

        scroll.add_widget(grid)

        # ── System info ───────────────────────────────────────────────────────
        info = self._get_sysinfo()
        info_label = Label(
            text=info, font_size="12sp",
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None, height=80,
            halign="left", valign="top",
            padding=(10, 4)
        )
        info_label.bind(size=info_label.setter("text_size"))

        # ── Save button ───────────────────────────────────────────────────────
        btn_save = Button(
            text="💾  Save Settings",
            font_size="15sp", size_hint_y=None, height=52,
            background_color=(0.10, 0.45, 0.10, 1), background_normal=""
        )
        btn_save.bind(on_press=self._save)

        root.add_widget(header)
        root.add_widget(scroll)
        root.add_widget(info_label)
        root.add_widget(btn_save)
        self.add_widget(root)

    def _save(self, *args):
        import os
        os.makedirs("/etc/adnrpi-hackpad", exist_ok=True)
        with open(SETTINGS_FILE, "w") as f:
            for _, key, _, _ in self._fields:
                f.write(f"{key}={self._inputs[key].text}\n")

    def _get_sysinfo(self):
        lines = []
        try:
            ip = subprocess.check_output(["hostname", "-I"], text=True).strip()
            lines.append(f"IPs: {ip}")
        except Exception:
            pass
        try:
            uname = subprocess.check_output(["uname", "-r"], text=True).strip()
            lines.append(f"Kernel: {uname}")
        except Exception:
            pass
        return "  |  ".join(lines)
