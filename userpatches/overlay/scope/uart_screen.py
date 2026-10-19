"""
ADNRPi Scope — UART Monitor
Ecoute un port série et affiche les données reçues.

Ports disponibles sur SmartPi One H3 :
  UART1 : /dev/ttyS1  — Pin 8 (TX/GPIOG6)  + Pin 10 (RX/GPIOG7)
  UART2 : /dev/ttyS2  — Pin 11 (TX/GPIOA0) + Pin 22 (RX/GPIOA1)
  UART3 : /dev/ttyS3  — Pin 36 (TX/GPIOA13)+ Pin 40 (RX/GPIOA14)
  USB   : /dev/ttyUSB0 — adaptateur USB-série
  Pico  : /dev/ttyACM0 — Pi Pico USB
"""
import os
import threading
import time

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window

import settings_manager as SM
from strings import t

_SCR_W   = int(os.environ.get("HACKPAD_W", Window.width or 800))
_COMPACT = (_SCR_W <= 800)

HDR_H  = 46 if _COMPACT else 56
BOT_H  = 36 if _COMPACT else 44
FS_HDR = "14sp" if _COMPACT else "18sp"
FS_BTN = "12sp" if _COMPACT else "15sp"
FS_TRM = "12sp" if _COMPACT else "14sp"

_PORTS = ["/dev/ttyS1", "/dev/ttyS2", "/dev/ttyS3", "/dev/ttyUSB0", "/dev/ttyACM0"]
_PORT_LABELS = {
    "/dev/ttyS1":   "UART1 (Pin8/10)",
    "/dev/ttyS2":   "UART2 (Pin11/22)",
    "/dev/ttyS3":   "UART3 (Pin36/40)",
    "/dev/ttyUSB0": "USB-Série",
    "/dev/ttyACM0": "Pico USB",
}
_BAUDS = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

MAX_LINES = 200   # nombre max de lignes affichées


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *a: setattr(rect, "pos", widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )


class UartScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._port_idx  = 0
        self._baud_idx  = _BAUDS.index(115200)
        self._serial    = None
        self._connected = False
        self._rx_thread = None
        self._lines     = []
        self._hex_mode  = False
        self._build()

    # ── Construction UI ───────────────────────────────────────────────────────

    def _build(self):
        p = SM.get_palette()
        root = BoxLayout(orientation="vertical")
        _bg(root, p["BG"])
        root.add_widget(Widget(size_hint=(1, None), height=4))
        root.add_widget(self._build_header(p))
        root.add_widget(self._build_terminal(p))
        root.add_widget(self._build_bottom(p))
        self.add_widget(root)

    def _build_header(self, p):
        hdr = BoxLayout(orientation="horizontal",
                        size_hint=(1, None), height=HDR_H,
                        padding=[6, 4], spacing=6)
        _bg(hdr, p["HDR"])

        btn_back = Button(text="Menu", font_size=FS_HDR, bold=True,
                          background_color=(0.20, 0.20, 0.32, 1),
                          background_normal="",
                          size_hint=(None, 1), width=80)
        btn_back.bind(on_press=self._open_menu)

        # Cycle port
        self._btn_port = Button(
            text=self._port_label(), font_size=FS_BTN, bold=True,
            background_color=(0.22, 0.22, 0.30, 1),
            background_normal="",
            size_hint=(None, 1), width=150)
        self._btn_port.bind(on_press=self._cycle_port)

        # Cycle baud
        self._btn_baud = Button(
            text=self._baud_label(), font_size=FS_BTN, bold=True,
            background_color=(0.22, 0.22, 0.22, 1),
            background_normal="",
            size_hint=(None, 1), width=90)
        self._btn_baud.bind(on_press=self._cycle_baud)

        hdr.add_widget(btn_back)
        hdr.add_widget(self._btn_port)
        hdr.add_widget(self._btn_baud)
        hdr.add_widget(Widget(size_hint=(1, 1)))   # spacer

        # Connexion
        self._btn_conn = Button(
            text="[Conn]", font_size=FS_BTN, bold=True,
            background_color=(0.18, 0.40, 0.18, 1),
            background_normal="",
            size_hint=(None, 1), width=80)
        self._btn_conn.bind(on_press=self._toggle_conn)
        hdr.add_widget(self._btn_conn)

        return hdr

    def _build_terminal(self, p):
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False)
        _bg(scroll, (0.02, 0.02, 0.02, 1))

        self._lbl_term = Label(
            text="",
            font_size=FS_TRM,
            color=(0.80, 0.95, 0.80, 1),
            size_hint=(1, None),
            halign="left", valign="top",
            font_name="RobotoMono-Regular",   # police mono si dispo
            text_size=(_SCR_W - 16, None))
        self._lbl_term.bind(texture_size=self._lbl_term.setter("size"))
        scroll.add_widget(self._lbl_term)
        self._scroll = scroll
        return scroll

    def _build_bottom(self, p):
        bot = BoxLayout(orientation="horizontal",
                        size_hint=(1, None), height=BOT_H,
                        padding=[6, 4], spacing=6)
        _bg(bot, p["HDR"])

        self._lbl_status = Label(
            text=t("disconnected"),
            font_size=FS_BTN, color=(0.50, 0.50, 0.50, 1),
            size_hint=(1, 1), halign="left", valign="middle")

        btn_hex = Button(text="HEX", font_size=FS_BTN,
                          background_color=(0.22, 0.22, 0.22, 1),
                          background_normal="",
                          size_hint=(None, 1), width=56)
        btn_hex.bind(on_press=self._toggle_hex)
        self._btn_hex = btn_hex

        btn_clr = Button(text=t("clear"), font_size=FS_BTN,
                          background_color=(0.28, 0.10, 0.10, 1),
                          background_normal="",
                          size_hint=(None, 1), width=80)
        btn_clr.bind(on_press=self._clear)

        bot.add_widget(self._lbl_status)
        bot.add_widget(btn_hex)
        bot.add_widget(btn_clr)
        return bot

    # ── Helpers label ─────────────────────────────────────────────────────────

    def _port_label(self):
        port = _PORTS[self._port_idx]
        return _PORT_LABELS.get(port, port.split("/")[-1])

    def _baud_label(self):
        return f"{_BAUDS[self._baud_idx]}"

    # ── Actions ───────────────────────────────────────────────────────────────

    def _cycle_port(self, *a):
        if self._connected:
            return
        self._port_idx = (self._port_idx + 1) % len(_PORTS)
        self._btn_port.text = self._port_label()

    def _cycle_baud(self, *a):
        if self._connected:
            return
        self._baud_idx = (self._baud_idx + 1) % len(_BAUDS)
        self._btn_baud.text = self._baud_label()

    def _toggle_conn(self, *a):
        if self._connected:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = _PORTS[self._port_idx]
        baud = _BAUDS[self._baud_idx]
        try:
            import serial
            self._serial = serial.Serial(port, baud, timeout=0.1)
            self._connected = True
            self._btn_conn.text = "[Stop]"
            self._btn_conn.background_color = (0.45, 0.10, 0.10, 1)
            self._btn_port.background_color  = (0.14, 0.14, 0.14, 1)
            self._btn_baud.background_color  = (0.14, 0.14, 0.14, 1)
            self._lbl_status.text = f"Connecté  {port}  {baud} baud"
            self._lbl_status.color = (0.20, 1.00, 0.40, 1)
            self._rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
            self._rx_thread.start()
        except Exception as e:
            self._lbl_status.text = f"Erreur: {e}"
            self._lbl_status.color = (1.0, 0.40, 0.10, 1)

    def _disconnect(self):
        self._connected = False
        if self._serial:
            try:
                self._serial.close()
            except Exception:
                pass
            self._serial = None
        self._btn_conn.text = "[Conn]"
        self._btn_conn.background_color = (0.18, 0.40, 0.18, 1)
        self._btn_port.background_color = (0.22, 0.22, 0.30, 1)
        self._btn_baud.background_color = (0.22, 0.22, 0.22, 1)
        self._lbl_status.text  = t("disconnected")
        self._lbl_status.color = (0.50, 0.50, 0.50, 1)

    def _rx_loop(self):
        buf = b""
        while self._connected and self._serial:
            try:
                data = self._serial.read(256)
                if data:
                    buf += data
                    lines_raw = buf.split(b"\n")
                    buf = lines_raw[-1]
                    for raw in lines_raw[:-1]:
                        if self._hex_mode:
                            txt = " ".join(f"{b:02X}" for b in raw)
                        else:
                            txt = raw.decode("utf-8", errors="replace").rstrip("\r")
                        Clock.schedule_once(lambda dt, t=txt: self._append(t))
            except Exception:
                time.sleep(0.01)

    def _append(self, line):
        self._lines.append(line)
        if len(self._lines) > MAX_LINES:
            self._lines = self._lines[-MAX_LINES:]
        self._lbl_term.text = "\n".join(self._lines)
        Clock.schedule_once(lambda dt: self._scroll_bottom())

    def _scroll_bottom(self):
        self._scroll.scroll_y = 0

    def _toggle_hex(self, *a):
        self._hex_mode = not self._hex_mode
        self._btn_hex.background_color = (
            (0.18, 0.45, 0.18, 1) if self._hex_mode else (0.22, 0.22, 0.22, 1))

    def _clear(self, *a):
        self._lines = []
        self._lbl_term.text = ""

    # ── Navigation ────────────────────────────────────────────────────────────

    def _open_menu(self, *a):
        import nav_menu
        nav_menu.open_nav_menu(self)

    def on_leave(self, *a):
        self._disconnect()
