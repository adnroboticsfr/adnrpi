"""
Persistance des réglages ADNRPi Scope.
Fichier JSON : /opt/adnrpi-scope/settings.json
"""
import json
import os

_PATH = "/opt/adnrpi-scope/settings.json"

_DEFAULTS = {
    "source":        "AUTO",   # AUTO | MIC | SIM | PICO
    "shunt_ohm":     0.1,      # résistance shunt INA219 (ohm)
    "adc_offset_mv": 0.0,      # offset calibration CH1 (mV)
    "theme":         "dark",   # dark | blue | hicontrast
    "lang":          "fr",     # fr | en
}

_SHUNT_OPTIONS  = [0.01, 0.05, 0.1, 0.5, 1.0]
_SOURCE_OPTIONS = ["AUTO", "MIC", "SIM"]   # PICO ajouté si /dev/ttyACM0

# ── Palettes de couleurs ───────────────────────────────────────────────────────

PALETTES = {
    "dark": {
        "BG":    (0.04, 0.04, 0.04, 1),
        "HDR":   (0.07, 0.07, 0.07, 1),
        "PANEL": (0.10, 0.10, 0.10, 1),
        "MEAS":  (0.06, 0.06, 0.06, 1),
        "WAVE":  (0.10, 1.00, 0.25, 1),
        "GRID":  (0.14, 0.14, 0.14, 1),
        "AXIS":  (0.24, 0.24, 0.24, 1),
        "TEXT":  (0.78, 0.78, 0.78, 1),
    },
    "blue": {
        "BG":    (0.02, 0.04, 0.12, 1),
        "HDR":   (0.03, 0.06, 0.18, 1),
        "PANEL": (0.03, 0.06, 0.16, 1),
        "MEAS":  (0.02, 0.05, 0.14, 1),
        "WAVE":  (0.20, 0.85, 1.00, 1),
        "GRID":  (0.08, 0.12, 0.22, 1),
        "AXIS":  (0.12, 0.18, 0.32, 1),
        "TEXT":  (0.80, 0.88, 1.00, 1),
    },
    "hicontrast": {
        "BG":    (0.00, 0.00, 0.00, 1),
        "HDR":   (0.10, 0.10, 0.10, 1),
        "PANEL": (0.08, 0.08, 0.08, 1),
        "MEAS":  (0.06, 0.06, 0.06, 1),
        "WAVE":  (1.00, 1.00, 0.00, 1),
        "GRID":  (0.18, 0.18, 0.18, 1),
        "AXIS":  (0.28, 0.28, 0.28, 1),
        "TEXT":  (1.00, 1.00, 1.00, 1),
    },
}


def get_palette():
    theme = get("theme", "dark")
    return PALETTES.get(theme, PALETTES["dark"])


# ── Persistance ────────────────────────────────────────────────────────────────

_current = None


def load():
    global _current
    try:
        with open(_PATH) as f:
            d = _DEFAULTS.copy()
            d.update(json.load(f))
            _current = d
            return d
    except Exception:
        _current = _DEFAULTS.copy()
        return _current


def get(key, default=None):
    if _current is None:
        load()
    return _current.get(key, _DEFAULTS.get(key, default))


def set_val(key, value):
    if _current is None:
        load()
    _current[key] = value
    _save()


def _save():
    try:
        with open(_PATH, "w") as f:
            json.dump(_current, f, indent=2)
    except Exception:
        pass
