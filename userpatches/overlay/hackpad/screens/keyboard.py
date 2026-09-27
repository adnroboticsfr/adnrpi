import time
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.clock import Clock

KB_ROWS = [
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm",
]


class InputPopup(Popup):
    """
    Popup clavier tactile.  S'ouvre sur un champ, retourne la valeur via on_confirm.
    Supporte aussi le clavier physique (branché ou BT).
    """

    def __init__(self, field_label, initial_value, on_confirm, password=False, **kwargs):
        super().__init__(
            title=field_label,
            title_size="15sp",
            size_hint=(0.97, 0.82),
            auto_dismiss=False,
            separator_height=1,
            **kwargs,
        )
        self._value = initial_value
        self._on_confirm = on_confirm
        self._password = password
        self._last_type = 0.0
        self._keys_enabled = False   # activé après délai dans on_open

        root = BoxLayout(orientation="vertical", spacing=4, padding=(6, 4))

        # ── Affichage de la valeur ────────────────────────────────────────────
        self._disp = Label(
            font_size="16sp",
            size_hint_y=None, height=44,
            halign="left", valign="middle",
            color=(0.2, 1.0, 0.4, 1),
            text_size=(None, None),
        )
        self._refresh_display()

        # ── Rangées de lettres ────────────────────────────────────────────────
        kb = BoxLayout(orientation="vertical", spacing=3)
        for row in KB_ROWS:
            r = BoxLayout(spacing=2)
            for ch in row:
                b = Button(text=ch, font_size="16sp",
                           background_color=(0.25, 0.25, 0.25, 1),
                           background_normal="")
                b.bind(on_press=lambda inst, c=ch: self._type(c))
                r.add_widget(b)
            kb.add_widget(r)

        # ── Rangée symboles + actions ─────────────────────────────────────────
        sym = BoxLayout(spacing=2)
        for lbl, val, sx in [
            (".",     ".",      0.06),
            ("/",     "/",      0.06),
            ("-",     "-",      0.06),
            ("_",     "_",      0.06),
            ("ESP",   " ",      0.28),
            ("<|",    "__bs__", 0.13),
            ("Annul", "__no__", 0.17),
            ("OK",    "__ok__", 0.18),
        ]:
            bc = (0.10, 0.45, 0.10, 1) if val == "__ok__" \
                else (0.50, 0.15, 0.15, 1) if val == "__no__" \
                else (0.35, 0.20, 0.10, 1) if val == "__bs__" \
                else (0.25, 0.25, 0.25, 1)
            b = Button(text=lbl, font_size="13sp", size_hint_x=sx,
                       background_color=bc, background_normal="")
            b.bind(on_press=lambda inst, v=val: self._type(v))
            sym.add_widget(b)
        kb.add_widget(sym)

        root.add_widget(self._disp)
        root.add_widget(kb)
        self.content = root

    # ── Cycle de vie ──────────────────────────────────────────────────────────

    def on_open(self):
        # On attend 400 ms après l'ouverture pour éviter de capter le tap d'ouverture
        Clock.schedule_once(self._enable_keys, 0.4)

    def _enable_keys(self, dt):
        self._keys_enabled = True
        Window.bind(on_key_down=self._physical_key)

    def on_dismiss(self):
        self._keys_enabled = False
        Window.unbind(on_key_down=self._physical_key)

    # ── Saisie ────────────────────────────────────────────────────────────────

    def _refresh_display(self):
        if self._password:
            shown = "*" * len(self._value)
        else:
            shown = self._value
        self._disp.text = shown + "|"

    def _type(self, val):
        now = time.monotonic()
        if now - self._last_type < 0.15:
            return
        self._last_type = now

        if val == "__bs__":
            self._value = self._value[:-1]
        elif val == "__ok__":
            self._confirm()
            return
        elif val == "__no__":
            self._cancel()
            return
        else:
            self._value += val
        self._refresh_display()

    def _confirm(self):
        Window.unbind(on_key_down=self._physical_key)
        self._on_confirm(self._value)
        self.dismiss()

    def _cancel(self):
        Window.unbind(on_key_down=self._physical_key)
        self.dismiss()

    def _physical_key(self, window, key, scancode, codepoint, modifiers):
        if not self._keys_enabled:
            return True
        if key == 8:
            self._type("__bs__")
        elif key in (13, 271):
            self._confirm()
        elif key == 27:
            self._cancel()
        elif codepoint:
            self._type(codepoint)
        return True


def make_field_button(label_txt, initial_value, on_confirm,
                      height=50, password=False, hint=""):
    """Retourne un Button qui ouvre InputPopup au tap.
    Affiche le hint en gris quand la valeur est vide.
    """
    def _display(val):
        if password:
            return "*" * len(val) if val else (hint or "")
        return val if val else (hint or "")

    btn = Button(
        text=_display(initial_value),
        font_size="13sp",
        halign="left",
        padding=(8, 0),
        size_hint_y=None, height=height,
        background_color=(0.18, 0.18, 0.18, 1),
        background_normal="",
        color=(1, 1, 1, 1) if initial_value else (0.45, 0.45, 0.45, 1),
    )
    btn.bind(size=btn.setter("text_size"))
    btn._real_value = initial_value

    def _open(*a):
        def confirm(val):
            btn._real_value = val
            btn.text = _display(val)
            btn.color = (1, 1, 1, 1) if val else (0.45, 0.45, 0.45, 1)
            on_confirm(val)
        InputPopup(label_txt, btn._real_value, confirm, password=password).open()

    btn.bind(on_press=_open)
    return btn
