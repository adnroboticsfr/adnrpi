"""
ADNRPi — Menu de navigation partagé entre tous les écrans outils.
"""
from kivy.uix.modalview import ModalView
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle
from strings import t


_TOOL_KEYS = [
    ("nav_scope",    "scope",    (0.12, 0.32, 0.12, 1)),
    ("nav_meter",    "meter",    (0.20, 0.38, 0.20, 1)),
    ("nav_i2c",      "i2c",      (0.14, 0.22, 0.36, 1)),
    ("nav_uart",     "uart",     (0.30, 0.16, 0.08, 1)),
    ("nav_settings", "settings", (0.28, 0.20, 0.10, 1)),
]


def _bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(pos=widget.pos, size=widget.size)
    widget.bind(
        pos=lambda *a: setattr(rect, "pos", widget.pos),
        size=lambda *a: setattr(rect, "size", widget.size),
    )


def open_nav_menu(screen):
    """Ouvre la popup de navigation depuis n'importe quel écran."""
    current = screen.name if screen.manager else ""

    mv = ModalView(size_hint=(None, None), size=(270, 316),
                   background_color=(0, 0, 0, 0),
                   overlay_color=(0, 0, 0, 0.60),
                   auto_dismiss=False)

    box = BoxLayout(orientation="vertical", padding=10, spacing=8)
    _bg(box, (0.07, 0.07, 0.14, 1))

    for key, dest, color in _TOOL_KEYS:
        label = t(key)
        is_current = (dest == current)
        c = (0.12, 0.12, 0.12, 1) if is_current else color
        txt = f"[ {label} ]" if is_current else label
        b = Button(text=txt, font_size="15sp", bold=True,
                   background_color=c, background_normal="",
                   disabled=is_current,
                   size_hint=(1, None), height=44)

        def _go(*a, d=dest):
            mv.dismiss()
            if screen.manager:
                screen.manager.current = d

        b.bind(on_press=_go)
        box.add_widget(b)

    btn_close = Button(text=t("close"), font_size="14sp",
                       background_color=(0.22, 0.22, 0.22, 1),
                       background_normal="",
                       size_hint=(1, None), height=36)
    btn_close.bind(on_press=lambda *a: mv.dismiss())
    box.add_widget(btn_close)

    mv.add_widget(box)
    mv.open()
