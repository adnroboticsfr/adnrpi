import math
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

from tools.registry import TOOLS

HEADER_H  = 52
SCREEN_H  = 480
SPACING   = 5
PADDING   = 10   # top+bottom
BTN_MIN   = 75
BTN_MAX   = 120


class CategoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root = BoxLayout(orientation="vertical", spacing=0)
        self.add_widget(self._root)

    def load(self, cat_id):
        self._root.clear_widgets()

        cat_tools = TOOLS.get(cat_id, [])
        cat_label = cat_id.replace("_", " ").title()
        n = len(cat_tools)

        # ── Header ───────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=HEADER_H, padding=(8, 6), spacing=8)
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda i, v: setattr(rect, "pos", v),
                    size=lambda i, v: setattr(rect, "size", v))

        btn_back = Button(
            text="<", font_size="22sp",
            size_hint=(None, None), size=(50, 40),
            background_color=(0.2, 0.2, 0.2, 1)
        )
        btn_back.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))
        header.add_widget(btn_back)
        header.add_widget(Label(
            text=f"[b]{cat_label}[/b]  [size=12][color=888888]{n} outils[/color][/size]",
            markup=True, font_size="17sp",
            color=(0.2, 0.8, 0.2, 1), halign="left", valign="middle"
        ))

        # ── Calcul colonnes et hauteur bouton ─────────────────────────────────
        cols  = 3 if n > 9 else 2
        rows  = math.ceil(n / cols)
        avail = SCREEN_H - HEADER_H - PADDING - SPACING * (rows - 1)
        btn_h = max(BTN_MIN, min(BTN_MAX, avail // rows))
        needs_scroll = (rows * btn_h + (rows - 1) * SPACING + PADDING) > (SCREEN_H - HEADER_H)

        name_sp = "15sp" if cols == 3 else "17sp"
        desc_sp = "12sp" if cols == 3 else "13sp"

        # ── Grille ────────────────────────────────────────────────────────────
        grid = GridLayout(
            cols=cols, spacing=SPACING, padding=(PADDING // 2, PADDING // 2),
            size_hint_y=None,
        )
        grid.bind(minimum_height=grid.setter("height"))

        for tool in cat_tools:
            btn = Button(
                text=f"[b]{tool['name']}[/b]\n[size={desc_sp}][color=cccccc]{tool.get('desc','')}[/color][/size]",
                markup=True,
                font_size=name_sp,
                halign="center",
                valign="middle",
                size_hint_y=None, height=btn_h,
                background_color=(0.12, 0.18, 0.28, 1),
                background_normal="",
                padding=(8, 4),
            )
            btn.bind(size=btn.setter("text_size"))
            t = tool
            btn.bind(on_press=lambda inst, tool=t: self._open_tool(tool))
            grid.add_widget(btn)

        if needs_scroll:
            scroll = ScrollView(
                size_hint=(1, 1),
                bar_width=8,
                bar_color=(0.2, 0.8, 0.2, 0.9),
                bar_inactive_color=(0.2, 0.5, 0.2, 0.4),
                scroll_type=["bars", "content"],
                do_scroll_x=False,
            )
            scroll.add_widget(grid)
            self._root.add_widget(header)
            self._root.add_widget(scroll)
        else:
            # Tout rentre — ScrollView quand même pour un éventuel over-scroll tactile
            scroll = ScrollView(
                size_hint=(1, 1),
                do_scroll_x=False,
                bar_width=0,
            )
            scroll.add_widget(grid)
            self._root.add_widget(header)
            self._root.add_widget(scroll)

    def _open_tool(self, tool):
        tool_screen = self.manager.get_screen("tool")
        tool_screen.load(tool)
        self.manager.current = "tool"
