from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

from tools.registry import TOOLS


class CategoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._root = BoxLayout(orientation="vertical", spacing=0)
        self.add_widget(self._root)

    def load(self, cat_id):
        self._root.clear_widgets()

        cat_tools = TOOLS.get(cat_id, [])
        cat_label = cat_id.replace("_", " ").title()

        # ── Header ───────────────────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=52, padding=(8, 6), spacing=8)
        with header.canvas.before:
            Color(0.05, 0.05, 0.05, 1)
            rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda i, v: setattr(rect, "pos", v),
                    size=lambda i, v: setattr(rect, "size", v))

        btn_back = Button(
            text="◀", font_size="20sp",
            size_hint=(None, None), size=(50, 40),
            background_color=(0.2, 0.2, 0.2, 1)
        )
        btn_back.bind(on_press=lambda *a: setattr(self.manager, "current", "home"))

        header.add_widget(btn_back)
        header.add_widget(Label(
            text=f"[b]{cat_label}[/b]",
            markup=True, font_size="18sp",
            color=(0.2, 0.8, 0.2, 1), halign="left", valign="middle"
        ))

        # ── Tool buttons ──────────────────────────────────────────────────────
        scroll = ScrollView()
        grid = GridLayout(cols=2, spacing=6, padding=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter("height"))

        for tool in cat_tools:
            btn = Button(
                text=f"[b]{tool['name']}[/b]\n[size=12]{tool['desc']}[/size]",
                markup=True,
                font_size="14sp",
                halign="left",
                text_size=(340, None),
                size_hint_y=None, height=72,
                background_color=(0.12, 0.18, 0.25, 1),
                background_normal="",
                padding=(10, 8)
            )
            t = tool
            btn.bind(on_press=lambda instance, tool=t: self._open_tool(tool))
            grid.add_widget(btn)

        scroll.add_widget(grid)
        self._root.add_widget(header)
        self._root.add_widget(scroll)

    def _open_tool(self, tool):
        tool_screen = self.manager.get_screen("tool")
        tool_screen.load(tool)
        self.manager.current = "tool"
