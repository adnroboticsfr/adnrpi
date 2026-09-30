"""
ADNRPi Scope — Traductions FR / EN
Usage : from strings import t
"""

_S = {
    "fr": {
        # Navigation
        "menu":       "Menu",
        "close":      "Fermer",
        "quit":       "< Quitter",
        # Scope panel
        "slope":      "Pente",
        "coupling":   "Couplage",
        "rise":       "^ MONT",
        "fall":       "v DESC",
        # Meter
        "voltage":    "Tension",
        "current":    "Courant",
        "power":      "Puissance",
        "searching":  "Recherche...",
        # I2C
        "press_scan": "Appuyer sur [Scan]",
        "scanning":   "Scan en cours...",
        "no_device":  "Aucun peripherique detecte",
        # UART
        "disconnected": "Deconnecte",
        "hex_mode":   "HEX",
        "clear":      "Effacer",
        # Settings sections
        "settings_title": "REGLAGES",
        "src_label":  "Source par defaut",
        "shunt_label": "Shunt INA219 (ohm)",
        "offset_label": "Offset ADC CH1 (calibration)",
        "theme_label": "Theme affichage",
        "lang_label":  "Langue",
        "startup_label": "Application de demarrage",
        "change":     "Changer",
        # Nav menu items
        "nav_scope":  "Oscilloscope",
        "nav_meter":  "Metre INA219",
        "nav_i2c":    "I2C Scanner",
        "nav_uart":   "UART Monitor",
        "nav_settings": "Reglages",
        # Version info
        "app_info":   "ADNRPi Scope v1.0 — SmartPi One H3 — Armbian Bookworm",
        "startup_app_lbl": "Application de demarrage :",
    },
    "en": {
        # Navigation
        "menu":       "Menu",
        "close":      "Close",
        "quit":       "< Quit",
        # Scope panel
        "slope":      "Slope",
        "coupling":   "Coupling",
        "rise":       "^ RISE",
        "fall":       "v FALL",
        # Meter
        "voltage":    "Voltage",
        "current":    "Current",
        "power":      "Power",
        "searching":  "Searching...",
        # I2C
        "press_scan": "Press [Scan]",
        "scanning":   "Scanning...",
        "no_device":  "No device detected",
        # UART
        "disconnected": "Disconnected",
        "hex_mode":   "HEX",
        "clear":      "Clear",
        # Settings sections
        "settings_title": "SETTINGS",
        "src_label":  "Default source",
        "shunt_label": "INA219 Shunt (ohm)",
        "offset_label": "ADC CH1 Offset (cal.)",
        "theme_label": "Display theme",
        "lang_label":  "Language",
        "startup_label": "Startup app",
        "change":     "Change",
        # Nav menu items
        "nav_scope":  "Oscilloscope",
        "nav_meter":  "INA219 Meter",
        "nav_i2c":    "I2C Scanner",
        "nav_uart":   "UART Monitor",
        "nav_settings": "Settings",
        # Version info
        "app_info":   "ADNRPi Scope v1.0 — SmartPi One H3 — Armbian Bookworm",
        "startup_app_lbl": "Startup application:",
    },
}


def t(key, fallback=None):
    """Retourne la traduction de key dans la langue courante."""
    import settings_manager as SM
    lang = SM.get("lang", "fr")
    return _S.get(lang, _S["fr"]).get(key, fallback if fallback is not None else key)
