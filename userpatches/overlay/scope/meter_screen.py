"""
ADNRPi Multimètre — INA219 (I2C-0, 0x40)
Mesures : Tension bus (V), Courant (A), Puissance (W)
Shunt configurable : 10mΩ / 100mΩ / 1Ω
"""
import os
import time
import threading

from strings import t

from kivy.core.window import Window
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle, Line
from kivy.clock import Clock

# ── Layout adaptatif (même logique que scope_screen) ─────────────────────────

_SCR_W = int(os.environ.get("HACKPAD_W", Window.width or 800))
_COMPACT = (_SCR_W <= 800)

if _COMPACT:
    HEADER_H  = 46
    STATUS_H  = 28
    FS_HDR    = "15sp"
    FS_VAL    = "58sp"
    FS_LABEL  = "18sp"
    FS_MINMAX = "16sp"
    FS_STATUS = "13sp"
    FS_BTN    = "14sp"
else:
    HEADER_H  = 56
    STATUS_H  = 34
    FS_HDR    = "19sp"
    FS_VAL    = "84sp"
    FS_LABEL  = "18sp"
    FS_MINMAX = "15sp"
    FS_STATUS = "14sp"
    FS_BTN    = "16sp"

# ── Palette ───────────────────────────────────────────────────────────────────

C_BG   = (0.04, 0.04, 0.04, 1)
C_HDR  = (0.07, 0.07, 0.07, 1)
C_STA  = (0.06, 0.06, 0.06, 1)
C_SEP  = (0.18, 0.18, 0.18, 1)
C_TEXT = (0.78, 0.78, 0.78, 1)
C_V    = (0.20, 0.85, 1.00, 1)   # tension : cyan
C_I    = (1.00, 0.95, 0.30, 1)   # courant : jaune
C_P    = (0.20, 1.00, 0.40, 1)   # puissance : vert
C_BTN  = (0.20, 0.20, 0.20, 1)
C_ON   = (0.18, 0.50, 0.18, 1)
C_WARN = (0.80, 0.40, 0.10, 1)

SHUNT_OPTS = [0.010, 0.100, 1.000]   # Ω

# ── Helpers ───────────────────────────────────────────────────────────────────

def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos =lambda *a: setattr(rect, "pos",  widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )

def _sep_line(widget):
    with widget.canvas.after:
        Color(*C_SEP)
        line = Line(points=[widget.x, widget.y, widget.x + widget.width, widget.y], width=1)
    widget.bind(
        pos =lambda *a: setattr(line, "points",
                                [widget.x, widget.y, widget.x + widget.width, widget.y]),
        size=lambda *a: setattr(line, "points",
                                [widget.x, widget.y, widget.x + widget.width, widget.y]),
    )

# ── Backend INA219 ────────────────────────────────────────────────────────────

class INA219Capture:
    """Lecture INA219 via smbus2 sur I2C-0 (adresse 0x40 par défaut)."""

    ADDR = 0x40
    REG_CONFIG  = 0x00
    REG_SHUNT   = 0x01
    REG_BUS     = 0x02
    REG_CURRENT = 0x04
    REG_CALIB   = 0x05

    # 16V range, ±320mV shunt, 12-bit ADC, mode continu
    _CONFIG = 0x399F

    def __init__(self, shunt_ohm=0.1, i2c_bus=0):
        self.shunt_ohm = shunt_ohm
        self._lock     = threading.Lock()
        self._running  = False
        self.v_bus = self.current = self.power = self.v_shunt = 0.0
        self.error = None
        self._bus  = None

        try:
            import smbus2
            self._bus = smbus2.SMBus(i2c_bus)
            self._configure()
        except Exception as e:
            self.error = str(e)

    def _wr(self, reg, val):
        self._bus.write_i2c_block_data(self.ADDR, reg, [(val >> 8) & 0xFF, val & 0xFF])

    def _rd(self, reg):
        d = self._bus.read_i2c_block_data(self.ADDR, reg, 2)
        return (d[0] << 8) | d[1]

    def _configure(self):
        self._wr(self.REG_CONFIG, self._CONFIG)
        # current_lsb = 1 mA, calibration = 0.04096 / (lsb * shunt)
        self._ilsb = 0.001
        cal = int(0.04096 / (self._ilsb * self.shunt_ohm))
        self._wr(self.REG_CALIB, cal)

    @property
    def ok(self):
        return self._bus is not None and self.error is None

    def _read_once(self):
        raw_bus   = self._rd(self.REG_BUS)
        raw_shunt = self._rd(self.REG_SHUNT)
        raw_cur   = self._rd(self.REG_CURRENT)

        v_bus   = ((raw_bus >> 3) * 4) / 1000.0
        v_shunt = (raw_shunt if raw_shunt < 32768 else raw_shunt - 65536) * 1e-5
        current = (raw_cur  if raw_cur  < 32768 else raw_cur  - 65536) * self._ilsb
        power   = v_bus * current

        with self._lock:
            self.v_bus    = v_bus
            self.v_shunt  = v_shunt
            self.current  = current
            self.power    = power

    def _loop(self):
        while self._running:
            try:
                self._read_once()
            except Exception as e:
                self.error = str(e)
            time.sleep(0.5)

    def start(self):
        if not self.ok: return
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def get(self):
        with self._lock:
            return self.v_bus, self.current, self.power, self.v_shunt


class DummyINA219:
    """Simulation pour test sans matériel."""

    def __init__(self, shunt_ohm=0.1):
        self.shunt_ohm = shunt_ohm
        self.ok    = True
        self.error = None

    def start(self): pass
    def stop(self):  pass

    def get(self):
        import math
        t = time.time()
        v = 12.0 + 0.5 * math.sin(t * 0.3)
        i = 1.20 + 0.3 * math.sin(t * 0.7 + 1.0)
        p = v * abs(i)
        vs = i * self.shunt_ohm
        return v, i, p, vs


# ── MeterScreen ───────────────────────────────────────────────────────────────

class MeterScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)
        import settings_manager as SM
        self._SM    = SM
        SM.load()
        self._shunt = SM.get("shunt_ohm", 0.100)
        self._meter = None
        self._running = True
        self._v_min = self._v_max = None
        self._i_min = self._i_max = None
        self._p_min = self._p_max = None
        self._wh    = 0.0

        root = BoxLayout(orientation="vertical", spacing=0)
        _bg(root, C_BG)
        root.add_widget(Widget(size_hint=(1, None), height=4))
        root.add_widget(self._build_header())
        root.add_widget(self._build_body())
        root.add_widget(self._build_status())
        self.add_widget(root)

        self._init_meter()
        Clock.schedule_interval(self._tick, 0.5)

    # ── Header ────────────────────────────────────────────────────────────────

    def _build_header(self):
        hdr = BoxLayout(size_hint=(1, None), height=HEADER_H,
                        padding=[8, 5], spacing=6)
        _bg(hdr, C_HDR)

        self._lbl_src = Label(text="INA219", font_size=FS_HDR,
                               color=C_P, bold=True,
                               size_hint=(None, 1), width=72,
                               halign="center", valign="middle")
        self._lbl_src.bind(size=lambda w, s: setattr(w, "text_size", s))

        self._lbl_info = Label(text=t("searching"), font_size="12sp",
                                color=C_TEXT, size_hint=(1, 1),
                                halign="left", valign="middle",
                                shorten=True, shorten_from="right")
        self._lbl_info.bind(size=lambda w, s: setattr(w, "text_size", s))

        # Sélection shunt
        shunt_box = BoxLayout(size_hint=(None, 1), width=174, spacing=4)
        self._shunt_btns = []
        for r in SHUNT_OPTS:
            lbl = f"{int(r*1000)}m" if r < 1 else "1ohm"
            b = Button(text=lbl, font_size="12sp",
                       background_normal="",
                       background_color=C_ON if r == self._shunt else C_BTN,
                       size_hint=(1, 1))
            b.bind(on_press=lambda _, rv=r: self._set_shunt(rv))
            shunt_box.add_widget(b)
            self._shunt_btns.append((b, r))

        btn_rst = Button(text="RST", font_size=FS_BTN,
                          background_normal="", background_color=C_WARN,
                          size_hint=(None, 1), width=44)
        btn_rst.bind(on_press=self._reset_minmax)

        btn_menu = Button(text="Menu", font_size=FS_BTN, bold=True,
                          background_normal="",
                          background_color=(0.20, 0.20, 0.32, 1),
                          size_hint=(None, 1), width=70)
        btn_menu.bind(on_press=self._open_menu)

        for w in (self._lbl_src, self._lbl_info, shunt_box, btn_rst, btn_menu):
            hdr.add_widget(w)
        return hdr

    # ── Body (3 rangées V / I / P) ────────────────────────────────────────────

    def _build_body(self):
        body = BoxLayout(orientation="vertical", size_hint=(1, 1), spacing=0)

        self._lbl_v,  self._lbl_v_mm,  row_v = self._reading_row(C_V, "V",  t("voltage"))
        self._lbl_i,  self._lbl_i_mm,  row_i = self._reading_row(C_I, "A",  t("current"))
        self._lbl_p,  self._lbl_p_mm,  row_p = self._reading_row(C_P, "W",  t("power"))

        body.add_widget(row_v)
        body.add_widget(self._make_sep())
        body.add_widget(row_i)
        body.add_widget(self._make_sep())
        body.add_widget(row_p)
        return body

    def _reading_row(self, color, unit, name):
        # Layout vertical centré : NOM / VALEUR UNITE / MIN MAX
        row = BoxLayout(orientation="vertical", size_hint=(1, 1),
                        padding=[12, 4], spacing=2)

        lbl_name = Label(text=name, font_size=FS_LABEL, color=C_TEXT,
                         size_hint=(1, None), height=26,
                         halign="center", valign="middle")
        lbl_name.bind(size=lambda w, s: setattr(w, "text_size", s))

        # Valeur + unité sur la même ligne dans un BoxLayout horizontal
        val_row = BoxLayout(orientation="horizontal", size_hint=(1, 1))
        lbl_val = Label(text="---", font_size=FS_VAL, color=color, bold=True,
                        size_hint=(1, 1), halign="right", valign="middle")
        lbl_val.bind(size=lambda w, s: setattr(w, "text_size", s))
        lbl_unit = Label(text=unit, font_size=FS_VAL, color=color, bold=True,
                         size_hint=(None, 1), width=56,
                         halign="left", valign="middle")
        lbl_unit.bind(size=lambda w, s: setattr(w, "text_size", s))
        val_row.add_widget(lbl_val)
        val_row.add_widget(lbl_unit)

        lbl_mm = Label(text="min: ---      max: ---", font_size=FS_MINMAX,
                       color=C_TEXT, size_hint=(1, None), height=26,
                       halign="center", valign="middle")
        lbl_mm.bind(size=lambda w, s: setattr(w, "text_size", s))

        row.add_widget(lbl_name)
        row.add_widget(val_row)
        row.add_widget(lbl_mm)
        return lbl_val, lbl_mm, row

    def _make_sep(self):
        w = Widget(size_hint=(1, None), height=1)
        with w.canvas:
            Color(*C_SEP)
            rect = Rectangle(pos=w.pos, size=w.size)
        w.bind(pos =lambda *a: setattr(rect, "pos",  w.pos),
               size=lambda *a: setattr(rect, "size", w.size))
        return w

    # ── Status bar ────────────────────────────────────────────────────────────

    def _build_status(self):
        bar = BoxLayout(size_hint=(1, None), height=STATUS_H,
                        padding=[10, 4])
        _bg(bar, C_STA)
        self._lbl_raw = Label(text="Vshunt: ---   Shunt: 0.1ohm   Plage: +/-3.2A",
                               font_size=FS_STATUS, color=C_TEXT,
                               halign="left", valign="middle")
        self._lbl_raw.bind(size=lambda w, s: setattr(w, "text_size", s))
        bar.add_widget(self._lbl_raw)
        return bar

    # ── Capture ───────────────────────────────────────────────────────────────

    def _init_meter(self):
        m = INA219Capture(shunt_ohm=self._shunt)
        if m.ok:
            self._meter = m
            self._lbl_src.text  = "INA219"
            self._lbl_info.text = "@ 0x40  I2C-0  OK"
        else:
            self._meter = DummyINA219(shunt_ohm=self._shunt)
            self._lbl_src.text  = "DEMO"
            self._lbl_info.text = f"Simulation — INA219 non détecté ({m.error})"
            self._lbl_src.color = C_WARN
        self._meter.start()

    # ── Tick ──────────────────────────────────────────────────────────────────

    def _tick(self, dt):
        if not self._running or not self._meter: return
        v, i, p, vs = self._meter.get()
        self._wh += abs(p) * dt / 3600

        def _upd(val, mn, mx):
            mn = val if mn is None else min(mn, val)
            mx = val if mx is None else max(mx, val)
            return mn, mx

        self._v_min, self._v_max = _upd(v, self._v_min, self._v_max)
        self._i_min, self._i_max = _upd(i, self._i_min, self._i_max)
        self._p_min, self._p_max = _upd(p, self._p_min, self._p_max)

        def fv(x):
            return f"{x:+.3f}" if abs(x) < 100 else f"{x:+.1f}"
        def fi(x):
            return f"{x:+.4f}" if abs(x) < 10 else f"{x:+.2f}"
        def fp(x):
            return f"{x:+.3f}" if abs(x) < 100 else f"{x:+.1f}"

        self._lbl_v.text = fv(v)
        self._lbl_i.text = fi(i)
        self._lbl_p.text = fp(p)

        def mm(mn, mx, fmt):
            if mn is None: return "min: ---      max: ---"
            return f"min: {fmt(mn)}    max: {fmt(mx)}"

        self._lbl_v_mm.text = mm(self._v_min, self._v_max, lambda x: f"{x:.3f}V")
        self._lbl_i_mm.text = mm(self._i_min, self._i_max, lambda x: f"{x:.4f}A")
        self._lbl_p_mm.text = mm(self._p_min, self._p_max, lambda x: f"{x:.3f}W")

        plage = 0.320 / self._shunt
        shunt_str = (f"{int(self._shunt*1000)}mohm" if self._shunt < 1 else "1ohm")
        self._lbl_raw.text = (f"Vsh:{vs*1000:.1f}mV  "
                               f"{shunt_str}  "
                               f"+/-{plage:.0f}A  "
                               f"Wh:{self._wh:.4f}")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _set_shunt(self, r):
        self._shunt = r
        self._SM.set_val("shunt_ohm", r)
        for b, rv in self._shunt_btns:
            b.background_color = C_ON if rv == r else C_BTN
        if self._meter: self._meter.stop()
        self._reset_minmax()
        self._init_meter()

    def _reset_minmax(self, *a):
        self._v_min = self._v_max = None
        self._i_min = self._i_max = None
        self._p_min = self._p_max = None
        self._wh    = 0.0

    def _open_menu(self, *a):
        import nav_menu
        nav_menu.open_nav_menu(self)

    def on_enter(self, *a):
        self._SM.load()
        shunt_new = self._SM.get("shunt_ohm", 0.100)
        if abs(shunt_new - self._shunt) > 1e-9:
            self._shunt = shunt_new
            for b, rv in self._shunt_btns:
                b.background_color = C_ON if abs(rv - shunt_new) < 1e-9 else C_BTN
        self._running = True
        self._init_meter()
        Clock.schedule_interval(self._tick, 0.5)

    def on_leave(self, *a):
        self._running = False
        Clock.unschedule(self._tick)
        if self._meter:
            self._meter.stop()
            self._meter = None
