"""
Oscilloscope screen — simulation + Pico USB
Standalone : python oscilloscope.py
HackPad    : importer OscilloscopeScreen
"""
import math
import random

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock

# ── Palette ─────────────────────────────────────────────────────────────────
_BG        = (0.04, 0.06, 0.04, 1)
_GRID_MIN  = (0.14, 0.22, 0.14, 1)
_GRID_AX   = (0.28, 0.42, 0.28, 1)
_WAVE      = (0.12, 0.95, 0.12, 1)
_TRIG      = (0.95, 0.72, 0.08, 1)
_PANEL_BG  = (0.06, 0.06, 0.06, 1)
_BAR_BG    = (0.04, 0.04, 0.04, 1)
_MEAS      = (0.95, 0.90, 0.25, 1)


class WaveCanvas(Widget):
    """Dessine grille + signal + ligne trigger."""

    DIVS_X = 10
    DIVS_Y = 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.samples   = []
        self.volts_div = 1.0
        self.trig_v    = 0.0
        self.bind(size=self._redraw, pos=self._redraw)

    def update(self, samples):
        self.samples = samples
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        w, h = self.size
        x0, y0 = self.pos
        if w < 10 or h < 10:
            return
        with self.canvas:
            self._bg(x0, y0, w, h)
            self._grid(x0, y0, w, h)
            self._trigger(x0, y0, w, h)
            self._wave(x0, y0, w, h)

    def _bg(self, x0, y0, w, h):
        Color(*_BG)
        Rectangle(pos=(x0, y0), size=(w, h))

    def _grid(self, x0, y0, w, h):
        Color(*_GRID_MIN)
        for i in range(self.DIVS_X + 1):
            px = x0 + i * w / self.DIVS_X
            Line(points=[px, y0, px, y0 + h], width=1)
        for i in range(self.DIVS_Y + 1):
            py = y0 + i * h / self.DIVS_Y
            Line(points=[x0, py, x0 + w, py], width=1)
        Color(*_GRID_AX)
        cx, cy = x0 + w / 2, y0 + h / 2
        Line(points=[cx, y0, cx, y0 + h], width=1.5)
        Line(points=[x0, cy, x0 + w, cy], width=1.5)

    def _trigger(self, x0, y0, w, h):
        Color(*_TRIG)
        scale = h / (self.volts_div * self.DIVS_Y)
        cy = y0 + h / 2 + self.trig_v * scale
        cy = max(y0 + 1, min(y0 + h - 1, cy))
        Line(points=[x0, cy, x0 + w, cy], width=1,
             dash_offset=4, dash_length=10)
        # petit triangle de trigger à gauche
        Line(points=[x0 + 6, cy, x0 + 1, cy + 5, x0 + 1, cy - 5, x0 + 6, cy],
             width=1)

    def _wave(self, x0, y0, w, h):
        if len(self.samples) < 2:
            return
        Color(*_WAVE)
        scale = h / (self.volts_div * self.DIVS_Y)
        cy = y0 + h / 2
        n = len(self.samples)
        pts = []
        for i, v in enumerate(self.samples):
            px = x0 + i * w / (n - 1)
            py = cy + v * scale
            pts.extend([px, py])
        Line(points=pts, width=1.5)


# ── Écran principal ──────────────────────────────────────────────────────────

class OscilloscopeScreen(Screen):

    _TIMEBASES  = ["0.1 ms", "0.2 ms", "0.5 ms", "1 ms",
                   "2 ms",   "5 ms",   "10 ms",  "20 ms"]
    _VOLTS_DIVS = ["0.1 V", "0.2 V", "0.5 V",
                   "1 V",   "2 V",   "5 V",   "10 V"]
    _WAVEFORMS  = ["Sine", "Square", "Triangle", "Sawtooth"]
    _FREQS      = [("100 Hz", 100), ("500 Hz", 500), ("1 kHz", 1_000),
                   ("5 kHz", 5_000), ("10 kHz", 10_000), ("50 kHz", 50_000)]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._running     = True
        self._timebase_ms = 1.0
        self._volts_div   = 1.0
        self._sim_freq    = 1_000.0
        self._sim_wave    = "sine"
        self._build_ui()
        Clock.schedule_interval(self._tick, 1 / 30)

    # ── Construction UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        root = BoxLayout(orientation="vertical", spacing=0)
        root.add_widget(self._topbar())

        body = BoxLayout(orientation="horizontal", spacing=2)
        self._wave_canvas = WaveCanvas()
        body.add_widget(self._wave_canvas)
        body.add_widget(self._controls())

        root.add_widget(body)
        root.add_widget(self._meas_bar())
        self.add_widget(root)

    def _topbar(self):
        bar = BoxLayout(size_hint_y=None, height=44,
                        spacing=6, padding=(8, 4))
        with bar.canvas.before:
            Color(*_BAR_BG)
            r = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda i, v: setattr(r, "pos", v),
                 size=lambda i, v: setattr(r, "size", v))

        # Bouton retour (HackPad seulement)
        try:
            b = Button(text="◀", font_size="18sp",
                       size_hint=(None, None), size=(44, 36),
                       background_color=(0.2, 0.2, 0.2, 1))
            b.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))
            bar.add_widget(b)
        except AttributeError:
            pass

        bar.add_widget(Label(text="[b]Oscilloscope[/b]", markup=True,
                             font_size="17sp", color=(0.2, 0.92, 0.2, 1),
                             halign="left", valign="middle"))

        self._btn_run = Button(
            text="⏹  STOP", font_size="13sp",
            size_hint=(None, None), size=(96, 36),
            background_color=(0.65, 0.15, 0.08, 1), background_normal=""
        )
        self._btn_run.bind(on_press=self._toggle_run)
        bar.add_widget(self._btn_run)
        return bar

    def _controls(self):
        pnl = BoxLayout(orientation="vertical", size_hint_x=None, width=165,
                        spacing=6, padding=(8, 8))
        with pnl.canvas.before:
            Color(*_PANEL_BG)
            r = Rectangle(pos=pnl.pos, size=pnl.size)
        pnl.bind(pos=lambda i, v: setattr(r, "pos", v),
                 size=lambda i, v: setattr(r, "size", v))

        def lbl(t):
            return Label(text=t, font_size="11sp", color=(0.55, 0.55, 0.55, 1),
                         size_hint_y=None, height=20,
                         halign="left", valign="middle")

        def spin(vals, default, cb):
            s = Spinner(text=default, values=vals, font_size="12sp",
                        size_hint_y=None, height=34,
                        background_color=(0.14, 0.14, 0.14, 1),
                        color=(0.9, 0.9, 0.9, 1))
            s.bind(text=cb)
            return s

        pnl.add_widget(lbl("⏱  Time / div"))
        pnl.add_widget(spin(self._TIMEBASES, "1 ms", self._set_tb))

        pnl.add_widget(lbl("⚡ Volts / div"))
        pnl.add_widget(spin(self._VOLTS_DIVS, "1 V", self._set_vdiv))

        pnl.add_widget(Label(text="── Simulation ──", font_size="10sp",
                             color=(0.30, 0.30, 0.30, 1),
                             size_hint_y=None, height=22))

        pnl.add_widget(lbl("Forme d'onde"))
        pnl.add_widget(spin(self._WAVEFORMS, "Sine", self._set_wave))

        pnl.add_widget(lbl("Fréquence"))
        for txt, hz in self._FREQS:
            b = Button(text=txt, font_size="12sp",
                       size_hint_y=None, height=30,
                       background_color=(0.10, 0.18, 0.10, 1),
                       background_normal="")
            b.bind(on_press=lambda _, f=hz: self._set_freq(f))
            pnl.add_widget(b)

        pnl.add_widget(Widget())
        return pnl

    def _meas_bar(self):
        bar = BoxLayout(size_hint_y=None, height=36,
                        spacing=20, padding=(12, 4))
        with bar.canvas.before:
            Color(0.04, 0.04, 0.02, 1)
            r = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=lambda i, v: setattr(r, "pos", v),
                 size=lambda i, v: setattr(r, "size", v))

        self._lbl_vpp  = Label(text="Vpp: --",     font_size="13sp", color=_MEAS)
        self._lbl_freq = Label(text="Freq: --",    font_size="13sp", color=_MEAS)
        self._lbl_per  = Label(text="Période: --", font_size="13sp", color=_MEAS)
        self._lbl_dc   = Label(text="DC: --",      font_size="13sp", color=_MEAS)
        for l in (self._lbl_vpp, self._lbl_freq, self._lbl_per, self._lbl_dc):
            bar.add_widget(l)
        return bar

    # ── Callbacks ────────────────────────────────────────────────────────────

    def _toggle_run(self, *_):
        self._running = not self._running
        if self._running:
            self._btn_run.text = "⏹  STOP"
            self._btn_run.background_color = (0.65, 0.15, 0.08, 1)
        else:
            self._btn_run.text = "▶  RUN"
            self._btn_run.background_color = (0.10, 0.48, 0.10, 1)

    def _set_tb(self, _, text):
        self._timebase_ms = float(text.split()[0])

    def _set_vdiv(self, _, text):
        self._volts_div = float(text.split()[0])
        self._wave_canvas.volts_div = self._volts_div

    def _set_wave(self, _, text):
        self._sim_wave = text.lower()

    def _set_freq(self, hz):
        self._sim_freq = float(hz)

    # ── Boucle d'acquisition simulée ─────────────────────────────────────────

    def _tick(self, dt):
        if not self._running:
            return
        samples = self._simulate(512)
        self._wave_canvas.update(samples)
        self._update_meas(samples)

    def _simulate(self, n):
        window_s = self._timebase_ms * self._wave_canvas.DIVS_X / 1000
        dt = window_s / n
        T  = 1.0 / self._sim_freq
        amp = 1.5
        out = []
        for i in range(n):
            phase = (i * dt / T) % 1.0
            if self._sim_wave == "sine":
                v = amp * math.sin(2 * math.pi * phase)
            elif self._sim_wave == "square":
                v = amp * (1.0 if phase < 0.5 else -1.0)
            elif self._sim_wave == "triangle":
                v = amp * (4 * phase - 1 if phase < 0.5 else 3 - 4 * phase)
            else:  # sawtooth
                v = amp * (2 * phase - 1)
            out.append(v + random.gauss(0, 0.018))
        return out

    def _update_meas(self, s):
        vpp  = max(s) - min(s)
        dc   = sum(s) / len(s)
        freq = self._sim_freq
        per  = 1e6 / freq  # µs
        self._lbl_vpp.text  = f"Vpp: {vpp:.2f} V"
        self._lbl_dc.text   = f"DC: {dc:+.3f} V"
        if freq >= 1000:
            self._lbl_freq.text = f"Freq: {freq/1000:.1f} kHz"
        else:
            self._lbl_freq.text = f"Freq: {freq:.0f} Hz"
        if per >= 1000:
            self._lbl_per.text = f"T: {per/1000:.2f} ms"
        else:
            self._lbl_per.text = f"T: {per:.1f} µs"


# ── Runner standalone ────────────────────────────────────────────────────────

if __name__ == "__main__":
    from kivy.app import App
    from kivy.uix.screenmanager import ScreenManager
    from kivy.core.window import Window

    Window.size = (800, 480)
    Window.title = "ADNRPi — Oscilloscope preview"

    class OscApp(App):
        def build(self):
            sm = ScreenManager()
            sm.add_widget(OscilloscopeScreen(name="osc"))
            return sm

    OscApp().run()
