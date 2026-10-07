#!/usr/bin/env python3
"""
FaceEngine — Moteur visage robot kawaii, SmartPi H3 / Mali400.
Canvas 100 % persistant, zéro canvas.clear() par frame.

Formes de tête :
  neutral  → arrondi haut/bas
  sun      → disque doré + rayons
  cloud    → 4 ellipses silhouette nuage (base + 3 bosses circulaires)
  storm    → rectangle sombre anguleux + foudre
  snow     → ovale bleu glacé + stalactites

Cross-fade symétrique : chaque forme a son propre alpha (_shape_alpha).
"""
from __future__ import annotations
import math, random
from typing import Optional

from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import (Color, Ellipse, Line, PopMatrix, PushMatrix,
                            Rectangle, Rotate, RoundedRectangle)
from kivy.uix.widget import Widget

# ── Constantes ───────────────────────────────────────────────────────────────
TAU = math.tau
PI  = math.pi

N_SNOW    = 12
N_RAYS    = 8
N_ICICLE  = 6

FPS             = 60.0
MIN_WIDGET_SIZE = 200
MAX_DT          = 1.0 / 8.0

RATE_COLOR   = 4.0
RATE_GAZE    = 12.0
RATE_ANGLE   = 12.0
HEAD_SPEED   = 360.0   # px/s — vitesse constante errance (indépendant du FPS)
RATE_SHAPE     = 10.0
RATE_SHAPE_OUT = 22.0   # sortie quasi-instantanée → pas de mélange visible

JUMP_V0  = 420.0
GRAVITY  = 900.0

BLINK_CLOSE_T  = 0.08
BLINK_HOLD_T   = 0.06
BLINK_WAIT_MIN = 1.5
BLINK_WAIT_MAX = 5.0

IDLE_TIMEOUT = 45.0
WANDER_MIN   = 4.0
WANDER_MAX   = 9.0

WEATHER_BOLT_P = 0.55

# 4 ellipses nuage — (x_frac, y_frac, w_frac, h_frac) relatif à (fw, fh)
# Bosses quasi-circulaires : w_frac/h_frac ≈ fh/fw ≈ 0.658 pour 800×480
_CLOUD_LAYOUT = [
    ( 0.00, -0.10, 1.08, 0.52),   # base aplatie (plus large que tête)
    (-0.27,  0.14, 0.45, 0.68),   # bosse gauche  (≈cercle 150px)
    ( 0.00,  0.25, 0.51, 0.77),   # bosse centrale (≈cercle 170px, la plus haute)
    ( 0.27,  0.14, 0.45, 0.68),   # bosse droite
]
CLOUD_W = 1.08
CLOUD_H = 1.30


# ── Utilitaires ──────────────────────────────────────────────────────────────
def _lerp(a, b, t):    return a + (b - a) * t
def _clamp(v, lo, hi): return max(lo, min(hi, v))
def _smooth(cur, tgt, rate, dt, eps=0.3):
    if abs(tgt - cur) < eps: return tgt
    return cur + (tgt - cur) * (1.0 - math.exp(-rate * dt))
def _identity(t):      return t
def _ease_inout(t):    return t * t * (3.0 - 2.0 * t)
def _ease_out_quad(t): return t * (2.0 - t)

def _make_star_unit(n=5):
    pts = []
    for i in range(n * 2 + 1):
        r = 1.0 if i % 2 == 0 else 0.40
        a = PI / 2 + i * PI / n
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts

_STAR_UNIT = _make_star_unit()

def _scale_pts(unit, cx, cy, s):
    out = []
    for x, y in unit:
        out.append(cx + x * s)
        out.append(cy + y * s)
    return out


# ── Animation composable ─────────────────────────────────────────────────────
class _Anim:
    __slots__ = ("dur", "fn", "done", "ease", "tag",
                 "_e", "finished", "cancelled")
    def __init__(self, dur, fn, done=None, ease=None, tag=None):
        self.dur = max(dur, 0.001); self.fn = fn; self.done = done
        self.ease = ease or _identity; self.tag = tag
        self._e = 0.0; self.finished = False; self.cancelled = False
    def tick(self, dt):
        self._e = min(self._e + dt, self.dur)
        self.fn(self.ease(self._e / self.dur))
        if self._e >= self.dur:
            self.finished = True
            if self.done: self.done()


# ── FaceEngine ───────────────────────────────────────────────────────────────
class FaceEngine(Widget):
    """
    API
    ───
    set_expression(name)       neutral/happy/sad/surprised/curious/
                               tired/worried/angry/love/thinking/
                               laughing/excited
    set_eye_type(t)            normal/stars/bars/dots
    set_head_color(r,g,b,dur)
    set_weather(w)             none/sun/cloud/storm/snow
    animate_jump()
    animate_spin()
    animate_flip(side)         'left'|'right'
    animate_flip_vertical()
    animate_roll()
    animate_somersault()
    animate_backflip()
    animate_shake(amp, dur)
    animate_excited()
    animate_nod()
    animate_peek(side)         'left'|'right'
    speak(active)
    look_at(nx, ny, hold)
    set_state(s, lv)
    """

    _STATE_MAP = {
        "init": "neutral", "idle": "neutral", "wake": "surprised",
        "listening": "curious", "processing": "thinking", "result": "happy",
    }
    _STATE_COLOR = {
        "init":       (0.96, 0.96, 0.97),
        "idle":       (0.96, 0.96, 0.97),
        "wake":       (1.00, 0.95, 0.62),   # jaune-chaud  — "Je t'entends !"
        "listening":  (0.70, 0.90, 1.00),   # cyan vif     — "Parle maintenant"
        "processing": (0.90, 0.84, 1.00),   # violet doux  — "Je réfléchis"
        "result":     (0.82, 1.00, 0.86),   # vert clair   — "J'ai compris"
    }

    # ── Init ─────────────────────────────────────────────────────────────────
    def __init__(self, **kw):
        super().__init__(**kw)
        self._t = 0.0; self._breath = 0.0; self._idle_t = 0.0
        self._expression = "neutral"; self._eye_type = "normal"
        self._speaking = False; self._speak_t = 0.0

        self.face_cx = 400.0; self.face_cy = 240.0
        self._tgt_cx = 400.0; self._tgt_cy = 240.0
        self._wander_t = 10.0; self._centered = False
        self._wander_hold = 0.0

        self._gaze_x = 0.0; self._gaze_y = 0.0
        self._tgt_gx = 0.0; self._tgt_gy = 0.0
        self._face_angle = 0.0; self._tgt_face_angle = 0.0

        self._blink = 1.0; self._blink_phase = "wait"
        self._blink_timer = random.uniform(BLINK_WAIT_MIN, BLINK_WAIT_MAX)

        self._hr = 0.96; self._hg = 0.96; self._hb = 0.97
        self._tr = 0.96; self._tg = 0.96; self._tb = 0.97

        self._scale_x = 1.0; self._scale_y = 1.0
        self._jump_vy = 0.0; self._jump_base = 240.0
        self._shake_x = 0.0; self._nod_y = 0.0

        # Cross-fade symétrique par forme
        self._shape_alpha  = {"neutral": 1.0, "sun": 0.0, "cloud": 0.0,
                               "storm": 0.0, "snow": 0.0}
        self._shape_target = dict(self._shape_alpha)
        self._weather = None
        self._weather_a = 0.0

        self._snow_x = [random.uniform(50, 750) for _ in range(N_SNOW)]
        self._snow_y = [random.uniform(0, 480)  for _ in range(N_SNOW)]
        self._ray_ang = [i * (360.0 / N_RAYS) for i in range(N_RAYS)]
        self._bolt_t = 0.0; self._bolt_pts = [0.0] * 8

        self._anims: list = []

        self._build_canvas()
        self.bind(size=self._on_resize, pos=self._on_resize)
        self._ev_tick = Clock.schedule_interval(self._tick,        1.0 / 30.0)
        self._ev_gaze = Clock.schedule_interval(self._random_gaze, 2.4)

    def on_parent(self, _widget, parent):
        if parent is None:
            for ev in (self._ev_tick, self._ev_gaze):
                if ev: ev.cancel()
            self._ev_tick = self._ev_gaze = None
        elif self._ev_tick is None:
            self._ev_tick = Clock.schedule_interval(self._tick,        1.0 / 30.0)
            self._ev_gaze = Clock.schedule_interval(self._random_gaze, 2.4)

    # ── Canvas persistant ─────────────────────────────────────────────────────
    def _build_canvas(self):
        with self.canvas:
            Color(0, 0, 0, 1)
            self._bg = Rectangle(pos=(0, 0), size=(800, 480))

            PushMatrix()
            self._face_rot = Rotate(angle=0, axis=(0, 0, 1), origin=(400, 240))

            # Rayons
            self._ray_c = Color(1.0, 0.88, 0.2, 0)
            self._rays  = [Line(points=[0, 0, 0, 0], width=2.8)
                           for _ in range(N_RAYS)]

            # Ombre
            self._shadow_c = Color(0, 0, 0, 0)
            self._shadow   = Ellipse(pos=(-500, -500), size=(100, 100))

            # NEUTRE
            self._head_c = Color(0.96, 0.96, 0.97, 0)
            self._head   = RoundedRectangle(pos=(-500, -500),
                                            size=(100, 100), radius=[60])

            # SOLEIL
            self._sun_c    = Color(1.0, 0.90, 0.25, 0)
            self._sun_body = Ellipse(pos=(-500, -500), size=(200, 200))

            # NUAGE
            self._cloud_c     = Color(0.94, 0.96, 1.00, 0)
            self._cloud_parts = [Ellipse(pos=(-500, -500), size=(80, 80))
                                 for _ in _CLOUD_LAYOUT]

            # ORAGE
            self._storm_c    = Color(0.28, 0.28, 0.35, 0)
            self._storm_head = RoundedRectangle(pos=(-500, -500),
                                               size=(100, 100), radius=[18])

            # NEIGE
            self._snow_head_c = Color(0.85, 0.94, 1.00, 0)
            self._snow_head   = Ellipse(pos=(-500, -500), size=(200, 200))
            self._ice_c       = Color(0.72, 0.90, 1.00, 0)
            self._icicles     = [Line(points=[0, 0, 0, 0], width=3.5, cap="round")
                                 for _ in range(N_ICICLE)]

            # Reflet
            self._hl_c = Color(1, 1, 1, 0)
            self._hl   = Ellipse(pos=(-500, -500), size=(80, 20))

            # Yeux
            self._eye_c  = Color(0.04, 0.07, 0.22, 0)
            self._leye   = Ellipse(pos=(-500, -500), size=(60, 60))
            self._reye   = Ellipse(pos=(-500, -500), size=(60, 60))
            self._iris_c = Color(0.09, 0.15, 0.42, 0)
            self._liris  = Ellipse(pos=(-500, -500), size=(34, 34))
            self._riris  = Ellipse(pos=(-500, -500), size=(34, 34))
            self._cl_c   = Color(1, 1, 1, 0)
            self._lcl    = Ellipse(pos=(-500, -500), size=(15, 15))
            self._rcl    = Ellipse(pos=(-500, -500), size=(15, 15))
            self._cl2_c  = Color(1, 1, 1, 0)
            self._lcl2   = Ellipse(pos=(-500, -500), size=(7, 7))
            self._rcl2   = Ellipse(pos=(-500, -500), size=(7, 7))

            # Paupières
            self._lid_c = Color(0.96, 0.96, 0.97, 0)
            self._llid  = Rectangle(pos=(0, 0), size=(64, 40))
            self._rlid  = Rectangle(pos=(0, 0), size=(64, 40))

            # Arcs D / reverse-D / curious
            self._darc_c = Color(0.04, 0.07, 0.22, 0)
            self._ldarcL = Line(ellipse=(0, 0, 60, 50, -90, 90), width=8)
            self._rdarcL = Line(ellipse=(0, 0, 60, 50, -90, 90), width=8)
            self._rarc_c = Color(0.04, 0.07, 0.22, 0)
            self._lrarcL = Line(ellipse=(0, 0, 60, 50, 90, 270), width=8)
            self._rrarcL = Line(ellipse=(0, 0, 60, 50, 90, 270), width=8)
            self._iarc_c = Color(0.04, 0.07, 0.22, 0)
            self._liarcL = Line(ellipse=(0, 0, 60, 50, -90,  90), width=8)
            self._riarcL = Line(ellipse=(0, 0, 60, 50,  90, 270), width=8)

            # Sourcils
            self._ang_c = Color(0.04, 0.07, 0.22, 0)
            self._lang  = Line(points=[0, 0, 0, 0], width=5, cap="round")
            self._rang  = Line(points=[0, 0, 0, 0], width=5, cap="round")

            # Étoiles
            self._star_c = Color(1.0, 0.85, 0.1, 0)
            self._lstar  = Line(points=[0, 0], width=3, joint="miter")
            self._rstar  = Line(points=[0, 0], width=3, joint="miter")

            # Barres
            self._bar_c = Color(0.04, 0.07, 0.22, 0)
            self._lbar  = Line(points=[0, 0, 0, 0], width=8, cap="round")
            self._rbar  = Line(points=[0, 0, 0, 0], width=8, cap="round")

            # Bouche
            self._mhp_c  = Color(0.08, 0.06, 0.16, 0)
            self._mhp    = Line(points=[0, 0], width=4.5, joint="round", cap="round")
            self._msd_c  = Color(0.08, 0.06, 0.16, 0)
            self._msd    = Line(points=[0, 0], width=4.0, joint="round", cap="round")
            self._msp_c  = Color(0.08, 0.06, 0.16, 0)
            self._msp    = Ellipse(pos=(0, 0), size=(26, 22))
            self._mfl_c  = Color(0.14, 0.12, 0.20, 0)
            self._mfl    = Line(points=[0, 0, 0, 0], width=3, cap="round")
            self._mspk_c = Color(0.08, 0.06, 0.16, 0)
            self._mspk   = Ellipse(pos=(0, 0), size=(20, 10))

            # "?"
            _ql = CoreLabel(text="?", font_size=90, bold=True,
                            color=(0.08, 0.08, 0.20, 1))
            _ql.refresh()
            self._qmark_c   = Color(0.08, 0.08, 0.20, 0)
            self._qmark_tex = _ql.texture
            self._qmark_r   = Rectangle(texture=self._qmark_tex,
                                        pos=(0, 0), size=self._qmark_tex.size)

            PopMatrix()

            # Météo premier plan
            self._snowfall_c = Color(0.88, 0.96, 1.0, 0)
            self._flakes     = [Ellipse(pos=(0, 0), size=(7, 7))
                                for _ in range(N_SNOW)]
            self._bolt_c = Color(1.0, 1.0, 0.2, 0)
            self._bolt   = Line(points=[0, 0, 0, 0], width=3.5, joint="miter")

    # ── Resize ────────────────────────────────────────────────────────────────
    def _on_resize(self, *_):
        W, H = self.width, self.height
        self._bg.size = (W, H)
        if W < MIN_WIDGET_SIZE or H < MIN_WIDGET_SIZE: return
        if not self._centered:
            self.face_cx = self._tgt_cx = W * 0.5
            self.face_cy = self._tgt_cy = H * 0.5
            self._jump_base = H * 0.5
            self._centered = True

    # ── API ───────────────────────────────────────────────────────────────────
    def set_expression(self, name: str):
        self._expression = name; self._idle_t = 0.0

    def set_eye_type(self, t: str): self._eye_type = t

    def set_head_color(self, r, g, b, dur: float = 0.7):
        self._tr, self._tg, self._tb = r, g, b
        if dur <= 0: self._hr, self._hg, self._hb = r, g, b

    def set_weather(self, w: Optional[str]):
        w = None if w in (None, "none") else w
        if w == self._weather: return
        self._weather = w
        w_key = w or "neutral"
        for k in self._shape_alpha:
            v = 1.0 if k == w_key else 0.0
            self._shape_alpha[k]  = v
            self._shape_target[k] = v

    def _safe_jump_v0(self) -> float:
        """Vitesse initiale max pour rester dans l'écran."""
        fh = self.height * 0.46
        headroom = max(20.0, self.height - self.face_cy - fh * 0.5 - 12)
        return min(JUMP_V0, math.sqrt(2.0 * GRAVITY * headroom))

    def animate_jump(self):
        if self._jump_vy != 0.0: return
        self._jump_base = self.face_cy
        self._jump_vy   = self._safe_jump_v0()

    def animate_spin(self):
        self._cancel("spin")
        def upd(t):
            self._scale_x = 1.0 - 2.0 * t if t < 0.5 else (t - 0.5) * 2.0
        self._run(_Anim(0.45, upd,
                        lambda: setattr(self, "_scale_x", 1.0), tag="spin"))

    def animate_flip(self, _side: str = "right"):
        self.animate_spin()

    def animate_flip_vertical(self):
        self._cancel("flip_v")
        def upd(t):
            self._scale_y = abs(math.cos(t * PI))
        self._run(_Anim(0.5, upd,
                        lambda: setattr(self, "_scale_y", 1.0), tag="flip_v"))

    def animate_roll(self):
        self._cancel("roll")
        def upd(t): self._face_angle = 360.0 * t
        def done():  self._face_angle = 0.0
        self._run(_Anim(0.75, upd, done, _ease_inout, tag="roll"))

    def animate_somersault(self):
        self._cancel("somersault")
        base = self._jump_base = self.face_cy
        fh   = self.height * 0.58
        h    = max(20.0, self.height - base - fh * 0.5 - 12)
        def upd(t):
            self.face_cy  = base + h * math.sin(t * PI)
            self._tgt_cy  = self.face_cy
            self._scale_y = abs(math.cos(t * PI * 2))
        def done():
            self.face_cy = base; self._tgt_cy = base; self._scale_y = 1.0
        self._run(_Anim(0.9, upd, done, _ease_inout, tag="somersault"))

    def animate_backflip(self):
        self._cancel("backflip")
        base = self._jump_base = self.face_cy
        fh   = self.height * 0.58
        h    = max(20.0, self.height - base - fh * 0.5 - 12)
        def upd(t):
            self.face_cy     = base + h * math.sin(t * PI)
            self._tgt_cy     = self.face_cy
            self._face_angle = -360.0 * t
        def done():
            self.face_cy = base; self._tgt_cy = base; self._face_angle = 0.0
        self._run(_Anim(0.85, upd, done, _ease_inout, tag="backflip"))

    def animate_shake(self, amp: float = 14.0, dur: float = 0.55):
        self._cancel("shake")
        def upd(t):
            self._shake_x = amp * math.sin(t * PI * 7) * (1.0 - t)
        self._run(_Anim(dur, upd,
                        lambda: setattr(self, "_shake_x", 0.0), tag="shake"))

    def animate_excited(self):
        self._cancel("excited")
        def upd(t):
            p = math.sin(t * PI)
            self._scale_x = 1.0 + 0.20 * p; self._scale_y = 1.0 + 0.20 * p
        def done(): self._scale_x = self._scale_y = 1.0
        self._run(_Anim(0.65, upd, done, _ease_inout, "excited"))
        self.animate_shake(7.0, 0.65)

    def animate_nod(self):
        self._cancel("nod")
        def upd(t):
            self._nod_y = 22.0 * math.sin(t * PI * 2) * (1.0 - t)
        self._run(_Anim(0.6, upd,
                        lambda: setattr(self, "_nod_y", 0.0), tag="nod"))

    def animate_peek(self, side: str = "right"):
        self._cancel("peek"); self._cancel("wander")
        W = self.width; fw = W * 0.42
        saved_cx = self._tgt_cx; saved_cy = self._tgt_cy
        edge_cx = (W - fw * 0.28) if side == "right" else fw * 0.28
        tilt    = -18.0 if side == "right" else 18.0
        def slide_in(t):
            p = _lerp(saved_cx, edge_cx, _ease_out_quad(t))
            self.face_cx = p; self._tgt_cx = p
            self._tgt_face_angle = tilt * _ease_out_quad(t)
        def peek_done():
            Clock.schedule_once(lambda _: self._peek_return(saved_cx, saved_cy), 2.2)
        self._run(_Anim(0.55, slide_in, peek_done, tag="peek"))

    def _peek_return(self, sx, sy):
        self._cancel("peek_back")
        cur_cx = self.face_cx; cur_angle = self._face_angle
        def slide_back(t):
            p = _lerp(cur_cx, sx, _ease_inout(t))
            self.face_cx = p; self._tgt_cx = p
            self._tgt_face_angle = cur_angle * (1.0 - t)
        def done():
            self._tgt_face_angle = 0.0; self._tgt_cx = sx; self._tgt_cy = sy
        self._run(_Anim(0.55, slide_back, done, tag="peek_back"))

    def speak(self, active: bool): self._speaking = bool(active)

    def look_at(self, nx: float, ny: float = 0.0, hold: float = 2.0):
        self._tgt_gx = _clamp(nx, -1, 1); self._tgt_gy = _clamp(ny, -1, 1)
        self._wander_hold = max(self._wander_hold, hold)

    def set_state(self, s: str, _lv: float = 0.0):
        self.set_expression(self._STATE_MAP.get(s, "neutral"))
        self.set_head_color(*self._STATE_COLOR.get(s, (0.96, 0.96, 0.97)))

    def pause(self):
        """Suspend toutes les animations (pendant chargement modèle)."""
        if self._ev_tick:
            self._ev_tick.cancel(); self._ev_tick = None
        if self._ev_gaze:
            self._ev_gaze.cancel(); self._ev_gaze = None

    def resume(self):
        """Reprend les animations après chargement."""
        if self._ev_tick is None:
            self._ev_tick = Clock.schedule_interval(self._tick,        1.0 / 30.0)
        if self._ev_gaze is None:
            self._ev_gaze = Clock.schedule_interval(self._random_gaze, 2.4)

    # ── Moteur anim ───────────────────────────────────────────────────────────
    def _run(self, anim: _Anim): self._anims.append(anim)
    def _cancel(self, tag: str):
        for a in self._anims:
            if a.tag == tag: a.cancelled = True

    # ── Tick ──────────────────────────────────────────────────────────────────
    def _tick(self, dt: float):
        real_dt = dt
        dt = min(dt, MAX_DT)
        self._t += dt; self._breath += dt; self._idle_t += dt
        self._tick_anims(real_dt)
        self._tick_blink(dt); self._tick_motion(dt); self._tick_weather(dt)
        if self._idle_t > IDLE_TIMEOUT and self._blink_phase == "wait":
            self._idle_behavior()
        self._draw()

    def _tick_anims(self, dt: float):
        for a in list(self._anims):
            if not a.cancelled and not a.finished: a.tick(dt)
        self._anims = [a for a in self._anims
                       if not a.cancelled and not a.finished]

    def _tick_blink(self, dt: float):
        p = self._blink_phase
        if p == "wait":
            self._blink_timer -= dt
            if self._blink_timer <= 0: self._blink_phase = "closing"
        elif p == "closing":
            self._blink -= dt / BLINK_CLOSE_T
            if self._blink <= 0:
                self._blink = 0.0; self._blink_phase = "hold"
                self._blink_timer = BLINK_HOLD_T
        elif p == "hold":
            self._blink_timer -= dt
            if self._blink_timer <= 0: self._blink_phase = "opening"
        else:
            self._blink += dt / BLINK_CLOSE_T
            if self._blink >= 1.0:
                self._blink = 1.0; self._blink_phase = "wait"
                self._blink_timer = random.uniform(BLINK_WAIT_MIN, BLINK_WAIT_MAX)

    def _tick_motion(self, dt: float):
        self._hr = _smooth(self._hr, self._tr, RATE_COLOR, dt)
        self._hg = _smooth(self._hg, self._tg, RATE_COLOR, dt)
        self._hb = _smooth(self._hb, self._tb, RATE_COLOR, dt)
        self._gaze_x = _smooth(self._gaze_x, self._tgt_gx, RATE_GAZE, dt)
        self._gaze_y = _smooth(self._gaze_y, self._tgt_gy, RATE_GAZE, dt)
        self._face_angle = _smooth(self._face_angle, self._tgt_face_angle,
                                   RATE_ANGLE, dt)

        if self._wander_hold > 0:
            self._wander_hold -= dt
        else:
            self._wander_t -= dt
            if self._wander_t <= 0:
                fw = self.width * 0.42; fh = self.height * 0.46; mg = 30
                self._tgt_cx = random.uniform(fw / 2 + mg, self.width  - fw / 2 - mg)
                cy_max = self.height - fh / 2 - mg - 90
                self._tgt_cy = random.uniform(fh / 2 + mg, max(fh / 2 + mg, cy_max))
                self._wander_t = random.uniform(WANDER_MIN, WANDER_MAX)
        step = HEAD_SPEED * dt
        for attr, tgt in (("face_cx", self._tgt_cx), ("face_cy", self._tgt_cy)):
            cur = getattr(self, attr); d = tgt - cur
            setattr(self, attr, tgt if abs(d) <= step else cur + math.copysign(step, d))

        if self._jump_vy != 0.0:
            self._jump_vy -= GRAVITY * dt
            self.face_cy += self._jump_vy * dt; self._tgt_cy = self.face_cy
            if self.face_cy <= self._jump_base:
                self.face_cy = self._jump_base; self._tgt_cy = self._jump_base
                self._jump_vy = 0.0
        if self._speaking: self._speak_t += dt * 9.0

    def _idle_behavior(self):
        self._idle_t = 0.0; r = random.random()
        if r < 0.30:
            self.set_expression("surprised")
            def _after(_):
                self.set_expression("tired")
                Clock.schedule_once(lambda _: self.set_expression("neutral"), 2.0)
            Clock.schedule_once(_after, 0.8)
        elif r < 0.50: self.animate_shake(4.0, 0.4)
        elif r < 0.65: self.animate_nod()
        elif r < 0.80: self.animate_peek(random.choice(["left", "right"]))
        elif r < 0.90: self.animate_flip_vertical()
        else:          self.animate_roll()

    # ── Météo ─────────────────────────────────────────────────────────────────
    def _tick_weather(self, dt: float):
        tgt = 1.0 if self._weather else 0.0
        self._weather_a = _smooth(self._weather_a, tgt, RATE_SHAPE, dt)

        w = self._weather
        if w == "snow":
            for i in range(N_SNOW):
                self._snow_y[i] -= (35.0 + i * 4.0) * dt
                self._snow_x[i] += math.sin(self._t * 0.7 + i * 1.3) * 0.6
                if self._snow_y[i] < -10:
                    self._snow_y[i] = self.height + 10
                    self._snow_x[i] = random.uniform(40, self.width - 40)
                self._snow_x[i] = _clamp(self._snow_x[i], 40, self.width - 40)
        if w == "sun":
            for i in range(N_RAYS):
                self._ray_ang[i] = (self._ray_ang[i] + 14.0 * dt) % 360.0
        if (w == "storm" and self._bolt_t <= 0
                and random.random() < dt * WEATHER_BOLT_P):
            self._bolt_t = 0.10
            lx = self.face_cx + random.uniform(-30, 30)
            fh = self.height * 0.46; cy = self.face_cy
            self._bolt_pts = [lx, cy + fh * 0.65,
                              lx - 10, cy + fh * 0.25,
                              lx + 8,  cy + fh * 0.20,
                              lx - 12, cy - fh * 0.35]
        if self._bolt_t > 0: self._bolt_t -= dt

    # ── Draw ──────────────────────────────────────────────────────────────────
    def _draw(self):
        W, H = self.width, self.height
        if W < MIN_WIDGET_SIZE or H < MIN_WIDGET_SIZE: return
        self._bg.size = (W, H)

        cx = self.face_cx + self._shake_x
        cy = self.face_cy + self._nod_y
        self._face_rot.angle  = self._face_angle
        self._face_rot.origin = (cx, cy)

        pulse = 0.5 + 0.5 * math.sin(self._breath * 1.1)
        fw = (W * 0.42 + pulse * 2.0) * _clamp(self._scale_x, 0.001, 2.5)
        fh = (H * 0.46 + pulse * 1.5) * _clamp(self._scale_y, 0.001, 2.5)

        em = self._expression
        if em == "surprised": fw *= 1.12; fh *= 1.12
        elif em == "excited": fw *= 1.08; fh *= 1.08

        self._draw_rays(cx, cy, fw, fh)
        self._draw_head(cx, cy, fw, fh)
        self._draw_eyes(cx, cy, fw, fh)
        self._draw_mouth(cx, cy, fw, fh)
        self._draw_weather_fg()

    # ── Rayons ────────────────────────────────────────────────────────────────
    def _draw_rays(self, cx, cy, fw, fh):
        em = self._expression
        ray_a = (self._shape_alpha["sun"] * self._weather_a
                 if self._weather == "sun"
                 else (0.7 if em == "surprised" else 0.0))
        self._ray_c.a = ray_a
        if ray_a > 0.01:
            for i, ray in enumerate(self._rays):
                ang = math.radians(self._ray_ang[i])
                r0  = max(fw, fh) * 0.56
                r1  = r0 + 28.0 + 9.0 * math.sin(self._t * 2 + i)
                ray.points = [cx + r0 * math.cos(ang), cy + r0 * math.sin(ang),
                              cx + r1 * math.cos(ang), cy + r1 * math.sin(ang)]

    # ── Formes de la tête ─────────────────────────────────────────────────────
    def _draw_head(self, cx, cy, fw, fh):
        fx = cx - fw * 0.5; fy = cy - fh * 0.5
        sa = self._shape_alpha
        a_neu = sa["neutral"]; a_sun  = sa["sun"]
        a_cloud = sa["cloud"]; a_storm = sa["storm"]; a_snow = sa["snow"]

        # Ombre interpolée selon la forme dominante
        total = a_neu + a_sun + a_cloud + a_storm + a_snow
        if total > 0.001:
            sh_w = (a_neu * fw + a_sun * max(fw, fh) * 0.92 +
                    a_cloud * fw * CLOUD_W + a_storm * fw * 0.92 +
                    a_snow  * fw * 0.96) / total
            sh_h = (a_neu * fh + a_sun * max(fw, fh) * 0.92 +
                    a_cloud * fh * CLOUD_H * 0.72 + a_storm * fh * 0.94 +
                    a_snow  * fh * 1.02) / total
        else:
            sh_w, sh_h = fw, fh
        self._shadow_c.a  = 0.18 * min(total, 1.0)
        self._shadow.pos  = (cx - sh_w * 0.5 + 8, cy - sh_h * 0.5 - 10)
        self._shadow.size = (sh_w, sh_h)

        # NEUTRE
        rad_top = int(fh * 0.42); rad_bot = int(fh * 0.26)
        self._head_c.rgba = (self._hr, self._hg, self._hb, a_neu)
        self._head.pos    = (fx, fy)
        self._head.size   = (fw, fh)
        self._head.radius = [rad_top, rad_top, rad_bot, rad_bot]

        # SOLEIL
        sd = max(fw, fh) * 0.92
        self._sun_c.rgba    = (1.0, 0.90, 0.25, a_sun)
        self._sun_body.pos  = (cx - sd / 2, cy - sd / 2)
        self._sun_body.size = (sd, sd)

        # NUAGE
        self._cloud_c.a = a_cloud
        for i, (xf, yf, rwf, rhf) in enumerate(_CLOUD_LAYOUT):
            rw = fw * rwf; rh = fh * rhf
            self._cloud_parts[i].pos  = (cx + fw * xf - rw / 2,
                                         cy + fh * yf - rh / 2)
            self._cloud_parts[i].size = (rw, rh)

        # ORAGE
        self._storm_c.a         = a_storm
        self._storm_head.pos    = (fx + fw * 0.04, fy + fh * 0.03)
        self._storm_head.size   = (fw * 0.92, fh * 0.94)
        self._storm_head.radius = [int(fh * 0.08)]

        # NEIGE
        nw = fw * 0.96; nh = fh * 1.02
        self._snow_head_c.a  = a_snow
        self._snow_head.pos  = (cx - nw / 2, cy - nh / 2)
        self._snow_head.size = (nw, nh)
        self._ice_c.a        = a_snow * 0.90
        for i, ic in enumerate(self._icicles):
            ix = fx + fw * (0.10 + i * (0.80 / (N_ICICLE - 1)))
            iy = fy - fh * 0.02
            il = fh * (0.06 + 0.04 * math.sin(i * 1.7 + self._t * 0.5))
            ic.points = [ix, iy, ix, iy - il]

        # Reflet
        hl_a = max(a_neu, a_sun * 0.8, a_cloud * 0.7, a_snow * 0.8)
        hl_w = fw * 0.72; hl_h = fh * 0.18
        self._hl_c.a  = 0.36 * hl_a
        self._hl.pos  = (cx - hl_w / 2, cy + fh * 0.24)
        self._hl.size = (hl_w, hl_h)

    # ── Yeux ──────────────────────────────────────────────────────────────────
    def _draw_eyes(self, cx, cy, fw, fh):
        ew = fw * 0.148; eh = fh * 0.215
        e_sep = fw * 0.248; eye_y = cy - fh * 0.08
        b = self._blink
        gx = self._gaze_x * ew * 0.28; gy = self._gaze_y * eh * 0.15
        ex_l = cx - e_sep + gx; ey_l = eye_y + gy
        ex_r = cx + e_sep + gx; ey_r = eye_y + gy
        em = self._expression

        for c in (self._eye_c, self._iris_c, self._cl_c, self._cl2_c,
                  self._lid_c, self._darc_c, self._rarc_c, self._iarc_c,
                  self._ang_c, self._star_c, self._bar_c):
            c.a = 0

        # Couleur des yeux selon forme active
        sa = self._shape_alpha
        ec = (0.04, 0.07, 0.22)
        if sa["storm"] > 0:
            ec = (_lerp(ec[0], 0.60, sa["storm"]),
                  _lerp(ec[1], 0.80, sa["storm"]),
                  _lerp(ec[2], 1.00, sa["storm"]))
        elif sa["sun"] > 0:
            ec = (_lerp(ec[0], 0.38, sa["sun"]),
                  _lerp(ec[1], 0.22, sa["sun"]),
                  _lerp(ec[2], 0.04, sa["sun"]))
        elif sa["snow"] > 0:
            ec = (_lerp(ec[0], 0.10, sa["snow"]),
                  _lerp(ec[1], 0.28, sa["snow"]),
                  _lerp(ec[2], 0.55, sa["snow"]))
        elif sa["cloud"] > 0:
            ec = (_lerp(ec[0], 0.22, sa["cloud"]),
                  _lerp(ec[1], 0.30, sa["cloud"]),
                  _lerp(ec[2], 0.50, sa["cloud"]))

        eye_t = self._eye_type
        if em == "excited": eye_t = "stars"

        if eye_t == "stars":
            self._star_c.rgba = (ec[0] + 0.9, ec[1] + 0.75, 0.1, b)
            ro = max(ew * 0.46, 5.0)
            self._lstar.points = _scale_pts(_STAR_UNIT, ex_l, ey_l, ro)
            self._rstar.points = _scale_pts(_STAR_UNIT, ex_r, ey_r, ro)
            return
        if eye_t == "bars":
            self._bar_c.rgba = (*ec, b)
            hw = ew * 0.46
            self._lbar.points = [ex_l - hw, ey_l, ex_l + hw, ey_l]
            self._rbar.points = [ex_r - hw, ey_r, ex_r + hw, ey_r]
            return
        if eye_t == "dots":
            rs = max(ew * 0.24, 5.0)
            self._eye_c.rgba = (*ec, b)
            self._leye.pos  = (ex_l - rs / 2, ey_l - rs / 2); self._leye.size = (rs, rs)
            self._reye.pos  = (ex_r - rs / 2, ey_r - rs / 2); self._reye.size = (rs, rs)
            return

        if em in ("happy", "laughing", "love"):
            ah = max(eh * 0.72 * b, 2)
            self._darc_c.rgba = (*ec, b)
            self._ldarcL.ellipse = (ex_l - ew / 2, ey_l - ah / 2, ew, ah, -90, 90)
            self._rdarcL.ellipse = (ex_r - ew / 2, ey_r - ah / 2, ew, ah, -90, 90)
        elif em == "sad":
            ah = max(eh * 0.68 * b, 2)
            self._rarc_c.rgba = (*ec, b)
            self._lrarcL.ellipse = (ex_l - ew / 2, ey_l - ah / 2, ew, ah, 90, 270)
            self._rrarcL.ellipse = (ex_r - ew / 2, ey_r - ah / 2, ew, ah, 90, 270)
        elif em == "curious":
            ah = max(eh * b, 2)
            self._iarc_c.rgba = (*ec, b)
            self._liarcL.ellipse = (ex_l - ew / 2, ey_l - ah / 2, ew, ah, -90,  90)
            self._riarcL.ellipse = (ex_r - ew / 2, ey_r - ah / 2, ew, ah,  90, 270)
        elif em in ("tired", "worried"):
            hh = max(eh * 0.44 * b, 2)
            lo = eh * 0.10 if em == "worried" else 0.0
            ro = -eh * 0.10 if em == "worried" else 0.0
            self._eye_c.rgba = (*ec, b)
            self._leye.pos = (ex_l - ew / 2, ey_l + lo - hh / 2); self._leye.size = (ew, hh)
            self._reye.pos = (ex_r - ew / 2, ey_r + ro - hh / 2); self._reye.size = (ew, hh)
            self._lid_c.a = 1; self._lid_c.rgb = (self._hr, self._hg, self._hb)
            self._llid.pos = (ex_l - ew / 2 - 2, ey_l + lo); self._llid.size = (ew + 4, eh + 8)
            self._rlid.pos = (ex_r - ew / 2 - 2, ey_r + ro); self._rlid.size = (ew + 4, eh + 8)
        elif em == "surprised":
            sw = ew * 1.25; sh = max(eh * 1.35 * b, 2)
            self._eye_c.rgba = (*ec, 1)
            self._leye.pos = (ex_l - sw / 2, ey_l - sh / 2); self._leye.size = (sw, sh)
            self._reye.pos = (ex_r - sw / 2, ey_r - sh / 2); self._reye.size = (sw, sh)
            iw = sw * 0.54; ih = sh * 0.54
            self._iris_c.rgba = (*ec, 0.55)
            self._liris.pos = (ex_l - iw / 2, ey_l - ih / 2); self._liris.size = (iw, ih)
            self._riris.pos = (ex_r - iw / 2, ey_r - ih / 2); self._riris.size = (iw, ih)
            self._set_cl(ex_l, ey_l, ex_r, ey_r, sw, sh, b)
        elif em == "angry":
            cw = ew; ch = max(eh * b, 2)
            self._eye_c.rgba = (*ec, b)
            self._leye.pos = (ex_l - cw / 2, ey_l - ch / 2); self._leye.size = (cw, ch)
            self._reye.pos = (ex_r - cw / 2, ey_r - ch / 2); self._reye.size = (cw, ch)
            self._ang_c.rgba = (*ec, b)
            bw = ew * 0.62
            self._lang.points = [ex_l - bw, ey_l + ch * 0.44, ex_l + bw, ey_l + ch * 0.66]
            self._rang.points = [ex_r - bw, ey_r + ch * 0.66, ex_r + bw, ey_r + ch * 0.44]
        elif em == "thinking":
            cw = ew; ch = max(eh * b, 2)
            self._eye_c.rgba = (*ec, 1)
            self._leye.pos  = (ex_l - cw / 2, ey_l - ch / 2); self._leye.size = (cw, ch)
            self._reye.pos  = (ex_r - cw / 2, ey_r - ch / 2); self._reye.size = (cw, ch)
            self._iris_c.rgba = (*ec, 0.55)
            up = ch * 0.14
            self._liris.pos  = (ex_l - cw * 0.29, ey_l - ch * 0.29 + up)
            self._liris.size = (cw * 0.58, ch * 0.58)
            self._riris.pos  = (ex_r - cw * 0.29, ey_r - ch * 0.29 + up)
            self._riris.size = (cw * 0.58, ch * 0.58)
            self._set_cl(ex_l, ey_l + up, ex_r, ey_r + up, cw, ch, b)
        else:
            cw = ew; ch = max(eh * b, 2)
            self._eye_c.rgba  = (*ec, 1)
            self._leye.pos  = (ex_l - cw / 2, ey_l - ch / 2); self._leye.size = (cw, ch)
            self._reye.pos  = (ex_r - cw / 2, ey_r - ch / 2); self._reye.size = (cw, ch)
            self._iris_c.rgba = (*ec, 0.55)
            self._liris.pos  = (ex_l - cw * 0.29, ey_l - ch * 0.29)
            self._liris.size = (cw * 0.58, ch * 0.58)
            self._riris.pos  = (ex_r - cw * 0.29, ey_r - ch * 0.29)
            self._riris.size = (cw * 0.58, ch * 0.58)
            self._set_cl(ex_l, ey_l, ex_r, ey_r, cw, ch, b)

        qma = 1.0 if em == "surprised" else 0.0
        self._qmark_c.a = qma * b
        if qma > 0.01:
            self._qmark_r.pos = (ex_r + ew * 0.45, eye_y + fh * 0.28)

    def _set_cl(self, elx, ely, erx, ery, cw, ch, b, cw2=None, ch2=None):
        cw2 = cw2 or cw; ch2 = ch2 or ch
        if b > 0.3:
            av  = min((b - 0.3) / 0.7, 1.0)
            cl  = max(int(cw * 0.30), 6); cl2 = max(cl // 2, 4)
            self._cl_c.a  = 0.90 * av; self._cl2_c.a = 0.35 * av
            self._lcl.size  = (cl, cl);   self._lcl.pos  = (elx - cw  / 2 + 7, ely + ch  * 0.14)
            self._rcl.size  = (cl, cl);   self._rcl.pos  = (erx - cw2 / 2 + 7, ery + ch2 * 0.14)
            self._lcl2.size = (cl2, cl2); self._lcl2.pos = (elx + cw  / 4,     ely - ch  * 0.15)
            self._rcl2.size = (cl2, cl2); self._rcl2.pos = (erx + cw2 / 4,     ery - ch2 * 0.15)
        else:
            self._cl_c.a = self._cl2_c.a = 0

    # ── Bouche ────────────────────────────────────────────────────────────────
    def _draw_mouth(self, cx, cy, fw, fh):
        ew = fw * 0.148; eh = fh * 0.215
        mouth_y = cy - fh * 0.24; em = self._expression
        self._mhp_c.a = self._msd_c.a = self._msp_c.a = 0
        self._mfl_c.a = self._mspk_c.a = 0
        if self._speaking:
            op = abs(math.sin(self._speak_t)) * 0.75 + 0.25
            mw = ew * 0.88; mh = max(eh * 0.38 * op, 4)
            self._mspk_c.a = 0.75; self._mspk.pos = (cx - mw / 2, mouth_y - mh / 2)
            self._mspk.size = (mw, mh)
        elif em in ("happy", "laughing", "love", "excited"):
            self._mhp_c.a = 0.65
            self._mhp.points = [cx - 36, mouth_y + 8, cx - 18, mouth_y - 6,
                                 cx, mouth_y - 11, cx + 18, mouth_y - 6,
                                 cx + 36, mouth_y + 8]
        elif em == "sad":
            self._msd_c.a = 0.58
            self._msd.points = [cx - 32, mouth_y - 8, cx - 16, mouth_y + 5,
                                 cx, mouth_y + 10, cx + 16, mouth_y + 5,
                                 cx + 32, mouth_y - 8]
        elif em == "surprised":
            self._msp_c.a = 0.68
            self._msp.pos = (cx - 13, mouth_y - 15); self._msp.size = (26, 24)
        elif em in ("tired", "worried", "thinking", "angry"):
            self._mfl_c.a = 0.48
            self._mfl.points = [cx - 22, mouth_y, cx + 22, mouth_y]

    # ── Météo premier plan ────────────────────────────────────────────────────
    def _draw_weather_fg(self):
        w  = self._weather; wa = self._weather_a
        self._snowfall_c.a = wa if w == "snow" else 0.0
        for i, sf in enumerate(self._flakes):
            sf.pos = (self._snow_x[i] - 3.5, self._snow_y[i] - 3.5); sf.size = (7, 7)
        self._bolt_c.a = 0.95 if (self._bolt_t > 0 and w == "storm") else 0.0
        if self._bolt_t > 0: self._bolt.points = self._bolt_pts

    # ── Regard aléatoire ──────────────────────────────────────────────────────
    def _random_gaze(self, dt):
        if self._wander_hold > 0: return
        self._tgt_gx = random.uniform(-0.9, 0.9)
        self._tgt_gy = random.uniform(-0.3, 0.3)
