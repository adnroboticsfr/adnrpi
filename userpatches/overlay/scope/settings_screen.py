"""
ADNRPi Scope — Ecran de reglages
Accessible via bouton [S] dans le panel du scope.

Reglages :
  - Source par defaut (AUTO / MIC / PICO / SIM)
  - Shunt INA219 (0.01 / 0.05 / 0.10 / 0.50 / 1.00 ohm)
  - Offset ADC CH1 (calibration, +/- mV)
  - Theme (dark / blue / hicontrast)
"""
import os

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window

import settings_manager as SM
from strings import t

# ── Layout ────────────────────────────────────────────────────────────────────

_SCR_W = int(os.environ.get("HACKPAD_W", Window.width or 800))
_COMPACT = (_SCR_W <= 800)

if _COMPACT:
    HDR_H  = 46
    ROW_H  = 36
    SEP_H  = 14
    FS_HDR = "15sp"
    FS_SEC = "12sp"
    FS_BTN = "13sp"
    FS_VAL = "16sp"
    FS_PM  = "20sp"
    PAD    = 16
else:
    HDR_H  = 56
    ROW_H  = 48
    SEP_H  = 18
    FS_HDR = "19sp"
    FS_SEC = "15sp"
    FS_BTN = "16sp"
    FS_VAL = "20sp"
    FS_PM  = "26sp"
    PAD    = 24

C_BG    = (0.04, 0.04, 0.04, 1)
C_HDR   = (0.07, 0.07, 0.07, 1)
C_PANEL = (0.09, 0.09, 0.09, 1)
C_TEXT  = (0.78, 0.78, 0.78, 1)
C_SEC   = (0.45, 0.45, 0.45, 1)
C_BTN   = (0.20, 0.20, 0.20, 1)
C_ON    = (0.18, 0.50, 0.18, 1)
C_YEL   = (1.0,  0.95, 0.3,  1)

_SHUNTS  = [0.01, 0.05, 0.1, 0.5, 1.0]
_THEMES  = ["dark", "blue", "hicontrast"]
_THEME_LABELS = {"dark": "Dark", "blue": "Blue", "hicontrast": "Hi-Contrast"}


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *a: setattr(rect, "pos", widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )


def _section_label(text):
    return Label(text=text, font_size=FS_SEC, color=C_SEC,
                 size_hint=(1, None), height=SEP_H,
                 halign="left", valign="middle",
                 text_size=(_SCR_W - PAD * 2, SEP_H))


def _tog_group(options, labels, current, group, on_select, cols=None):
    """Ligne de ToggleButtons. Retourne (row, {value: button})."""
    n = len(options)
    cols = cols or n
    row = GridLayout(cols=cols, size_hint=(1, None), height=ROW_H, spacing=4)
    btns = {}
    for val, lbl in zip(options, labels):
        active = (val == current)
        b = ToggleButton(text=lbl, group=group, font_size=FS_BTN,
                         background_normal="",
                         state="down" if active else "normal",
                         background_color=C_ON if active else C_BTN)
        b.bind(on_press=lambda btn, v=val: on_select(v))
        row.add_widget(b)
        btns[val] = b
    return row, btns


class SettingsScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)
        SM.load()
        self._build()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build(self):
        root = BoxLayout(orientation="vertical")
        _bg(root, C_BG)
        root.add_widget(self._build_header())
        root.add_widget(self._build_body())
        self.add_widget(root)

    def _build_header(self):
        hdr = BoxLayout(orientation="horizontal",
                        size_hint=(1, None), height=HDR_H, padding=[8, 4], spacing=8)
        _bg(hdr, C_HDR)

        btn_menu = Button(text="Menu", font_size=FS_HDR, bold=True,
                          background_color=(0.20, 0.20, 0.32, 1),
                          background_normal="",
                          size_hint=(None, 1), width=90)
        btn_menu.bind(on_press=self._open_menu)

        title = Label(text=t("settings_title"), font_size=FS_HDR, bold=True,
                      color=C_TEXT, size_hint=(1, 1),
                      halign="center", valign="middle")

        hdr.add_widget(btn_menu)
        hdr.add_widget(title)
        return hdr

    def _build_body(self):
        body = BoxLayout(orientation="vertical",
                         size_hint=(1, 1), padding=[PAD, 12], spacing=6)
        _bg(body, C_BG)

        # ── Source par defaut ─────────────────────────────────────────────────
        body.add_widget(_section_label(t("src_label")))
        sources = ["AUTO", "MIC", "PICO", "SIM"]
        src_row, self._src_btns = _tog_group(
            sources, sources, SM.get("source"), "src_def",
            lambda v: SM.set_val("source", v))
        self._src_btns["PICO"].disabled = not os.path.exists("/dev/ttyACM0")
        body.add_widget(src_row)

        body.add_widget(Widget(size_hint=(1, None), height=6))

        # ── Shunt INA219 ──────────────────────────────────────────────────────
        body.add_widget(_section_label(t("shunt_label")))
        shunt_labels = ["0.01", "0.05", "0.10", "0.50", "1.00"]
        shunt_row, self._shunt_btns = _tog_group(
            _SHUNTS, shunt_labels, SM.get("shunt_ohm"), "shunt",
            lambda v: SM.set_val("shunt_ohm", v))
        body.add_widget(shunt_row)

        body.add_widget(Widget(size_hint=(1, None), height=6))

        # ── Offset ADC CH1 ────────────────────────────────────────────────────
        body.add_widget(_section_label(t("offset_label")))
        off_row = BoxLayout(size_hint=(1, None), height=ROW_H, spacing=4)
        self._lbl_off = Label(
            text=self._fmt_offset(), font_size=FS_VAL, color=C_YEL,
            size_hint=(1, 1), halign="center", valign="middle")
        btn_om = Button(text="-", font_size=FS_PM, bold=True,
                        size_hint=(None, 1), width=60,
                        background_color=C_BTN, background_normal="")
        btn_op = Button(text="+", font_size=FS_PM, bold=True,
                        size_hint=(None, 1), width=60,
                        background_color=C_BTN, background_normal="")
        btn_om.bind(on_press=lambda *a: self._adj_offset(-1))
        btn_op.bind(on_press=lambda *a: self._adj_offset(+1))
        btn_orst = Button(text="Reset", font_size=FS_BTN,
                          size_hint=(None, 1), width=70,
                          background_color=(0.25, 0.10, 0.10, 1),
                          background_normal="")
        btn_orst.bind(on_press=lambda *a: self._reset_offset())
        off_row.add_widget(btn_om)
        off_row.add_widget(self._lbl_off)
        off_row.add_widget(btn_op)
        off_row.add_widget(btn_orst)
        body.add_widget(off_row)

        body.add_widget(Widget(size_hint=(1, None), height=6))

        # ── Theme ─────────────────────────────────────────────────────────────
        body.add_widget(_section_label(t("theme_label")))
        theme_labels = [_THEME_LABELS[t] for t in _THEMES]
        theme_row, self._theme_btns = _tog_group(
            _THEMES, theme_labels, SM.get("theme"), "theme",
            self._set_theme)
        body.add_widget(theme_row)

        body.add_widget(Widget(size_hint=(1, None), height=6))

        # ── Langue ────────────────────────────────────────────────────────────
        body.add_widget(_section_label(t("lang_label")))
        lang_row, self._lang_btns = _tog_group(
            ["fr", "en"], ["FR", "EN"], SM.get("lang", "fr"), "lang",
            self._set_lang)
        body.add_widget(lang_row)

        body.add_widget(Widget(size_hint=(1, 1)))  # spacer bas

        # ── Changer application de démarrage ──────────────────────────────────
        sep = Label(
            text="─" * 60,
            font_size="10sp", color=(0.20, 0.20, 0.20, 1),
            size_hint=(1, None), height=14)
        body.add_widget(sep)

        change_row = BoxLayout(size_hint=(1, None), height=ROW_H, spacing=8)
        lbl_change = Label(
            text=t("startup_app_lbl"),
            font_size=FS_BTN, color=C_SEC,
            size_hint=(1, 1), halign="left", valign="middle")
        btn_change = Button(
            text=t("change"),
            font_size=FS_BTN,
            background_color=(0.30, 0.15, 0.05, 1),
            background_normal="",
            size_hint=(None, 1), width=110)
        btn_change.bind(on_press=self._change_app)
        change_row.add_widget(lbl_change)
        change_row.add_widget(btn_change)
        body.add_widget(change_row)

        # ── Infos ─────────────────────────────────────────────────────────────
        info = Label(
            text=t("app_info"),
            font_size="11sp", color=(0.25, 0.25, 0.25, 1),
            size_hint=(1, None), height=20,
            halign="center", valign="middle")
        body.add_widget(info)

        return body

    # ── Callbacks ─────────────────────────────────────────────────────────────

    def _fmt_offset(self):
        v = SM.get("adc_offset_mv", 0.0)
        return f"{v:+.1f} mV"

    def _adj_offset(self, d):
        cur = SM.get("adc_offset_mv", 0.0)
        SM.set_val("adc_offset_mv", round(cur + d * 5.0, 1))
        self._lbl_off.text = self._fmt_offset()

    def _reset_offset(self):
        SM.set_val("adc_offset_mv", 0.0)
        self._lbl_off.text = self._fmt_offset()

    def _set_lang(self, lang):
        SM.set_val("lang", lang)
        try:
            with open("/tmp/adnrpi-next", "w") as f:
                f.write("scope")
        except Exception:
            pass
        from kivy.app import App
        App.get_running_app().stop()

    def _set_theme(self, theme):
        SM.set_val("theme", theme)
        try:
            with open("/tmp/adnrpi-next", "w") as f:
                f.write("scope")
        except Exception:
            pass
        from kivy.app import App
        App.get_running_app().stop()

    def _change_app(self, *a):
        try:
            import os
            os.remove("/opt/adnrpi-launcher/startup-app")
        except Exception:
            pass
        try:
            with open("/tmp/adnrpi-next", "w") as f:
                f.write("change_app")
        except Exception:
            pass
        from kivy.app import App
        App.get_running_app().stop()

    def _open_menu(self, *a):
        import nav_menu
        nav_menu.open_nav_menu(self)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def on_enter(self, *a):
        SM.load()
        self._lbl_off.text = self._fmt_offset()
        pico_avail = os.path.exists("/dev/ttyACM0")
        self._src_btns["PICO"].disabled = not pico_avail
        for val, btn in self._src_btns.items():
            is_cur = (val == SM.get("source"))
            btn.state = "down" if is_cur else "normal"
            btn.background_color = C_ON if is_cur else C_BTN
        for val, btn in self._shunt_btns.items():
            is_cur = (abs(val - SM.get("shunt_ohm", 0.1)) < 1e-9)
            btn.state = "down" if is_cur else "normal"
            btn.background_color = C_ON if is_cur else C_BTN
        for val, btn in self._theme_btns.items():
            is_cur = (val == SM.get("theme"))
            btn.state = "down" if is_cur else "normal"
            btn.background_color = C_ON if is_cur else C_BTN
        cur_lang = SM.get("lang", "fr")
        for val, btn in self._lang_btns.items():
            is_cur = (val == cur_lang)
            btn.state = "down" if is_cur else "normal"
            btn.background_color = C_ON if is_cur else C_BTN
