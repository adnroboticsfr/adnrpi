import subprocess
import os
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle


def _current_target():
    try:
        out = subprocess.check_output(["systemctl", "get-default"], text=True).strip()
        return out
    except Exception:
        return "unknown"


class ModeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", spacing=0)

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
            text="[b]Display Mode[/b]", markup=True,
            font_size="18sp", color=(0.2, 0.8, 0.2, 1),
            halign="left", valign="middle"
        ))

        # ── Current mode ──────────────────────────────────────────────────────
        target = _current_target()
        mode_txt = "🖥  Desktop (graphical)" if "graphical" in target else "⌨  Server (console)"
        self._status = Label(
            text=f"Current mode: {mode_txt}",
            font_size="15sp", color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None, height=60, halign="center"
        )

        # ── Mode buttons ──────────────────────────────────────────────────────
        body = BoxLayout(orientation="vertical", spacing=16, padding=(20, 20))

        btn_server = Button(
            text="⌨  Server Mode\n[size=12]Kivy on framebuffer — no X11 needed[/size]",
            markup=True, font_size="16sp",
            size_hint_y=None, height=90,
            background_color=(0.10, 0.35, 0.10, 1), background_normal=""
        )
        btn_server.bind(on_press=self._set_server)

        btn_desktop = Button(
            text="🖥  Desktop Mode\n[size=12]XFCE + HackPad in X11 window[/size]",
            markup=True, font_size="16sp",
            size_hint_y=None, height=90,
            background_color=(0.10, 0.25, 0.50, 1), background_normal=""
        )
        btn_desktop.bind(on_press=self._set_desktop)

        self._feedback = Label(
            text="", font_size="13sp",
            color=(0.9, 0.7, 0.2, 1),
            size_hint_y=None, height=50,
            halign="center"
        )

        body.add_widget(self._status)
        body.add_widget(btn_server)
        body.add_widget(btn_desktop)
        body.add_widget(self._feedback)

        root.add_widget(header)
        root.add_widget(body)
        self.add_widget(root)

    def _set_server(self, *args):
        self._switch_mode("multi-user.target")

    def _set_desktop(self, *args):
        self._switch_mode("graphical.target")

    def _switch_mode(self, target):
        try:
            subprocess.run(["systemctl", "set-default", target], check=True)
            self._feedback.text = f"Mode set to {target}\nRebooting in 5 seconds..."
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: subprocess.run(["systemctl", "reboot"]), 5)
        except Exception as e:
            self._feedback.text = f"Error: {e}"
