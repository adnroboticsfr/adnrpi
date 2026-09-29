import os
import subprocess
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle

from screens.keyboard import make_field_button

SETTINGS_FILE = "/etc/adnrpi-hackpad/settings.conf"
SYSTEM_FILE   = "/etc/adnrpi-hackpad/system.conf"

# ── Champs scan ──────────────────────────────────────────────────────────────
SCAN_FIELDS = [
    ("Target IP",  "target_ip",  "192.168.1.1",                      False),
    ("Interface",  "interface",  "eth0",                              False),
    ("Wordlist",   "wordlist",   "/usr/share/wordlists/rockyou.txt",  False),
    ("Output dir", "output_dir", "/tmp",                              False),
]

# ── Langues / claviers disponibles ───────────────────────────────────────────
KEYBOARD_LAYOUTS = [
    ("fr",    "Français"),
    ("us",    "English (US)"),
    ("de",    "Deutsch"),
    ("es",    "Español"),
    ("it",    "Italiano"),
    ("pt",    "Português"),
    ("be",    "Belge"),
    ("ch",    "Suisse"),
]


def _load_conf(path):
    s = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, _, v = line.partition("=")
                    s[k.strip()] = v.strip()
    except Exception:
        pass
    return s


def _save_conf(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for k, v in data.items():
            f.write(f"{k}={v}\n")
        f.flush()
        os.fsync(f.fileno())


def _section_header(text):
    box = BoxLayout(size_hint_y=None, height=36, padding=(8, 4))
    with box.canvas.before:
        Color(0.10, 0.10, 0.10, 1)
        rr = RoundedRectangle(pos=box.pos, size=box.size, radius=[4])
    box.bind(pos=lambda w, v: setattr(rr, "pos", v),
             size=lambda w, v: setattr(rr, "size", v))
    box.add_widget(Label(
        text=f"[b]{text}[/b]", markup=True,
        font_size="13sp", color=(0.4, 0.8, 1.0, 1),
        halign="left", valign="middle"
    ))
    return box


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        saved_scan = _load_conf(SETTINGS_FILE)
        saved_sys  = _load_conf(SYSTEM_FILE)

        self._scan_values = {key: saved_scan.get(key, default)
                             for _, key, default, _ in SCAN_FIELDS}
        self._sys_values = {
            "vnc_enabled": saved_sys.get("vnc_enabled", "no"),
            "keyboard":    saved_sys.get("keyboard", "fr"),
        }

        root = BoxLayout(orientation="vertical", spacing=0)

        # ── Header ───────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=52, padding=(8, 6), spacing=8)
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda i, v: setattr(rect, "pos", v),
                    size=lambda i, v: setattr(rect, "size", v))

        btn_back = Button(
            text="<", font_size="22sp",
            size_hint=(None, None), size=(50, 40),
            background_color=(0.2, 0.2, 0.2, 1),
        )
        btn_back.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))
        header.add_widget(btn_back)
        header.add_widget(Label(
            text="[b]Settings[/b]", markup=True,
            font_size="18sp", color=(0.2, 0.8, 0.2, 1),
            halign="left", valign="middle",
        ))

        # ── Contenu scrollable ────────────────────────────────────────────────
        content = GridLayout(cols=1, size_hint_y=None, spacing=4, padding=(8, 6))
        content.bind(minimum_height=content.setter("height"))

        # §1 — Paramètres de scan
        content.add_widget(_section_header("Paramètres de scan"))

        for label_txt, key, default, pwd in SCAN_FIELDS:
            row = BoxLayout(size_hint_y=None, height=52, spacing=6)
            row.add_widget(Label(
                text=label_txt, font_size="13sp",
                size_hint=(None, 1), width=100,
                halign="right", valign="middle",
                color=(0.7, 0.7, 0.7, 1),
            ))

            def _make_confirm(k):
                def confirm(val):
                    self._scan_values[k] = val
                return confirm

            btn = make_field_button(label_txt, self._scan_values[key],
                                    _make_confirm(key),
                                    height=52, password=pwd, hint=default)
            row.add_widget(btn)
            content.add_widget(row)

        btn_save_scan = Button(
            text="Sauvegarder paramètres scan", font_size="14sp",
            size_hint_y=None, height=46,
            background_color=(0.10, 0.45, 0.10, 1), background_normal=""
        )
        btn_save_scan.bind(on_press=self._save_scan)
        content.add_widget(btn_save_scan)

        # §2 — Système
        content.add_widget(_section_header("Système"))

        # VNC toggle
        vnc_row = BoxLayout(size_hint_y=None, height=52, spacing=6)
        vnc_row.add_widget(Label(
            text="VNC", font_size="13sp",
            size_hint=(None, 1), width=100,
            halign="right", valign="middle",
            color=(0.7, 0.7, 0.7, 1),
        ))
        self._btn_vnc = Button(
            font_size="14sp",
            size_hint_y=None, height=44,
            background_normal=""
        )
        self._update_vnc_btn()
        self._btn_vnc.bind(on_press=self._toggle_vnc)
        vnc_row.add_widget(self._btn_vnc)
        content.add_widget(vnc_row)

        # Clavier/langue
        kbd_row = BoxLayout(size_hint_y=None, height=52, spacing=6)
        kbd_row.add_widget(Label(
            text="Clavier", font_size="13sp",
            size_hint=(None, 1), width=100,
            halign="right", valign="middle",
            color=(0.7, 0.7, 0.7, 1),
        ))
        self._btn_kbd = Button(
            text=self._kbd_label(),
            font_size="14sp",
            size_hint_y=None, height=44,
            background_color=(0.20, 0.20, 0.30, 1), background_normal=""
        )
        self._btn_kbd.bind(on_press=self._choose_keyboard)
        kbd_row.add_widget(self._btn_kbd)
        content.add_widget(kbd_row)

        btn_apply_sys = Button(
            text="Appliquer système (reboot si nécessaire)", font_size="13sp",
            size_hint_y=None, height=46,
            background_color=(0.45, 0.20, 0.05, 1), background_normal=""
        )
        btn_apply_sys.bind(on_press=self._apply_system)
        content.add_widget(btn_apply_sys)

        sv = ScrollView()
        sv.add_widget(content)

        root.add_widget(header)
        root.add_widget(sv)
        self.add_widget(root)

    # ── VNC ──────────────────────────────────────────────────────────────────

    def _update_vnc_btn(self):
        on = self._sys_values.get("vnc_enabled") == "yes"
        self._btn_vnc.text = "VNC : ON  [tap pour désactiver]" if on else "VNC : OFF [tap pour activer]"
        self._btn_vnc.background_color = (0.10, 0.50, 0.10, 1) if on else (0.40, 0.10, 0.10, 1)

    def _toggle_vnc(self, *args):
        current = self._sys_values.get("vnc_enabled", "no")
        self._sys_values["vnc_enabled"] = "no" if current == "yes" else "yes"
        self._update_vnc_btn()

    # ── Clavier ───────────────────────────────────────────────────────────────

    def _kbd_label(self):
        cur = self._sys_values.get("keyboard", "fr")
        for code, name in KEYBOARD_LAYOUTS:
            if code == cur:
                return f"Clavier : {name} ({code})"
        return f"Clavier : {cur}"

    def _choose_keyboard(self, *args):
        popup_root = BoxLayout(orientation="vertical", spacing=6, padding=8)
        grid = GridLayout(cols=2, spacing=4, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        popup = Popup(
            title="Choisir la langue du clavier",
            size_hint=(0.95, 0.80),
            auto_dismiss=False,
        )

        def _select(code, *a):
            self._sys_values["keyboard"] = code
            self._btn_kbd.text = self._kbd_label()
            popup.dismiss()

        for code, name in KEYBOARD_LAYOUTS:
            is_cur = (code == self._sys_values.get("keyboard", "fr"))
            btn = Button(
                text=f"{name}\n({code})", markup=False,
                font_size="13sp",
                size_hint_y=None, height=54,
                background_normal="",
                background_color=(0.15, 0.45, 0.15, 1) if is_cur else (0.20, 0.20, 0.25, 1)
            )
            btn.bind(on_press=lambda b, c=code: _select(c))
            grid.add_widget(btn)

        sv = ScrollView()
        sv.add_widget(grid)

        btn_cancel = Button(
            text="Annuler", font_size="14sp",
            size_hint_y=None, height=44,
            background_color=(0.30, 0.10, 0.10, 1), background_normal=""
        )
        btn_cancel.bind(on_press=popup.dismiss)

        popup_root.add_widget(sv)
        popup_root.add_widget(btn_cancel)
        popup.content = popup_root
        popup.open()

    # ── Sauvegarde / Application ──────────────────────────────────────────────

    def _save_scan(self, *args):
        _save_conf(SETTINGS_FILE, self._scan_values)
        self._toast("Paramètres scan sauvegardés")

    def _apply_system(self, *args):
        needs_reboot = False
        errors = []

        # VNC
        vnc_on = self._sys_values.get("vnc_enabled") == "yes"
        try:
            cmd = ["/usr/local/bin/adnrpi-vnc", "enable" if vnc_on else "disable"]
            subprocess.run(cmd, check=True, timeout=10)
        except Exception as e:
            errors.append(f"VNC: {e}")

        # Clavier
        kbd = self._sys_values.get("keyboard", "fr")
        try:
            subprocess.run(["localectl", "set-x11-keymap", kbd], check=True, timeout=10)
            subprocess.run(["localectl", "set-keymap", kbd], check=True, timeout=10)
            needs_reboot = True
        except Exception as e:
            errors.append(f"Clavier: {e}")

        # Sauvegarder l'état système
        _save_conf(SYSTEM_FILE, self._sys_values)

        if errors:
            self._toast("Erreurs : " + " | ".join(errors), duration=5)
            return

        if needs_reboot:
            self._reboot_popup()
        else:
            self._toast("Système configuré")

    def _reboot_popup(self):
        popup = Popup(
            title="Redémarrage requis",
            size_hint=(0.85, 0.40),
            auto_dismiss=False,
        )
        box = BoxLayout(orientation="vertical", spacing=8, padding=12)
        box.add_widget(Label(
            text="Les paramètres système ont été appliqués.\nRedémarrer maintenant ?",
            font_size="14sp", halign="center"
        ))
        btns = BoxLayout(size_hint_y=None, height=48, spacing=8)
        btn_yes = Button(
            text="Redémarrer", font_size="14sp",
            background_color=(0.55, 0.10, 0.10, 1), background_normal=""
        )
        btn_no = Button(
            text="Plus tard", font_size="14sp",
            background_color=(0.25, 0.25, 0.25, 1), background_normal=""
        )
        btn_yes.bind(on_press=lambda *a: subprocess.run(["systemctl", "reboot"]))
        btn_no.bind(on_press=popup.dismiss)
        btns.add_widget(btn_yes)
        btns.add_widget(btn_no)
        box.add_widget(btns)
        popup.content = box
        popup.open()

    def _toast(self, msg, duration=2.5):
        popup = Popup(
            title="", separator_height=0,
            size_hint=(0.80, 0.20),
            auto_dismiss=True,
        )
        popup.content = Label(
            text=msg, font_size="13sp", halign="center"
        )
        popup.open()
        Clock.schedule_once(lambda dt: popup.dismiss(), duration)
