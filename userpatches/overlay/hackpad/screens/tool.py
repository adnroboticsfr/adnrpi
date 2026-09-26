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
        btn_back.bind(on_press=self._go_back)

        header.add_widget(btn_back)
        header.add_widget(Label(
            text=f"[b]{tool['name']}[/b]",
            markup=True, font_size="17sp",
            color=(0.2, 0.8, 0.2, 1), halign="left", valign="middle"
        ))

        # ── Parameters ───────────────────────────────────────────────────────
        self._param_inputs = {}
        params_layout = GridLayout(
            cols=2, size_hint_y=None, spacing=4, padding=(6, 4)
        )
        params_layout.bind(minimum_height=params_layout.setter("height"))

        for param in tool.get("params", []):
            params_layout.add_widget(Label(
                text=param["label"], font_size="13sp",
                size_hint_y=None, height=36,
                halign="right", valign="middle",
                color=(0.7, 0.7, 0.7, 1)
            ))
            ti = TextInput(
                text=param.get("default", ""),
                multiline=False, font_size="13sp",
                size_hint_y=None, height=36,
                background_color=(0.15, 0.15, 0.15, 1),
                foreground_color=(1, 1, 1, 1),
                hint_text=param.get("hint", ""),
                password=param.get("password", False)
            )
            self._param_inputs[param["key"]] = ti
            params_layout.add_widget(ti)

        params_scroll = ScrollView(size_hint_y=None, height=min(len(tool.get("params", [])) * 42 + 8, 160))
        params_scroll.add_widget(params_layout)

        # ── Run / Stop buttons ────────────────────────────────────────────────
        btn_row = BoxLayout(size_hint_y=None, height=50, spacing=6, padding=(6, 4))

        self._btn_run = Button(
            text="▶  RUN",
            font_size="16sp",
            background_color=(0.10, 0.55, 0.10, 1),
            background_normal=""
        )
        self._btn_run.bind(on_press=self._run_tool)

        self._btn_stop = Button(
            text="■  STOP",
            font_size="16sp",
            background_color=(0.55, 0.10, 0.10, 1),
            background_normal="",
            disabled=True
        )
        self._btn_stop.bind(on_press=self._stop_tool)

        self._btn_clear = Button(
            text="🗑",
            font_size="18sp",
            size_hint_x=None, width=50,
            background_color=(0.25, 0.25, 0.25, 1),
            background_normal=""
        )
        self._btn_clear.bind(on_press=lambda *a: setattr(self._output, "text", ""))

        btn_row.add_widget(self._btn_run)
        btn_row.add_widget(self._btn_stop)
        btn_row.add_widget(self._btn_clear)

        # ── Output console ────────────────────────────────────────────────────
        self._output = TextInput(
            text="",
            readonly=True,
            multiline=True,
            font_name="RobotoMono-Regular",
            font_size="12sp",
            background_color=(0.04, 0.04, 0.04, 1),
            foreground_color=(0.2, 0.9, 0.2, 1),
        )

        self._root.add_widget(header)
        if tool.get("params"):
            self._root.add_widget(params_scroll)
        self._root.add_widget(btn_row)
        self._root.add_widget(self._output)

    # ── Tool execution ────────────────────────────────────────────────────────

    def _run_tool(self, *args):
        if self._proc and self._proc.poll() is None:
            return
        params = {k: v.text.strip() for k, v in self._param_inputs.items()}
        try:
            cmd = self._tool["build_cmd"](params)
        except Exception as e:
            self._append(f"[ERROR] {e}\n")
            return

        self._output.text = f"$ {' '.join(cmd)}\n"
        self._btn_run.disabled = True
        self._btn_stop.disabled = False

        def run():
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
                )
                for line in self._proc.stdout:
                    Clock.schedule_once(lambda dt, l=line: self._append(l), 0)
                self._proc.wait()
            except Exception as e:
                Clock.schedule_once(lambda dt: self._append(f"[ERROR] {e}\n"), 0)
            finally:
                Clock.schedule_once(self._on_done, 0)

        threading.Thread(target=run, daemon=True).start()

    def _stop_tool(self, *args):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()

    def _on_done(self, *args):
        self._btn_run.disabled = False
        self._btn_stop.disabled = True
        self._append("\n[done]\n")

    def _append(self, text):
        self._output.text += text
        self._output.cursor = (0, len(self._output._lines) - 1)

    def _go_back(self, *args):
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
        self.manager.current = "category"
