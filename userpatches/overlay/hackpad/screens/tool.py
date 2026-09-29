import subprocess
import threading
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle

from screens.keyboard import make_field_button

_MAX_OUTPUT_LINES = 300

# Clés de settings → clé de param qui se pré-remplit automatiquement
_SETTINGS_MAP = {
    "target":     "target_ip",
    "host":       "target_ip",
    "iface":      "interface",
    "wordlist":   "wordlist",
    "output":     "output_dir",
    "output_dir": "output_dir",
}


def _read_settings():
    s = {}
    try:
        with open("/etc/adnrpi-hackpad/settings.conf") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    k, _, v = line.partition("=")
                    s[k.strip()] = v.strip()
    except Exception:
        pass
    return s


class ToolScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._proc = None
        self._tool = None
        self._root = BoxLayout(orientation="vertical", spacing=0)
        self.add_widget(self._root)

    def load(self, tool):
        self._tool = tool
        self._proc = None
        self._root.clear_widgets()

        saved = _read_settings()

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
            background_color=(0.2, 0.2, 0.2, 1)
        )
        btn_back.bind(on_press=self._go_back)

        title_box = BoxLayout(orientation="vertical")
        title_box.add_widget(Label(
            text=f"[b]{tool['name']}[/b]", markup=True,
            font_size="16sp", color=(0.2, 0.8, 0.2, 1),
            halign="left", valign="middle", size_hint_y=0.6
        ))
        if tool.get("desc"):
            title_box.add_widget(Label(
                text=tool["desc"], font_size="11sp",
                color=(0.5, 0.5, 0.5, 1),
                halign="left", valign="middle", size_hint_y=0.4
            ))

        header.add_widget(btn_back)
        header.add_widget(title_box)

        # ── Paramètres avec pré-remplissage intelligent ───────────────────────
        self._param_values = {}
        params_layout = GridLayout(
            cols=2, size_hint_y=None, spacing=3, padding=(6, 3)
        )
        params_layout.bind(minimum_height=params_layout.setter("height"))

        for param in tool.get("params", []):
            key = param["key"]
            pwd = param.get("password", False)
            hint = param.get("hint", "")

            default = param.get("default", "")
            if not default:
                skey = _SETTINGS_MAP.get(key)
                if skey and saved.get(skey):
                    val = saved[skey]
                    if key in ("output", "output_dir"):
                        val = val.rstrip("/") + "/" + tool["name"].lower().replace(" ", "_")
                    default = val

            self._param_values[key] = default

            params_layout.add_widget(Label(
                text=param["label"], font_size="12sp",
                size_hint_y=None, height=44,
                halign="right", valign="middle",
                color=(0.7, 0.7, 0.7, 1)
            ))

            def _make_confirm(k):
                def confirm(val):
                    self._param_values[k] = val
                return confirm

            btn = make_field_button(
                param["label"], default, _make_confirm(key),
                height=44, password=pwd, hint=hint
            )
            params_layout.add_widget(btn)

        n_params = len(tool.get("params", []))
        params_scroll = ScrollView(size_hint_y=None, height=min(n_params * 48 + 6, 180))
        params_scroll.add_widget(params_layout)

        # ── Boutons RUN / STOP / CLR / RAPPORT ───────────────────────────────
        btn_row = BoxLayout(size_hint_y=None, height=48, spacing=5, padding=(6, 3))

        self._btn_run = Button(
            text=">> RUN", font_size="15sp",
            background_color=(0.10, 0.55, 0.10, 1), background_normal=""
        )
        self._btn_run.bind(on_press=self._run_tool)

        self._btn_stop = Button(
            text="[X] STOP", font_size="15sp",
            background_color=(0.55, 0.10, 0.10, 1), background_normal="",
            disabled=True
        )
        self._btn_stop.bind(on_press=self._stop_tool)

        self._btn_clear = Button(
            text="CLR", font_size="13sp",
            size_hint_x=None, width=52,
            background_color=(0.25, 0.25, 0.25, 1), background_normal=""
        )
        self._btn_clear.bind(on_press=lambda *a: setattr(self._output, "text", ""))

        self._btn_report = Button(
            text="RAPPORT", font_size="13sp",
            size_hint_x=None, width=88,
            background_color=(0.15, 0.35, 0.65, 1), background_normal="",
            disabled=True
        )
        self._btn_report.bind(on_press=self._show_report)

        btn_row.add_widget(self._btn_run)
        btn_row.add_widget(self._btn_stop)
        btn_row.add_widget(self._btn_clear)
        btn_row.add_widget(self._btn_report)

        # ── Console de sortie ────────────────────────────────────────────────
        self._output = TextInput(
            text="", readonly=True, multiline=True,
            font_name="RobotoMono-Regular", font_size="12sp",
            background_color=(0.04, 0.04, 0.04, 1),
            foreground_color=(0.2, 0.9, 0.2, 1),
        )

        self._root.add_widget(header)
        if tool.get("params"):
            self._root.add_widget(params_scroll)
        self._root.add_widget(btn_row)
        self._root.add_widget(self._output)

    # ── Exécution ─────────────────────────────────────────────────────────────

    def _run_tool(self, *args):
        if self._proc and self._proc.poll() is None:
            return
        params = dict(self._param_values)
        try:
            cmd = self._tool["build_cmd"](params)
        except Exception as e:
            self._append(f"[ERROR] {e}\n")
            return

        self._output.text = f"$ {' '.join(str(x) for x in cmd)}\n"
        self._btn_run.disabled = True
        self._btn_stop.disabled = False
        self._btn_report.disabled = True

        def run():
            try:
                self._proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1
                )
                for line in self._proc.stdout:
                    Clock.schedule_once(lambda dt, l=line: self._append(l), 0)
                self._proc.wait()
            except Exception as e:
                err = str(e)
                Clock.schedule_once(lambda dt, err=err: self._append(f"[ERROR] {err}\n"), 0)
            finally:
                Clock.schedule_once(self._on_done, 0)

        threading.Thread(target=run, daemon=True).start()

    def _stop_tool(self, *args):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            # SIGKILL si l'outil ne répond pas sous 3 secondes
            Clock.schedule_once(self._force_kill, 3)

    def _force_kill(self, dt):
        if self._proc and self._proc.poll() is None:
            self._proc.kill()

    def _on_done(self, *args):
        self._btn_run.disabled = False
        self._btn_stop.disabled = True
        self._append("\n--- done ---\n")
        # Activer RAPPORT si un analyseur existe pour cet outil
        from screens.report import ANALYZERS
        if self._tool.get("name", "").lower() in ANALYZERS:
            self._btn_report.disabled = False

    def _append(self, text):
        self._output.text += text
        # Limiter le buffer à _MAX_OUTPUT_LINES lignes
        lines = self._output.text.splitlines(True)
        if len(lines) > _MAX_OUTPUT_LINES:
            self._output.text = "".join(lines[-_MAX_OUTPUT_LINES:])
        # Scroll vers le bas
        self._output.cursor = (len(self._output.text), 0)

    def _show_report(self, *args):
        from screens.report import ReportPopup
        popup = ReportPopup(
            tool_name=self._tool.get("name", ""),
            output_text=self._output.text
        )
        popup.open()

    def _go_back(self, *args):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.manager.current = "category"
