"""Сворачиваемый блок (спойлер) для ttk."""
from tkinter import ttk


class CollapsibleFrame(ttk.Frame):
    """Заголовок-кнопка ▼/▶ + сворачиваемое тело `body`.

    on_toggle(expanded: bool) — вызывается при каждом изменении состояния.
    """

    def __init__(self, parent, title="", expanded=True, on_toggle=None, **kwargs):
        super().__init__(parent, style="Modern.TFrame", **kwargs)

        self._title = title
        self._expanded = bool(expanded)
        self._on_toggle = on_toggle

        self._header = ttk.Frame(self, style="Modern.TFrame", cursor="hand2")
        self._header.pack(fill="x")

        self._arrow = ttk.Label(self._header,
                                text="▼" if self._expanded else "▶",
                                font=("Segoe UI", 10, "bold"),
                                foreground=self._accent(),
                                cursor="hand2")
        self._arrow.pack(side="left", padx=(4, 6))

        self._title_label = ttk.Label(self._header,
                                      text=self._title,
                                      font=("Segoe UI", 10, "bold"),
                                      cursor="hand2")
        self._title_label.pack(side="left")

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(2, 0))

        self.body = ttk.Frame(self, style="Modern.TFrame")
        if self._expanded:
            self.body.pack(fill="both", expand=True, pady=(6, 0))

        for w in (self._header, self._arrow, self._title_label):
            w.bind("<Button-1>", lambda e: self.toggle())

    def _accent(self):
        try:
            return self.master.winfo_toplevel().colors.get("accent", "#2196f3")
        except Exception:
            return "#2196f3"

    @property
    def is_expanded(self):
        return self._expanded

    def toggle(self):
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        if self._expanded:
            return
        self._expanded = True
        self._arrow.config(text="▼")
        self.body.pack(fill="both", expand=True, pady=(6, 0))
        self._fire_toggle()

    def collapse(self):
        if not self._expanded:
            return
        self._expanded = False
        self._arrow.config(text="▶")
        self.body.pack_forget()
        self._fire_toggle()

    def _fire_toggle(self):
        if self._on_toggle is None:
            return
        try:
            self._on_toggle(self._expanded)
        except Exception:
            pass