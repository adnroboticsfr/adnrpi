"""
Écran oscilloscope Kivy — 800×480, tactile.

Layout :
  Header  52px  — titre, channel, RUN/STOP
  Scope  320px  — grille 10×8 + waveform canvas
  Mesures 48px  — Vpp / Vrms / Freq / Période
  Ctrls   60px  — T/div [-][val][+]  V/div [-][val][+]  Trig [-][val][+]
"""
import numpy as np
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock

# ── Constantes ────────────────────────────────────────────────────────────────

TIMEBASES_MS = [0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]  # ms / division
VOLT_DIVS    = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0]             # unités norm. / division
GRID_X = 10    # divisions horizontales
GRID_Y = 8     # divisions verticales

_COL_BG      = (0.04, 0.04, 0.04, 1)
_COL_GRID    = (0.12, 0.12, 0.12, 1)
_COL_CENTER  = (0.22, 0.22, 0.22, 1)
_COL_WAVE    = (0.15, 0.90, 0.15, 1)
_COL_TRIG    = (0.95, 0.80, 0.05, 1)
_COL_HEADER  = (0.05, 0.05, 0.05, 1)
_COL_MEAS    = (0.06, 0.06, 0.06, 1)
_COL_CTRL    = (0.04, 0.04, 0.07, 1)


# ── Widget waveform ───────────────────────────────────────────────────────────

class WaveformWidget(Widget):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._samples       = []
        self._timebase_idx  = 3    # 5 ms/div
        self._voltdiv_idx   = 4    # 1.0 unit/div
        self._trigger_level = 0.0
        self._running       = True
        self._sr            = 44100
        self.bind(size=self._redraw, pos=self._redraw)

    # ── Propriétés publiques ──────────────────────────────────────────────────

    @property
    def timebase_ms(self):
        return TIMEBASES_MS[self._timebase_idx]

    @property
    def volt_div(self):
        return VOLT_DIVS[self._voltdiv_idx]

    @property
    def trigger_level(self):
        return self._trigger_level

    def set_sample_rate(self, sr):
        self._sr = sr

    # ── Contrôles ─────────────────────────────────────────────────────────────

    def timebase_up(self):
        self._timebase_idx = min(self._timebase_idx + 1, len(TIMEBASES_MS) - 1)

    def timebase_down(self):
        self._timebase_idx = max(self._timebase_idx - 1, 0)

    def voltdiv_up(self):
        self._voltdiv_idx = min(self._voltdiv_idx + 1, len(VOLT_DIVS) - 1)

    def voltdiv_down(self):
        self._voltdiv_idx = max(self._voltdiv_idx - 1, 0)

    def trigger_up(self):
        self._trigger_level = min(1.0, self._trigger_level + 0.05)

    def trigger_down(self):
        self._trigger_level = max(-1.0, self._trigger_level - 0.05)

    # ── Rendu ────────────────────────────────────────────────────────────────

    def update(self, samples):
        self._samples = samples
        if self._running:
            self._redraw()

    def _redraw(self, *args):
        self.canvas.clear()
        w, h  = self.width, self.height
        x0, y0 = self.x, self.y
        if w == 0 or h == 0:
            return

        with self.canvas:
            # Fond
            Color(*_COL_BG)
            Rectangle(pos=(x0, y0), size=(w, h))

            # Grille mineure
            Color(*_COL_GRID)
            for i in range(GRID_X + 1):
                xi = x0 + i * w / GRID_X
                Line(points=[xi, y0, xi, y0 + h], width=1)
            for i in range(GRID_Y + 1):
                yi = y0 + i * h / GRID_Y
                Line(points=[x0, yi, x0 + w, yi], width=1)

            # Axes centraux
            Color(*_COL_CENTER)
            Line(points=[x0, y0 + h/2, x0 + w, y0 + h/2], width=1.4)
            Line(points=[x0 + w/2, y0, x0 + w/2, y0 + h], width=1.4)

            # Ligne de trigger
            Color(*_COL_TRIG)
            scale_y = (h / GRID_Y) / self.volt_div
            ty = y0 + h/2 + self._trigger_level * scale_y
            ty = max(y0 + 1, min(y0 + h - 1, ty))
            Line(points=[x0, ty, x0 + w, ty], dash_length=8, dash_offset=4, width=1)
            # Petit marqueur triangulaire gauche
            Line(points=[x0, ty, x0 + 8, ty + 5, x0 + 8, ty - 5, x0, ty], width=1)

            # Waveform
            if self._samples and len(self._samples) > 4:
                self._draw_wave(x0, y0, w, h, scale_y)

    def _draw_wave(self, x0, y0, w, h, scale_y):
        smp = np.array(self._samples, dtype=np.float32)

        # Nombre de samples à afficher pour le timebase courant
        n_show = int(self.timebase_ms * 1e-3 * self._sr * GRID_X)
        n_show = max(10, min(n_show, len(smp)))
        smp = smp[-n_show:]

        # Décimation si plus de 800 samples (1 par pixel)
        n = len(smp)
        n_px = int(w)
        if n > n_px:
            step = n / n_px
            idxs = [int(i * step) for i in range(n_px)]
            smp = smp[idxs]
            n = n_px

        cy = y0 + h / 2
        pts = []
        for i, v in enumerate(smp):
            xi = x0 + i * w / (n - 1)
            yi = cy + float(v) * scale_y
            yi = max(y0 + 1, min(y0 + h - 1, yi))
            pts += [xi, yi]

        Color(*_COL_WAVE)
        Line(points=pts, width=1.5)


# ── Écran principal ───────────────────────────────────────────────────────────

class ScopeScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._capture  = None
        self._channel  = "---"
        self._running  = True

        root = BoxLayout(orientation="vertical", spacing=0)

        root.add_widget(self._make_header())
        self._wave = WaveformWidget()
        root.add_widget(self._wave)
        root.add_widget(self._make_meas_bar())
        root.add_widget(self._make_controls())
        self.add_widget(root)

        self._init_capture()
        Clock.schedule_interval(self._tick, 1 / 25)   # 25 FPS

    # ── Construction UI ───────────────────────────────────────────────────────

    def _make_header(self):
        h = BoxLayout(size_hint_y=None, height=52, padding=(8, 4), spacing=8)
        with h.canvas.before:
            Color(*_COL_HEADER)
            r = Rectangle()
        h.bind(pos=lambda w, v: setattr(r, "pos", v),
               size=lambda w, v: setattr(r, "size", v))

        btn_back = Button(text="<", font_size="20sp",
                          size_hint=(None, 1), width=44,
                          background_color=(0.2, 0.2, 0.2, 1),
                          background_normal="")
        btn_back.bind(on_press=self._go_back)

        self._lbl_title = Label(
            text="[b]ADNRPi SCOPE[/b]", markup=True,
            font_size="16sp", color=(0.2, 0.9, 1.0, 1),
            halign="left", valign="middle"
        )
        self._lbl_ch = Label(
            text="CH: ---", font_size="12sp",
            color=(0.6, 0.6, 0.6, 1),
            size_hint=(None, 1), width=74, halign="center"
        )
        self._btn_run = Button(
            text="■ STOP", font_size="13sp",
            size_hint=(None, 1), width=80,
            background_color=(0.55, 0.10, 0.10, 1), background_normal=""
        )
        self._btn_run.bind(on_press=self._toggle_run)

        h.add_widget(btn_back)
        h.add_widget(self._lbl_title)
        h.add_widget(self._lbl_ch)
        h.add_widget(self._btn_run)
        return h

    def _make_meas_bar(self):
        bar = BoxLayout(size_hint_y=None, height=44, padding=(6, 2), spacing=4)
        with bar.canvas.before:
            Color(*_COL_MEAS)
            r = Rectangle()
        bar.bind(pos=lambda w, v: setattr(r, "pos", v),
                 size=lambda w, v: setattr(r, "size", v))

        kw = dict(font_size="12sp", color=(0.75, 0.95, 0.75, 1), halign="center")
        self._m_vpp  = Label(text="Vpp: ---",  **kw)
        self._m_vrms = Label(text="Vrms: ---", **kw)
        self._m_freq = Label(text="Freq: ---", **kw)
        self._m_per  = Label(text="T: ---",    **kw)
        for l in (self._m_vpp, self._m_vrms, self._m_freq, self._m_per):
            bar.add_widget(l)
        return bar

    def _make_controls(self):
        box = BoxLayout(size_hint_y=None, height=60, spacing=6, padding=(6, 4))
        with box.canvas.before:
            Color(*_COL_CTRL)
            r = Rectangle()
        box.bind(pos=lambda w, v: setattr(r, "pos", v),
                 size=lambda w, v: setattr(r, "size", v))

        box.add_widget(self._ctrl_group(
            "T/div",
            self._wave.timebase_down, self._wave.timebase_up,
            lambda: (f"{self._wave.timebase_ms}ms"
                     if self._wave.timebase_ms >= 1
                     else f"{self._wave.timebase_ms*1000:.0f}µs")
        ))
        box.add_widget(self._ctrl_group(
            "V/div",
            self._wave.voltdiv_down, self._wave.voltdiv_up,
            lambda: f"{self._wave.volt_div:.2f}"
        ))
        box.add_widget(self._ctrl_group(
            "Trig",
            self._wave.trigger_down, self._wave.trigger_up,
            lambda: f"{self._wave.trigger_level:+.2f}"
        ))
        return box

    def _ctrl_group(self, title, minus_cb, plus_cb, val_fn):
        col = BoxLayout(orientation="vertical", spacing=2)
        col.add_widget(Label(text=title, font_size="10sp",
                             color=(0.45, 0.45, 0.45, 1),
                             size_hint_y=None, height=14))
        row = BoxLayout(spacing=3)
        b_m = Button(text="–", font_size="16sp", size_hint=(None, 1), width=36,
                     background_color=(0.14, 0.14, 0.20, 1), background_normal="")
        val = Label(font_size="12sp", color=(0.9, 0.9, 0.9, 1), text=val_fn())
        b_p = Button(text="+", font_size="16sp", size_hint=(None, 1), width=36,
                     background_color=(0.14, 0.14, 0.20, 1), background_normal="")

        def _dn(*a):
            minus_cb()
            val.text = val_fn()
        def _up(*a):
            plus_cb()
            val.text = val_fn()

        b_m.bind(on_press=_dn)
        b_p.bind(on_press=_up)
        row.add_widget(b_m)
        row.add_widget(val)
        row.add_widget(b_p)
        col.add_widget(row)
        return col

    # ── Capture ───────────────────────────────────────────────────────────────

    def _init_capture(self):
        try:
            from audio_capture import make_capture
            self._capture, ch = make_capture()
            self._channel = ch
        except Exception as e:
            try:
                from audio_capture import DummyCapture
                self._capture = DummyCapture()
                self._capture.start()
                self._channel = "SIM"
            except Exception:
                self._capture = None
                self._channel = "ERR"
        self._lbl_ch.text = f"CH: {self._channel}"
        if self._capture:
            self._wave.set_sample_rate(self._capture.sample_rate)

    # ── Boucle de mise à jour ─────────────────────────────────────────────────

    def _tick(self, dt):
        if not self._capture:
            return

        tb_ms = self._wave.timebase_ms
        n_need = int(tb_ms * 1e-3 * self._capture.sample_rate * GRID_X) + 512
        n_need = max(2048, min(n_need, self._capture.sample_rate * 2))

        samples = self._capture.get_samples(n_need)

        if self._running:
            self._wave.update(samples)
            self._update_meas(samples)

    def _update_meas(self, samples):
        if len(samples) < 20:
            return
        smp = np.array(samples, dtype=np.float32)
        vpp  = float(np.max(smp) - np.min(smp))
        vrms = float(np.sqrt(np.mean(smp ** 2)))
        freq, period = self._detect_freq(smp)

        self._m_vpp.text  = f"Vpp: {vpp:.3f}"
        self._m_vrms.text = f"Vrms: {vrms:.3f}"
        if freq:
            f_txt = f"{freq:.1f}Hz" if freq < 1000 else f"{freq/1000:.2f}kHz"
            p_txt = f"{period*1000:.2f}ms" if period > 0.001 else f"{period*1e6:.1f}µs"
            self._m_freq.text = f"Freq: {f_txt}"
            self._m_per.text  = f"T: {p_txt}"
        else:
            self._m_freq.text = "Freq: ---"
            self._m_per.text  = "T: ---"

    def _detect_freq(self, smp):
        """Détection de fréquence par passages à zéro (montants)."""
        try:
            s = smp - np.mean(smp)
            # Crossings : négatif→positif
            pos = np.where((s[:-1] < 0) & (s[1:] >= 0))[0]
            if len(pos) < 2:
                return None, None
            periods_smp = np.diff(pos)
            avg = float(np.median(periods_smp))
            if avg < 2:
                return None, None
            sr = self._capture.sample_rate
            freq = sr / avg
            if 1.0 <= freq <= sr / 2:
                return freq, avg / sr
        except Exception:
            pass
        return None, None

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle_run(self, *args):
        self._running = not self._running
        self._wave._running = self._running
        if self._running:
            self._btn_run.text = "■ STOP"
            self._btn_run.background_color = (0.55, 0.10, 0.10, 1)
        else:
            self._btn_run.text = "▶ RUN"
            self._btn_run.background_color = (0.10, 0.55, 0.10, 1)

    def _go_back(self, *args):
        from kivy.app import App
        App.get_running_app().stop()

    def on_leave(self, *args):
        Clock.unschedule(self._tick)
        if self._capture:
            self._capture.stop()
