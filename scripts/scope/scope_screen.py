"""
ADNRPi Scope — Interface complète 800×480 (Scoppy-style)

Layout :
  ┌─────────────────────────────────────┬────────────┐  50px
  │  CH1:MIC  AUTO  ↑RISE  5ms  1V  DC │  [■ STOP]  │
  ├─────────────────────────────────────┤            │
  │                                     │  T/div     │
  │        Waveform 580×362            │  V/div     │  362px
  │  ← H1 H2 (curseurs tension) →      │  Trigger   │
  │  ↕ V1 V2 (curseurs temps)  ↕       │  Pente     │
  │                                     │  Mode      │
  ├─────────────────────────────────────┤  Couplage  │
  │ Vmax  Vmin  Vpp   Vrms  Mean        │  Options   │  68px
  │ Freq  Period Duty  ΔV   Δt          │ [Quitter]  │
  └─────────────────────────────────────┴────────────┘

Tactile + souris. Curseurs H1/H2/V1/V2 draggables.
"""
import math
import os
import numpy as np
from collections import deque
from kivy.core.window import Window
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.graphics import Color, Line, Rectangle
from kivy.clock import Clock

# ── Constantes layout ─────────────────────────────────────────────────────────

TIMEBASES_MS = [0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500]
_PINCH_STEP  = 35   # pixels de déplacement entre 2 doigts pour un step de zoom
VOLT_DIVS    = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0]
GRID_X, GRID_Y = 10, 8
GRAB_TOL = 22

# ── Détection résolution : adapte le layout automatiquement ──────────────────
# HACKPAD_W/H positionné par launch.sh ; sinon Window.width après Config.

_SCR_W = int(os.environ.get("HACKPAD_W", Window.width  or 800))
_SCR_H = int(os.environ.get("HACKPAD_H", Window.height or 480))
_COMPACT = (_SCR_W <= 800)      # True = écran tactile 800×480

if _COMPACT:
    PANEL_W  = 160
    HEADER_H = 46
    MEAS_H   = 54
    FS_HDR_CH   = "15sp"
    FS_HDR_INFO = "13sp"
    FS_HDR_STOP = "14sp"
    FS_TITLE    = "12sp"
    FS_VALUE    = "16sp"
    FS_PM       = "20sp"
    FS_TOGGLE   = "13sp"
    FS_MEAS     = "12sp"
    FS_QUIT     = "13sp"
    _PM_H       = 30
    _TOG_H      = 28
else:
    PANEL_W  = 260
    HEADER_H = 56
    MEAS_H   = 72
    FS_HDR_CH   = "20sp"
    FS_HDR_INFO = "17sp"
    FS_HDR_STOP = "17sp"
    FS_TITLE    = "15sp"
    FS_VALUE    = "22sp"
    FS_PM       = "26sp"
    FS_TOGGLE   = "17sp"
    FS_MEAS     = "16sp"
    FS_QUIT     = "16sp"
    _PM_H       = 50
    _TOG_H      = 44

# ── Palette (chargée depuis settings au démarrage) ────────────────────────────

import settings_manager as _SM
from strings import t as _t
_SM.load()
_P = _SM.get_palette()

C_BG    = _P["BG"]
C_GRID  = _P["GRID"]
C_AXIS  = _P["AXIS"]
C_WAVE  = _P["WAVE"]
C_HDR   = _P["HDR"]
C_MEAS  = _P["MEAS"]
C_PANEL = _P["PANEL"]
C_TEXT  = _P["TEXT"]

C_TRIG  = (1.0,  0.82, 0.0,  1)
C_H1    = (1.0,  0.90, 0.1,  1)
C_H2    = (0.1,  0.90, 1.0,  1)
C_V1    = (1.0,  0.30, 0.30, 1)
C_V2    = (0.5,  1.0,  0.30, 1)
C_YEL   = (1.0,  0.95, 0.3,  1)
C_GRN   = (0.2,  1.0,  0.4,  1)
C_CYN   = (0.2,  0.85, 1.0,  1)
C_BTN   = (0.20, 0.20, 0.20, 1)
C_ON    = (0.18, 0.50, 0.18, 1)

# ── Helpers format ────────────────────────────────────────────────────────────

def _fmt_t(ms):
    if ms < 1:    return f"{ms*1000:.0f}us"
    if ms < 1000: return f"{ms:g}ms"
    return f"{ms/1000:.1f}s"

def _fmt_v(v):
    if abs(v) < 0.1: return f"{v*1000:.0f}mV"
    return f"{v:g}V"

def _fmt_freq(hz):
    if hz <= 0:    return "---"
    if hz >= 1e6:  return f"{hz/1e6:.2f}MHz"
    if hz >= 1000: return f"{hz/1000:.2f}kHz"
    return f"{hz:.1f}Hz"

def _fmt_time(s):
    if s == 0:         return "---"
    if abs(s) < 1e-6:  return f"{s*1e9:.1f}ns"
    if abs(s) < 1e-3:  return f"{s*1e6:.1f}us"
    if abs(s) < 1:     return f"{s*1000:.2f}ms"
    return f"{s:.3f}s"

def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *a: setattr(rect, "pos", widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )

# ── WaveformWidget ────────────────────────────────────────────────────────────

class WaveformWidget(Widget):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._samples  = []
        self._t_idx    = TIMEBASES_MS.index(5)
        self._v_idx    = VOLT_DIVS.index(1.0)
        self._trig_lvl = 0.0
        self._slope    = "RISE"
        self._running  = True
        self._inverted = False
        self._sr       = 44100
        self._hpf_x = self._hpf_y = 0.0
        self._cursors = False
        self._cur = {"H1": None, "H2": None, "V1": None, "V2": None}
        self._grabbed = None
        self.m = {}
        self._fft_mode     = False
        self._persist_mode = False
        self._sweeps       = deque(maxlen=8)
        self._v_offset    = 0.0    # offset vertical CH1 en volts
        self._frozen_buf  = None   # buffer gelé quand STOP
        self._buf_offset  = 0      # samples depuis la fin du frozen_buf
        self._adj_cb      = None   # callback ScopeScreen._sync_labels
        self._gesture_dir = None   # None | "H" | "V"
        self._gesture_x0  = 0.0
        self._gesture_sx  = 0.0
        self._gesture_zone = "R"   # "L" (v_offset) | "R" (trigger)
        self._drag_y0     = None
        self.bind(size=self._on_size, pos=self._on_size)

    @property
    def t_ms(self):   return TIMEBASES_MS[self._t_idx]
    @property
    def v_div(self):  return VOLT_DIVS[self._v_idx]

    def set_sr(self, sr):      self._sr = sr
    def adj_t(self, d):        self._t_idx   = max(0, min(len(TIMEBASES_MS)-1, self._t_idx+d))
    def adj_v(self, d):        self._v_idx   = max(0, min(len(VOLT_DIVS)-1,    self._v_idx+d))
    def adj_trig(self, d):     self._trig_lvl = round(self._trig_lvl + d*0.05, 3)
    def adj_voff(self, d):     self._v_offset = round(self._v_offset + d * self.v_div * 0.5, 3)
    def set_slope(self, s):    self._slope    = s
    def set_inverted(self, b): self._inverted = b
    def reset_hpf(self):       self._hpf_x = self._hpf_y = 0.0

    def freeze_buf(self, samples):
        self._frozen_buf = list(samples)
        self._buf_offset = 0

    def set_fft_mode(self, b):
        self._fft_mode = b
        if not b: self._sweeps.clear()

    def set_persist_mode(self, b):
        self._persist_mode = b
        if not b: self._sweeps.clear()

    def adj_buf_offset(self, d):
        if not self._frozen_buf: return
        n_disp = max(2, int(self.t_ms*1e-3*self._sr*GRID_X))
        step   = max(1, n_disp // 4)
        max_off = max(0, len(self._frozen_buf) - n_disp)
        self._buf_offset = max(0, min(max_off, self._buf_offset + d * step))

    def toggle_cursors(self):
        self._cursors = not self._cursors
        if self._cursors and self.width > 10:
            h, w = self.height, self.width
            cy = self.y + h / 2
            self._cur = {
                "H1": cy + h/6, "H2": cy - h/6,
                "V1": self.x + w/3, "V2": self.x + 2*w/3,
            }
        return self._cursors

    # HPF ──────────────────────────────────────────────────────────────────────

    def apply_hpf(self, samples, fc=120):
        dt = 1.0 / self._sr
        rc = 1.0 / (2 * math.pi * fc)
        alpha = rc / (rc + dt)
        out, px, py = [], self._hpf_x, self._hpf_y
        for x in samples:
            y = alpha * (py + x - px)
            out.append(y)
            px, py = x, y
        self._hpf_x, self._hpf_y = px, py
        return out

    # Trigger ──────────────────────────────────────────────────────────────────

    def _find_trigger(self, buf, n):
        lvl = self._trig_lvl
        for i in range(len(buf) - n - 1):
            if self._slope == "RISE":
                if buf[i] <= lvl < buf[i+1]: return i
            else:
                if buf[i] >= lvl > buf[i+1]: return i
        return max(0, len(buf) - n)

    # Mesures ──────────────────────────────────────────────────────────────────

    def _compute_meas(self, win):
        if len(win) < 4:
            self.m = {}
            return
        arr  = np.array(win, dtype=np.float32)
        mean = float(arr.mean())
        s    = arr - mean
        rises = np.where((s[:-1] < 0) & (s[1:] >= 0))[0]
        freq = per = 0.0
        if len(rises) >= 2:
            periods = np.diff(rises.astype(float)) / self._sr
            med = float(np.median(periods))
            if med > 0:
                freq, per = round(1.0/med, 2), med
        duty = float((arr > self._trig_lvl).mean() * 100)
        dv = dt_c = None
        if self._cursors and self.height > 10:
            scale = (self.height / GRID_Y) / self.v_div
            t_win = self.t_ms * 1e-3 * GRID_X
            if self._cur["H1"] is not None and self._cur["H2"] is not None:
                dv = (self._cur["H2"] - self._cur["H1"]) / scale
            if self._cur["V1"] is not None and self._cur["V2"] is not None:
                dt_c = (self._cur["V2"] - self._cur["V1"]) / self.width * t_win
        self.m = {
            "vmax": float(arr.max()), "vmin": float(arr.min()),
            "vpp":  float(arr.max()-arr.min()),
            "vrms": float(np.sqrt(np.mean(arr**2))),
            "mean": mean, "duty": duty, "freq": freq, "per": per,
            "dv": dv, "dt": dt_c,
        }

    # Touch / Souris ───────────────────────────────────────────────────────────

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        touch.grab(self)

        # Double tap → reset T/div, V/div, trigger
        if touch.is_double_tap:
            self._t_idx    = TIMEBASES_MS.index(5)
            self._v_idx    = VOLT_DIVS.index(1.0)
            self._trig_lvl = 0.0
            if self._adj_cb: self._adj_cb()
            return True

        # Grab curseur si CUR actif
        if self._cursors:
            tx, ty = touch.pos
            best, best_d = None, GRAB_TOL
            for name, pos in self._cur.items():
                if pos is None: continue
                d = abs(ty-pos) if name.startswith("H") else abs(tx-pos)
                if d < best_d:
                    best, best_d = name, d
            if best:
                self._grabbed = best
                return True

        # Initialise le geste 1 doigt — zone L (tiers gauche) = V offset, R = trigger
        self._drag_y0      = touch.pos[1]
        self._gesture_dir  = None
        self._gesture_x0   = touch.pos[0]
        self._gesture_sx   = touch.pos[0]
        self._gesture_zone = "L" if touch.pos[0] < self.x + self.width / 3 else "R"
        return True

    def on_touch_move(self, touch):
        if touch.grab_current is not self:
            return False

        # Drag curseur
        if self._grabbed:
            name = self._grabbed
            if name.startswith("H"):
                self._cur[name] = max(self.y, min(self.y+self.height, touch.y))
            else:
                self._cur[name] = max(self.x, min(self.x+self.width, touch.x))
            return True

        if self._drag_y0 is None:
            return True

        tx, ty = touch.pos
        dx = tx - self._gesture_x0
        dy = ty - self._drag_y0

        # Verrouille la direction après 20px de déplacement
        if self._gesture_dir is None and (abs(dx) > 20 or abs(dy) > 20):
            self._gesture_dir = "H" if abs(dx) > abs(dy) else "V"

        if self._gesture_dir == "H":
            step_dx = tx - self._gesture_sx
            if abs(step_dx) >= _PINCH_STEP:
                if not self._running and self._frozen_buf:
                    # STOP : naviguer dans le buffer (gauche = avant, droite = arrière)
                    self.adj_buf_offset(-1 if step_dx > 0 else +1)
                else:
                    # Running : changer T/div
                    self.adj_t(+1 if step_dx > 0 else -1)
                self._gesture_sx = tx
                if self._adj_cb: self._adj_cb()

        elif self._gesture_dir == "V" and self.height > 0:
            scale = (self.height / GRID_Y) / self.v_div
            cy    = self.y + self.height / 2
            if self._gesture_zone == "L":
                # Tiers gauche → V offset (absolu)
                self._v_offset = round((ty - cy) / scale, 3)
            else:
                # Reste → trigger (absolu)
                self._trig_lvl = round((ty - cy) / scale, 3)
            if self._adj_cb: self._adj_cb()

        return True

    def on_touch_up(self, touch):
        if touch.grab_current is not self:
            return False
        touch.ungrab(self)
        if self._grabbed:
            self._grabbed = None
        else:
            self._drag_y0     = None
            self._gesture_dir = None
        return True

    def _on_size(self, *a):
        if self._cursors:
            for k in ("H1","H2"):
                if self._cur[k] is not None:
                    self._cur[k] = max(self.y, min(self.y+self.height, self._cur[k]))
            for k in ("V1","V2"):
                if self._cur[k] is not None:
                    self._cur[k] = max(self.x, min(self.x+self.width, self._cur[k]))
        self._redraw()

    # Update & Draw ────────────────────────────────────────────────────────────

    def update(self, samples, trig_mode="AUTO"):
        self._samples = samples
        n_disp = max(2, int(self.t_ms*1e-3*self._sr*GRID_X))
        if not self._running:
            if self._frozen_buf:
                end   = len(self._frozen_buf) - self._buf_offset
                start = max(0, end - n_disp)
                win   = self._frozen_buf[start:end]
                self._compute_meas(win)
                self._draw(win)
            return
        if trig_mode in ("NORM","SING"):
            start = self._find_trigger(samples, n_disp)
        else:
            start = max(0, len(samples)-n_disp)
        win = samples[start:start+n_disp]
        if self._persist_mode:
            self._sweeps.append(list(win))
        self._compute_meas(win)
        self._draw(win)

    def _redraw(self, *a):
        if self._samples: self.update(self._samples)
        else:             self._draw_empty()

    def _draw_empty(self):
        self.canvas.clear()
        w, h = self.width, self.height
        with self.canvas:
            Color(*C_BG)
            Rectangle(pos=self.pos, size=self.size)
            Color(*C_GRID)
            for c in range(GRID_X+1):
                Line(points=[self.x+c*w/GRID_X, self.y, self.x+c*w/GRID_X, self.y+h], width=1)
            for r in range(GRID_Y+1):
                Line(points=[self.x, self.y+r*h/GRID_Y, self.x+w, self.y+r*h/GRID_Y], width=1)

    def _draw(self, win):
        self.canvas.clear()
        w, h = self.width, self.height
        if w < 4 or h < 4: return

        if self._fft_mode:
            self._draw_fft(win)
            return

        n_px = int(w)
        def _resample(buf):
            n = len(buf)
            if n > n_px:
                step = n / n_px
                buf = [buf[int(i*step)] for i in range(n_px)]
            return buf

        win = _resample(win)
        n   = len(win)

        scale  = (h / GRID_Y) / self.v_div
        cy     = self.y + h/2
        cy_eff = cy + self._v_offset * scale
        trig_y = max(self.y+1, min(self.y+h-1, cy + self._trig_lvl*scale))

        def _sweep_pts(buf):
            nb = len(buf)
            if nb < 2: return []
            pts = []
            for i, v in enumerate(buf):
                if self._inverted: v = -v
                px = self.x + i*w/max(nb-1, 1)
                py = max(self.y+1, min(self.y+h-1, cy_eff + float(v)*scale))
                pts += [px, py]
            return pts

        C_DRAW_BG = (0.02, 0.0, 0.06, 1) if self._persist_mode else C_BG

        with self.canvas:
            Color(*C_DRAW_BG)
            Rectangle(pos=self.pos, size=self.size)

            # Persistence — sweeps anciens avec alpha décroissant
            if self._persist_mode and len(self._sweeps) > 1:
                n_sw = len(self._sweeps)
                for sw_idx, sweep in enumerate(self._sweeps):
                    if sw_idx == n_sw - 1:
                        continue
                    alpha = (sw_idx + 1) / n_sw * 0.55
                    pts = _sweep_pts(_resample(list(sweep)))
                    if pts:
                        Color(C_WAVE[0], C_WAVE[1], C_WAVE[2], alpha)
                        Line(points=pts, width=1.0)

            Color(*C_GRID)
            for c in range(GRID_X+1):
                xg = self.x+c*w/GRID_X
                Line(points=[xg, self.y, xg, self.y+h], width=1)
            for r in range(GRID_Y+1):
                yg = self.y+r*h/GRID_Y
                Line(points=[self.x, yg, self.x+w, yg], width=1)

            Color(*C_AXIS)
            Line(points=[self.x, cy_eff, self.x+w, cy_eff], width=1.5)
            Line(points=[self.x+w/2, self.y, self.x+w/2, self.y+h], width=1.5)

            my = max(self.y+4, min(self.y+h-4, cy_eff))
            Color(*C_WAVE)
            Line(points=[self.x, my, self.x+8, my+5, self.x+8, my-5, self.x, my], width=1)

            Color(*C_TRIG)
            Line(points=[self.x, trig_y, self.x+w, trig_y], width=1.2)
            tx = self.x+3
            Line(points=[tx, trig_y, tx+10, trig_y+5, tx+10, trig_y-5, tx, trig_y], width=1)

            if self._cursors:
                for name, color in (("H1",C_H1),("H2",C_H2)):
                    pos = self._cur[name]
                    if pos is not None:
                        Color(*color)
                        Line(points=[self.x, pos, self.x+w, pos],
                             dash_length=8, dash_offset=4, width=1.5)
                for name, color in (("V1",C_V1),("V2",C_V2)):
                    pos = self._cur[name]
                    if pos is not None:
                        Color(*color)
                        Line(points=[pos, self.y, pos, self.y+h],
                             dash_length=8, dash_offset=4, width=1.5)

            pts = _sweep_pts(win)
            if pts:
                Color(*C_WAVE)
                Line(points=pts, width=1.5)

    def _draw_fft(self, win):
        w, h = self.width, self.height
        n = len(win)
        if n < 8: return

        # Fenêtre Hann — réduit la fuite spectrale (harmoniques parasites)
        window   = np.hanning(n)
        arr      = np.array(win, dtype=np.float32) * window
        fft_vals = np.abs(np.fft.rfft(arr))
        fft_n    = len(fft_vals)

        # Echelle dB normalisée, plancher -60 dB
        fft_db = 20 * np.log10(fft_vals / max(float(fft_vals.max()), 1e-9) + 1e-9)
        fft_db = np.clip(fft_db, -60, 0)
        norm   = (fft_db + 60) / 60.0   # 0..1

        peak_idx  = int(np.argmax(fft_vals[1:])) + 1
        peak_freq = peak_idx * (self._sr / 2.0) / max(fft_n - 1, 1)

        C_FFT_BG  = (0.0, 0.04, 0.10, 1)
        AX_H      = 16   # hauteur réservée en bas pour l'axe de fréquence
        plot_y    = self.y + AX_H
        plot_h    = h - AX_H

        from kivy.core.text import Label as CoreLabel

        with self.canvas:
            Color(*C_FFT_BG)
            Rectangle(pos=self.pos, size=self.size)

            # Grille (dans la zone plot uniquement)
            Color(*C_GRID)
            for c in range(GRID_X + 1):
                xg = self.x + c * w / GRID_X
                Line(points=[xg, plot_y, xg, plot_y + plot_h], width=1)
            for r in range(GRID_Y + 1):
                yg = plot_y + r * plot_h / GRID_Y
                Line(points=[self.x, yg, self.x + w, yg], width=1)

            # Barres spectrales
            bar_w = max(1.0, w / max(fft_n, 1))
            for i in range(fft_n):
                v = float(norm[i])
                if v < 0.01: continue
                px    = self.x + i * w / max(fft_n - 1, 1)
                bar_h = v * plot_h * 0.95
                Color(0.1 + 0.6*v, 0.6 + 0.4*v, 0.2, 0.9)
                Rectangle(pos=(px, plot_y), size=(max(bar_w - 1, 1), bar_h))

            # Marqueur pic
            peak_px = self.x + peak_idx * w / max(fft_n - 1, 1)
            Color(*C_TRIG)
            Line(points=[peak_px, plot_y, peak_px, plot_y + plot_h], width=1.5)

            # Label pic — haut gauche
            Color(1.0, 0.85, 0.0, 1)
            cl = CoreLabel(text=f"Pic: {_fmt_freq(peak_freq)}", font_size=13)
            cl.refresh()
            if cl.texture:
                Rectangle(texture=cl.texture,
                          pos=(self.x + 6, plot_y + plot_h - cl.texture.height - 4),
                          size=cl.texture.size)

            # Axe de fréquence : labels START / intermédiaires / STOP
            nyq = self._sr / 2.0
            n_lbl = 5   # 0, 1/5, 2/5, 3/5, 4/5, 5/5 = 6 points
            Color(0.45, 0.45, 0.55, 1)
            for i in range(n_lbl + 1):
                freq = i * nyq / n_lbl
                lx   = self.x + i * w / n_lbl
                lbl  = CoreLabel(text=_fmt_freq(freq), font_size=10)
                lbl.refresh()
                if lbl.texture:
                    tx = max(self.x,
                             min(self.x + w - lbl.texture.width,
                                 lx - lbl.texture.width / 2))
                    Rectangle(texture=lbl.texture,
                              pos=(tx, self.y + 2),
                              size=lbl.texture.size)


# ── Helpers panneau droit ─────────────────────────────────────────────────────

def _pm_row(lbl, minus_cb, plus_cb, h=_PM_H):
    """Ligne [−] valeur [+] pour un réglage numérique."""
    row = BoxLayout(size_hint=(1, None), height=h, spacing=4)
    for text, cb in (("-", minus_cb), ("+", plus_cb)):
        b = Button(text=text, font_size=FS_PM, bold=True,
                   size_hint=(None, 1), width=46,
                   background_color=C_BTN, background_normal="")
        b.bind(on_press=lambda *a, f=cb: f())
        if text == "-":
            row.add_widget(b)
            row.add_widget(lbl)
        else:
            row.add_widget(b)
    return row


def _section(title, *children):
    """Bloc label titre + enfants, hauteur fixe auto-calculée."""
    child_h = sum(getattr(c, "height", 36) for c in children)
    h = 16 + child_h + 2 * (1 + len(children))
    box = BoxLayout(orientation="vertical", size_hint=(1, None), height=h, spacing=2)
    box.add_widget(Label(text=title, font_size=FS_TITLE, color=C_TEXT,
                          size_hint=(1, None), height=16,
                          halign="left", valign="middle",
                          text_size=(PANEL_W - 16, 16),
                          shorten=True, shorten_from="right"))
    for c in children:
        box.add_widget(c)
    return box


def _tog_row(*items, h=_TOG_H):
    """Ligne de ToggleButtons. items = [(text, group, cb, actif), ...]"""
    row = BoxLayout(size_hint=(1, None), height=h, spacing=4)
    btns = []
    for text, group, cb, active in items:
        b = ToggleButton(text=text, group=group, font_size=FS_TOGGLE,
                          background_normal="",
                          state="down" if active else "normal",
                          background_color=C_ON if active else C_BTN)
        b.bind(on_press=lambda btn, f=cb: f())
        btns.append(b)
        row.add_widget(b)
    return row, btns


# ── ScopeScreen ───────────────────────────────────────────────────────────────

class ScopeScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)
        import settings_manager as SM
        self._SM          = SM
        SM.load()
        self._capture     = None
        self._ch_label    = "---"
        self._running     = True
        self._trig_mode   = "AUTO"
        self._coupling    = "DC"
        self._single_done = False

        root = BoxLayout(orientation="horizontal", spacing=0)

        # Colonne gauche : header + waveform + mesures
        left = BoxLayout(orientation="vertical", size_hint=(1, 1))
        left.add_widget(self._build_header())
        self._wave = WaveformWidget()
        self._wave._adj_cb = self._sync_labels
        left.add_widget(self._wave)
        left.add_widget(self._build_meas())
        root.add_widget(left)

        # Panneau droit pleine hauteur
        root.add_widget(self._build_panel())

        self.add_widget(root)
        self._init_capture(source=SM.get("source"))
        Clock.schedule_interval(self._tick, 1/25)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = BoxLayout(size_hint=(1, None), height=HEADER_H,
                         padding=[10, 6], spacing=8)
        _bg(hdr, C_HDR)

        # Bouton source cyclique : tap = MIC→PICO→SIM→MIC
        self._btn_src = Button(
            text="* MIC", font_size=FS_HDR_INFO, bold=True,
            background_color=(0.10, 0.22, 0.10, 1), background_normal="",
            size_hint=(None, 1), width=88)
        self._btn_src.bind(on_press=self._cycle_source)

        self._lbl_mode  = Label(text="AUTO",     font_size=FS_HDR_INFO,
                                 color=(0.4,1,0.4,1), size_hint=(None,1), width=56)
        self._lbl_slope = Label(text="^ RISE",   font_size=FS_HDR_INFO,
                                 color=C_YEL, size_hint=(None,1), width=66)
        self._lbl_t_hdr = Label(text="5ms/div",  font_size=FS_HDR_INFO,
                                 color=C_YEL, size_hint=(None,1), width=80)
        self._lbl_v_hdr = Label(text="1V/div",   font_size=FS_HDR_INFO,
                                 color=C_CYN, size_hint=(None,1), width=72)
        self._lbl_coup  = Label(text="DC",        font_size=FS_HDR_INFO,
                                 color=C_TEXT, size_hint=(None,1), width=34)
        self._lbl_sr = Label(text="", font_size="11sp", color=(0.45, 0.45, 0.45, 1),
                              size_hint=(1, 1), halign="center", valign="middle")
        self._btn_run = Button(text="STOP", font_size=FS_HDR_STOP, bold=True,
                                background_color=(0.65,0.10,0.10,1),
                                background_normal="", size_hint=(None,1), width=100)
        self._btn_run.bind(on_press=self._toggle_run)

        for w in (self._btn_src, self._lbl_mode, self._lbl_slope,
                  self._lbl_t_hdr, self._lbl_v_hdr, self._lbl_coup,
                  self._lbl_sr, self._btn_run):
            hdr.add_widget(w)
        return hdr

    # ── Mesures ───────────────────────────────────────────────────────────────

    def _build_meas(self):
        bar = BoxLayout(orientation="vertical", size_hint=(1, None),
                         height=MEAS_H, padding=[8, 6], spacing=2)
        _bg(bar, C_MEAS)

        def _L(text, color=C_GRN):
            return Label(text=text, font_size=FS_MEAS, color=color,
                          halign="center", valign="middle")

        r1 = GridLayout(cols=5, size_hint=(1, None), height=28)
        self._m_vmax = _L("Vmax: ---")
        self._m_vmin = _L("Vmin: ---")
        self._m_vpp  = _L("Vpp: ---")
        self._m_vrms = _L("Vrms: ---")
        self._m_mean = _L("Mean: ---")
        for l in (self._m_vmax, self._m_vmin, self._m_vpp, self._m_vrms, self._m_mean):
            r1.add_widget(l)

        r2 = GridLayout(cols=5, size_hint=(1, None), height=28)
        self._m_freq = _L("Freq: ---",   C_CYN)
        self._m_per  = _L("Period: ---", C_CYN)
        self._m_duty = _L("Duty: ---",   C_CYN)
        self._m_dv   = _L("Trig: ---",  C_YEL)
        self._m_dt   = _L("---kS/s",    (0.45, 0.45, 0.45, 1))
        for l in (self._m_freq, self._m_per, self._m_duty, self._m_dv, self._m_dt):
            r2.add_widget(l)

        bar.add_widget(r1)
        bar.add_widget(r2)
        return bar

    # ── Panneau droit ─────────────────────────────────────────────────────────

    def _build_panel(self):
        panel = BoxLayout(orientation="vertical", size_hint=(None, 1),
                           width=PANEL_W, padding=[8, 6], spacing=1)
        _bg(panel, C_PANEL)

        # Largeur dispo pour la valeur dans une pm_row : panel - padding - 2 boutons - spacing
        _VW = PANEL_W - 16 - 92 - 8

        def _vlbl(text, color):
            return Label(text=text, font_size=FS_VALUE, color=color,
                         halign="center", valign="middle",
                         shorten=True, shorten_from="right",
                         text_size=(_VW, None))

        # T/div
        self._lbl_t = _vlbl("5ms", C_YEL)
        panel.add_widget(_section("T / div",
            _pm_row(self._lbl_t, lambda: self._adj("t",-1), lambda: self._adj("t",+1))))

        # V/div
        self._lbl_v = _vlbl("1V", C_CYN)
        panel.add_widget(_section("V / div",
            _pm_row(self._lbl_v, lambda: self._adj("v",-1), lambda: self._adj("v",+1))))

        # Trigger
        self._lbl_trig = _vlbl("+0.00V", C_YEL)
        panel.add_widget(_section("Trigger",
            _pm_row(self._lbl_trig, lambda: self._adj("trig",-1), lambda: self._adj("trig",+1))))

        # Pente
        slope_row, self._slope_btns = _tog_row(
            (_t("rise"), "slope", lambda: self._set_slope("RISE"), True),
            (_t("fall"), "slope", lambda: self._set_slope("FALL"), False),
        )
        panel.add_widget(_section(_t("slope"), slope_row))

        # Mode
        mode_row, self._mode_btns = _tog_row(
            ("AUTO", "tmode", lambda: self._set_mode("AUTO"), True),
            ("NORM", "tmode", lambda: self._set_mode("NORM"), False),
            ("SING", "tmode", lambda: self._set_mode("SING"), False),
        )
        panel.add_widget(_section("Mode", mode_row))

        # Couplage
        coup_row, self._coup_btns = _tog_row(
            ("AC", "coup", lambda: self._set_coupling("AC"), False),
            ("DC", "coup", lambda: self._set_coupling("DC"), True),
        )
        panel.add_widget(_section(_t("coupling"), coup_row))

        # Options ligne 1 : INV + CUR
        opts1 = BoxLayout(size_hint=(1, None), height=34, spacing=4)
        for attr, text, cb in (
            ("_btn_inv", "INV", self._toggle_inv),
            ("_btn_cur", "CUR", self._toggle_cur),
        ):
            b = Button(text=text, font_size=FS_TOGGLE,
                       background_normal="", background_down="",
                       background_color=C_BTN)
            b.bind(on_press=cb)
            setattr(self, attr, b)
            opts1.add_widget(b)

        # Options ligne 2 : bouton Vue qui cycle NORM→FFT→PST→NORM
        self._view_mode = "NORM"
        self._btn_vue = Button(text="Vue: NORM", font_size=FS_TOGGLE, bold=True,
                               background_normal="", background_down="",
                               background_color=C_BTN,
                               size_hint=(1, None), height=34)
        self._btn_vue.bind(on_press=self._cycle_view)

        panel.add_widget(_section("Options", opts1, self._btn_vue))

        # _lbl_voff gardé pour _sync_labels (V offset via geste waveform zone gauche)
        self._lbl_voff = _vlbl("+0.00V", C_GRN)

        panel.add_widget(Widget())   # spacer flexible

        btn_tools = Button(text=_t("menu"), font_size=FS_QUIT, bold=True,
                           size_hint=(1, None), height=_TOG_H + 4,
                           background_color=(0.20, 0.20, 0.32, 1), background_normal="")
        btn_tools.bind(on_press=self._open_tools_popup)
        panel.add_widget(btn_tools)

        btn_q = Button(text=_t("quit"), font_size=FS_QUIT,
                       size_hint=(1, None), height=_TOG_H + 4,
                       background_color=(0.18, 0.18, 0.28, 1), background_normal="")
        btn_q.bind(on_press=self._go_back)
        panel.add_widget(btn_q)

        return panel

    # ── Capture ───────────────────────────────────────────────────────────────

    def _init_capture(self, source=None):
        try:
            from audio_capture import make_capture
            self._capture, ch = make_capture(source=source)
            self._ch_label = ch
        except Exception:
            try:
                from audio_capture import DummyCapture
                self._capture = DummyCapture()
                self._capture.start()
                self._ch_label = "SIM"
            except Exception:
                self._capture = None
                self._ch_label = "ERR"
        Clock.schedule_once(lambda dt: setattr(self._btn_src, "text", f"* {self._ch_label}"))
        if self._capture:
            self._wave.set_sr(self._capture.sample_rate)

    # ── Tick ──────────────────────────────────────────────────────────────────

    def _tick(self, dt):
        if not self._capture: return
        if self._trig_mode == "SING" and self._single_done: return
        n   = max(4096, int(self._wave.t_ms*1e-3*self._capture.sample_rate*GRID_X)+2048)
        raw = self._capture.get_samples(n)
        if self._coupling == "AC":
            raw = self._wave.apply_hpf(raw)
        self._wave.update(raw, self._trig_mode)
        self._update_meas()
        if self._trig_mode == "SING":
            self._single_done = True

    def _update_meas(self):
        m = self._wave.m
        if not m: return
        fv = lambda x: f"{x:.3f}V"
        self._m_vmax.text = f"Vmax:{fv(m['vmax'])}"
        self._m_vmin.text = f"Vmin:{fv(m['vmin'])}"
        self._m_vpp.text  = f"Vpp:{fv(m['vpp'])}"
        self._m_vrms.text = f"Vrms:{fv(m['vrms'])}"
        self._m_mean.text = f"Mean:{fv(m['mean'])}"
        self._m_freq.text = f"Freq:{_fmt_freq(m['freq'])}"
        self._m_per.text  = f"T:{_fmt_time(m['per'])}"
        self._m_duty.text = f"Duty:{m['duty']:.1f}%"
        slope_sym = "^" if self._wave._slope == "RISE" else "v"
        self._m_dv.text = f"Trig:{fv(self._wave._trig_lvl)}{slope_sym}"
        if self._capture:
            if self._ch_label == "SIM":
                self._m_dt.text = "SIM"
            else:
                self._m_dt.text = f"{self._capture.sample_rate//1000}kS/s"

    # ── Actions ───────────────────────────────────────────────────────────────

    def _adj(self, what, d):
        w = self._wave
        if what == "t":
            w.adj_t(d)
            t = _fmt_t(w.t_ms)
            self._lbl_t.text     = t
            self._lbl_t_hdr.text = f"{t}/div"
        elif what == "v":
            w.adj_v(d)
            v = _fmt_v(w.v_div)
            self._lbl_v.text     = v
            self._lbl_v_hdr.text = f"{v}/div"
        elif what == "trig":
            w.adj_trig(d)
            self._lbl_trig.text = f"{w._trig_lvl:+.2f}V"
        elif what == "voff":
            w.adj_voff(d)
            self._lbl_voff.text = f"{w._v_offset:+.2f}V"

    def _set_slope(self, s):
        self._wave.set_slope(s)
        self._lbl_slope.text = _t("rise") if s == "RISE" else _t("fall")
        for b, key in zip(self._slope_btns, ("RISE", "FALL")):
            b.background_color = C_ON if key == s else C_BTN
            b.text = _t("rise") if key == "RISE" else _t("fall")

    def _set_mode(self, mode):
        self._trig_mode = mode
        self._single_done = False
        self._lbl_mode.text = mode
        labels = ["AUTO", "NORM", "SING"]
        for b, lbl in zip(self._mode_btns, labels):
            b.background_color = C_ON if lbl == mode else C_BTN

    def _set_coupling(self, c):
        self._coupling = c
        if c == "AC": self._wave.reset_hpf()
        self._lbl_coup.text = c
        for b, lbl in zip(self._coup_btns, ["AC","DC"]):
            b.background_color = C_ON if lbl == c else C_BTN

    def _toggle_inv(self, *a):
        self._inv_on = not getattr(self, "_inv_on", False)
        self._wave.set_inverted(self._inv_on)
        self._btn_inv.background_color = C_ON if self._inv_on else C_BTN
        self._update_mode_label()

    def _toggle_cur(self, *a):
        on = self._wave.toggle_cursors()
        self._btn_cur.background_color = C_ON if on else C_BTN

    def _cycle_view(self, *a):
        modes = ["NORM", "FFT", "PST"]
        self._view_mode = modes[(modes.index(self._view_mode) + 1) % len(modes)]
        self._wave.set_fft_mode(self._view_mode == "FFT")
        self._wave.set_persist_mode(self._view_mode == "PST")
        colors = {
            "NORM": C_BTN,
            "FFT":  (0.80, 0.50, 0.0, 1),
            "PST":  (0.0,  0.45, 0.70, 1),
        }
        self._btn_vue.background_color = colors[self._view_mode]
        self._btn_vue.text = f"Vue: {self._view_mode}"
        self._update_mode_label()

    def _update_mode_label(self):
        parts = []
        if self._view_mode != "NORM": parts.append(self._view_mode)
        if getattr(self, "_inv_on", False): parts.append("INV")
        self._lbl_sr.text  = "  ".join(parts) if parts else ""
        self._lbl_sr.color = (1.0, 0.80, 0.0, 1) if parts else (0.45, 0.45, 0.45, 1)

    def _sync_labels(self):
        w = self._wave
        t = _fmt_t(w.t_ms)
        v = _fmt_v(w.v_div)
        self._lbl_t.text     = t
        self._lbl_t_hdr.text = f"{t}/div"
        self._lbl_v.text     = v
        self._lbl_v_hdr.text = f"{v}/div"
        self._lbl_trig.text  = f"{w._trig_lvl:+.2f}V"
        self._lbl_voff.text  = f"{w._v_offset:+.2f}V"
        self._update_mode_label()

    def _toggle_run(self, *a):
        self._running = not self._running
        self._wave._running = self._running
        if not self._running:
            self._wave.freeze_buf(self._wave._samples)
        self._btn_run.text = "STOP" if self._running else "RUN"
        self._btn_run.background_color = ((0.65,0.10,0.10,1)
                                          if self._running else (0.10,0.55,0.10,1))

    def _cycle_source(self, *a):
        if getattr(self, "_src_busy", False):
            return
        self._src_busy = True
        self._btn_src.disabled = True
        self._btn_src.text = "* ..."
        sources = ["MIC"]
        if os.path.exists("/dev/ttyACM0"):
            sources.append("PICO")
        sources.append("SIM")
        idx = sources.index(self._ch_label) if self._ch_label in sources else -1
        nxt = sources[(idx + 1) % len(sources)]
        if self._capture:
            self._capture.stop()
            self._capture = None
        import threading
        def _worker():
            self._init_capture(source=nxt)
            def _done(dt):
                self._btn_src.disabled = False
                self._src_busy = False
            Clock.schedule_once(_done)
        threading.Thread(target=_worker, daemon=True).start()

    def _open_tools_popup(self, *a):
        import nav_menu
        nav_menu.open_nav_menu(self)

    def _go_back(self, *a):
        try:
            with open("/tmp/adnrpi-next", "w") as f:
                f.write("launcher")
        except Exception:
            pass
        from kivy.app import App
        App.get_running_app().stop()

    def on_enter(self, *a):
        self._SM.load()
        self._wave._v_offset = self._SM.get("adc_offset_mv", 0.0) / 1000.0
        if not self._capture:
            self._init_capture(source=self._SM.get("source"))
        Clock.unschedule(self._tick)
        Clock.schedule_interval(self._tick, 1/25)

    def on_leave(self, *a):
        Clock.unschedule(self._tick)
        if self._capture:
            self._capture.stop()
            self._capture = None
