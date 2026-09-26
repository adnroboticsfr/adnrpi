from kivy.uix.screenmanager import Screen
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

CATEGORIES = [
    {"id": "network",   "label": "Network\nScan",     "icon": "🌐", "color": (0.10, 0.45, 0.70, 1)},
    {"id": "wifi",      "label": "WiFi\nAttack",      "icon": "📡", "color": (0.70, 0.30, 0.10, 1)},
    {"id": "web",       "label": "Web\nAudit",        "icon": "🌍", "color": (0.10, 0.55, 0.30, 1)},
    {"id": "passwords", "label": "Passwords\n& Hashes","icon": "🔐", "color": (0.55, 0.10, 0.55, 1)},
    {"id": "recon",     "label": "Recon\n& OSINT",    "icon": "🔍", "color": (0.65, 0.50, 0.05, 1)},
    {"id": "capture",   "label": "Capture\n& Analysis","icon": "📦", "color": (0.15, 0.50, 0.60, 1)},
]


class HomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = BoxLayout(orientation="vertical", spacing=0)

        # ── Header ───────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=48, padding=(10, 4))
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            self._header_rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._update_header, size=self._update_header)

        header.add_widget(Label(
            text="[b]ADNRPi HackPad[/b]",
            markup=True, font_size="18sp", color=(0.2, 0.8, 0.2, 1),
            size_hint_x=0.7, halign="left", valign="middle"
        ))

        btn_settings = Button(
            text="⚙", font_size="22sp",
            size_hint=(None, None), size=(48, 40),
            background_color=(0.15, 0.15, 0.15, 1)
        )
        btn_settings.bind(on_press=lambda *a: setattr(self.manager, "current", "settings"))

        btn_mode = Button(
            text="🖥", font_size="22sp",
            size_hint=(None, None), size=(48, 40),
            background_color=(0.15, 0.15, 0.15, 1)
        )
        btn_mode.bind(on_press=lambda *a: setattr(self.manager, "current", "mode"))

        header.add_widget(btn_settings)
        header.add_widget(btn_mode)

        # ── Category grid 3×2 ────────────────────────────────────────────────
        grid = GridLayout(cols=3, rows=2, spacing=6, padding=6)
        for cat in CATEGORIES:
            btn = Button(
                text=f"{cat['icon']}\n{cat['label']}",
                markup=False,
                font_size="16sp",
                halign="center",
                background_color=cat["color"],
                background_normal="",
            )
            cat_id = cat["id"]
            btn.bind(on_press=lambda instance, c=cat_id: self._open_category(c))
            grid.add_widget(btn)

        root.add_widget(header)
        root.add_widget(grid)
        self.add_widget(root)

    def _open_category(self, cat_id):
        cat_screen = self.manager.get_screen("category")
        cat_screen.load(cat_id)
        self.manager.current = "category"

    def _update_header(self, instance, value):
        self._header_rect.pos  = instance.pos
        self._header_rect.size = instance.size
