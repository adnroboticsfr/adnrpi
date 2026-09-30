"""
ADNRPi Scope — I2C Scanner
Scan I2C-0 (/dev/i2c-0) et I2C-1 (/dev/i2c-1, si overlay activé).
"""
import os
import threading

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window

import settings_manager as SM
from strings import t

_SCR_W   = int(os.environ.get("HACKPAD_W", Window.width or 800))
_COMPACT = (_SCR_W <= 800)

HDR_H   = 46 if _COMPACT else 56
FS_HDR  = "15sp" if _COMPACT else "19sp"
FS_ADR  = "11sp" if _COMPACT else "13sp"
FS_BTN  = "13sp" if _COMPACT else "15sp"
FS_RES  = "12sp" if _COMPACT else "14sp"

CELL_H  = 24   # hauteur cellule grille
CELL_SP = 2    # espacement entre cellules
COLS    = 16   # colonnes (0x00..0x0F par ligne)
ROWS    = 8    # lignes  (0x00..0x70)
GRID_H  = ROWS * CELL_H + (ROWS - 1) * CELL_SP   # 214px

# Composants connus
_KNOWN = {
    0x20: "PCF8574",    0x21: "PCF8574",    0x22: "PCF8574",    0x23: "PCF8574",
    0x24: "PCF8574",    0x25: "PCF8574",    0x26: "PCF8574",    0x27: "PCF8574/LCD",
    0x3C: "SSD1306",    0x3D: "SSD1306",
    0x40: "INA219",     0x41: "INA219",     0x44: "INA219",     0x45: "INA219",
    0x48: "ADS1115",    0x49: "ADS1115",    0x4A: "ADS1115",    0x4B: "ADS1115",
    0x50: "EEPROM",     0x51: "EEPROM",     0x52: "EEPROM",     0x57: "EEPROM",
    0x60: "MCP4725",
    0x68: "MPU6050/DS3231",                 0x69: "MPU6050",
    0x70: "TCA9548A",   0x71: "TCA9548A",
    0x76: "BME/BMP280", 0x77: "BME/BMP280",
}

_BUS_PINS = {
    0: "Pin 3/5  (GPIOA12/11)",
    1: "Pin 27/28 (GPIOA19/18) — overlay requis",
}


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *a: setattr(rect, "pos", widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )


def _scan_i2c(bus_num):
    found = []
    try:
        import smbus2
        b = smbus2.SMBus(bus_num)
        for addr in range(3, 0x78):
            try:
                b.read_byte(addr)
                found.append(addr)
            except Exception:
                pass
        b.close()
    except Exception as e:
        return None, str(e)
    return found, None


class I2CScreen(Screen):

    def __init__(self, **kw):
        super().__init__(**kw)
        self._bus      = 0
        self._found    = []
        self._scanning = False
        self._build()

    def _build(self):
        p = SM.get_palette()
        root = BoxLayout(orientation="vertical")
        _bg(root, p["BG"])
        root.add_widget(Widget(size_hint=(1, None), height=4))
        root.add_widget(self._build_header(p))
        root.add_widget(self._build_body(p))
        self.add_widget(root)

    # ── Header ────────────────────────────────────────────────────────────────

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

        # Sélecteur bus I2C
        self._btn_bus0 = ToggleButton(
            text="I2C-0", font_size=FS_BTN, group="bus",
            state="down", background_normal="",
            background_color=(0.18, 0.45, 0.18, 1),
            size_hint=(None, 1), width=70)
        self._btn_bus1 = ToggleButton(
            text="I2C-1", font_size=FS_BTN, group="bus",
            state="normal", background_normal="",
            background_color=(0.22, 0.22, 0.22, 1),
            size_hint=(None, 1), width=70)
        self._btn_bus0.bind(on_press=lambda *a: self._set_bus(0))
        self._btn_bus1.bind(on_press=lambda *a: self._set_bus(1))

        # I2C-1 grisé si pas disponible
        if not os.path.exists("/dev/i2c-1"):
            self._btn_bus1.disabled = True
            self._btn_bus1.text = "I2C-1 ?"

        self._lbl_title = Label(text="I2C SCANNER", font_size=FS_HDR, bold=True,
                                color=p["TEXT"], size_hint=(1, 1),
                                halign="center", valign="middle")

        self._btn_scan = Button(text="[Scan]", font_size=FS_BTN, bold=True,
                                background_color=(0.18, 0.35, 0.18, 1),
                                background_normal="",
                                size_hint=(None, 1), width=80)
        self._btn_scan.bind(on_press=self._start_scan)

        for w in (btn_back, self._btn_bus0, self._btn_bus1,
                  self._lbl_title, self._btn_scan):
            hdr.add_widget(w)
        return hdr

    # ── Body ──────────────────────────────────────────────────────────────────

    def _build_body(self, p):
        body = BoxLayout(orientation="vertical",
                         size_hint=(1, 1), padding=[10, 8], spacing=6)
        _bg(body, p["BG"])

        # Statut + info bus
        self._lbl_status = Label(
            text=t("press_scan"),
            font_size=FS_BTN, color=(0.55, 0.55, 0.55, 1),
            size_hint=(1, None), height=22,
            halign="center", valign="middle")
        body.add_widget(self._lbl_status)

        self._lbl_pins = Label(
            text=_BUS_PINS[0],
            font_size="11sp", color=(0.35, 0.35, 0.35, 1),
            size_hint=(1, None), height=18,
            halign="center", valign="middle")
        body.add_widget(self._lbl_pins)

        # Grille adresses 0x00–0x7F — hauteur fixe calculée
        self._grid = GridLayout(
            cols=COLS,
            size_hint=(1, None), height=GRID_H,
            spacing=CELL_SP)
        self._cells = {}
        for addr in range(0x00, 0x80):
            lbl = Label(
                text=f"{addr:02X}",
                font_size=FS_ADR,
                color=(0.28, 0.28, 0.28, 1),
                size_hint=(1, None), height=CELL_H,
                halign="center", valign="middle",
                bold=False)
            self._cells[addr] = lbl
            self._grid.add_widget(lbl)
        body.add_widget(self._grid)

        # Résultats texte — prend le reste
        self._lbl_results = Label(
            text="",
            font_size=FS_RES,
            color=(0.65, 0.65, 0.65, 1),
            size_hint=(1, 1),
            halign="left", valign="top",
            text_size=(_SCR_W - 20, None))
        body.add_widget(self._lbl_results)

        return body

    # ── Scan ──────────────────────────────────────────────────────────────────

    def _set_bus(self, bus_num):
        self._bus = bus_num
        self._lbl_pins.text = _BUS_PINS[bus_num]
        self._btn_bus0.background_color = (0.18, 0.45, 0.18, 1) if bus_num == 0 else (0.22, 0.22, 0.22, 1)
        self._btn_bus1.background_color = (0.18, 0.45, 0.18, 1) if bus_num == 1 else (0.22, 0.22, 0.22, 1)
        self._start_scan()

    def _start_scan(self, *a):
        if self._scanning:
            return
        self._scanning = True
        self._btn_scan.disabled = True
        self._btn_scan.text = "..."
        self._lbl_status.text = f"{t('scanning')} I2C-{self._bus}"
        self._lbl_results.text = ""
        for lbl in self._cells.values():
            lbl.color = (0.28, 0.28, 0.28, 1)
            lbl.bold  = False

        bus = self._bus
        threading.Thread(target=lambda: self._worker(bus), daemon=True).start()

    def _worker(self, bus):
        found, err = _scan_i2c(bus)
        Clock.schedule_once(lambda dt: self._on_result(found, err))

    def _on_result(self, found, err):
        self._scanning = False
        self._btn_scan.disabled = False
        self._btn_scan.text = "[Scan]"

        if err is not None:
            self._lbl_status.text = f"Erreur I2C-{self._bus}: {err}"
            self._lbl_results.text = ""
            return

        self._found = found
        n = len(found)
        self._lbl_status.text = (
            f"I2C-{self._bus} : {n} peripherique{'s' if n != 1 else ''} trouve{'s' if n != 1 else ''}"
        )

        lines = []
        for addr in found:
            self._cells[addr].color = (0.20, 1.00, 0.40, 1)
            self._cells[addr].bold  = True
            name = _KNOWN.get(addr, "?")
            lines.append(f"0x{addr:02X}  {name}")

        self._lbl_results.text = "  ".join(lines) if lines else t("no_device")

    # ── Navigation ────────────────────────────────────────────────────────────

    def _open_menu(self, *a):
        import nav_menu
        nav_menu.open_nav_menu(self)

    def on_enter(self, *a):
        self._start_scan()
