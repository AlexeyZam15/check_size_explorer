"""Стили, цвета и настройка ttk."""
from tkinter import ttk


class StylesMixin:
    """Цветовая схема и setup_styles."""

    def _init_colors(self):
        self.colors = {
            'bg_primary': '#0a0e17',
            'bg_secondary': '#141b2b',
            'bg_tertiary': '#1a2332',
            'bg_hover': '#1e2a3e',
            'bg_selected': '#1a3a5c',
            'bg_header': '#0d1520',
            'text_primary': '#e8edf5',
            'text_secondary': '#8899b0',
            'text_light': '#ffffff',
            'text_selected': '#64b5f6',
            'text_muted': '#5a6a80',
            'accent': '#2196f3',
            'accent_hover': '#1976d2',
            'success': '#4caf50',
            'warning': '#ff9800',
            'error': '#f44336',
            'border': '#1e2a3e',
            'cache_hit': '#00bcd4',
            'stage_scan': '#4caf50',
            'stage_cache': '#00bcd4',
            'stage_prepare': '#ff9800',
        }

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure(".",
                        background=self.colors['bg_primary'],
                        foreground=self.colors['text_primary'],
                        font=('Segoe UI', 10)
                        )
        style.configure("Modern.TFrame",
                        background=self.colors['bg_primary']
                        )

        style.configure("Card.TLabelframe",
                        background=self.colors['bg_secondary'],
                        foreground=self.colors['text_primary'],
                        relief='flat',
                        borderwidth=1,
                        bordercolor=self.colors['border']
                        )
        style.configure("Card.TLabelframe.Label",
                        background=self.colors['bg_secondary'],
                        foreground=self.colors['text_primary'],
                        font=('Segoe UI', 11, 'bold')
                        )

        style.configure("Table.Treeview",
                        background=self.colors['bg_secondary'],
                        foreground=self.colors['text_primary'],
                        fieldbackground=self.colors['bg_secondary'],
                        font=('Segoe UI', 10),
                        rowheight=32,
                        borderwidth=0
                        )
        style.map("Table.Treeview",
                  background=[('selected', self.colors['bg_selected'])],
                  foreground=[('selected', self.colors['text_selected'])]
                  )

        style.configure("Table.Treeview.Heading",
                        background=self.colors['bg_header'],
                        foreground=self.colors['text_light'],
                        font=('Segoe UI', 10, 'bold'),
                        relief='flat',
                        borderwidth=0
                        )
        style.map("Table.Treeview.Heading",
                  background=[('active', self.colors['bg_tertiary'])]
                  )

        style.configure("Primary.TButton",
                        background=self.colors['accent'],
                        foreground=self.colors['text_light'],
                        font=('Segoe UI', 10, 'bold'),
                        padding=(20, 8),
                        borderwidth=0,
                        focusthickness=0,
                        focuscolor='none'
                        )
        style.map("Primary.TButton",
                  background=[('active', self.colors['accent_hover']),
                              ('disabled', '#2a3a5e')],
                  foreground=[('disabled', self.colors['text_muted'])]
                  )

        style.configure("Secondary.TButton",
                        background=self.colors['bg_tertiary'],
                        foreground=self.colors['text_primary'],
                        font=('Segoe UI', 10),
                        padding=(15, 8),
                        borderwidth=1,
                        bordercolor=self.colors['border']
                        )
        style.map("Secondary.TButton",
                  background=[('active', self.colors['bg_hover'])]
                  )

        style.configure("Modern.TEntry",
                        fieldbackground=self.colors['bg_tertiary'],
                        foreground=self.colors['text_primary'],
                        borderwidth=1,
                        bordercolor=self.colors['border'],
                        padding=8,
                        font=('Segoe UI', 10)
                        )
        style.map("Modern.TEntry",
                  bordercolor=[('focus', self.colors['accent'])],
                  fieldbackground=[('focus', self.colors['bg_secondary'])]
                  )

        style.configure("Modern.Horizontal.TProgressbar",
                        background=self.colors['accent'],
                        troughcolor=self.colors['bg_tertiary'],
                        borderwidth=0,
                        thickness=6
                        )
        style.configure("Detail.Horizontal.TProgressbar",
                        background=self.colors['cache_hit'],
                        troughcolor=self.colors['bg_tertiary'],
                        borderwidth=0,
                        thickness=6
                        )
        style.configure("Stage.Horizontal.TProgressbar",
                        background=self.colors['stage_scan'],
                        troughcolor=self.colors['bg_tertiary'],
                        borderwidth=0,
                        thickness=4
                        )

        style.configure("Modern.TSpinbox",
                        fieldbackground=self.colors['bg_tertiary'],
                        foreground=self.colors['text_primary'],
                        background=self.colors['bg_tertiary'],
                        borderwidth=1,
                        bordercolor=self.colors['border'],
                        padding=8,
                        font=('Segoe UI', 10)
                        )
        style.map("Modern.TSpinbox",
                  fieldbackground=[('focus', self.colors['bg_secondary'])],
                  foreground=[('focus', self.colors['text_primary'])],
                  bordercolor=[('focus', self.colors['accent'])]
                  )

        style.configure("Modern.TCheckbutton",
                        background=self.colors['bg_secondary'],
                        foreground=self.colors['text_primary'],
                        font=('Segoe UI', 10)
                        )
        style.map("Modern.TCheckbutton",
                  background=[('active', self.colors['bg_hover'])],
                  foreground=[('active', self.colors['text_primary'])]
                  )

        style.configure("Modern.TCombobox",
                        fieldbackground=self.colors['bg_tertiary'],
                        foreground=self.colors['text_primary'],
                        background=self.colors['bg_tertiary'],
                        borderwidth=1,
                        bordercolor=self.colors['border'],
                        padding=8,
                        font=('Segoe UI', 10)
                        )
        style.map("Modern.TCombobox",
                  fieldbackground=[('readonly', self.colors['bg_tertiary'])],
                  foreground=[('readonly', self.colors['text_primary'])],
                  bordercolor=[('focus', self.colors['accent'])]
                  )

        style.configure("Modern.TNotebook",
                        background=self.colors['bg_primary'],
                        borderwidth=0
                        )
        style.configure("Modern.TNotebook.Tab",
                        background=self.colors['bg_secondary'],
                        foreground=self.colors['text_secondary'],
                        padding=(15, 8),
                        font=('Segoe UI', 10)
                        )
        style.map("Modern.TNotebook.Tab",
                  background=[('selected', self.colors['bg_primary'])],
                  foreground=[('selected', self.colors['text_primary'])]
                  )

        style.configure("Modern.Vertical.TScrollbar",
                        background=self.colors['bg_tertiary'],
                        troughcolor=self.colors['bg_secondary'],
                        borderwidth=0,
                        arrowcolor=self.colors['text_muted']
                        )
        style.map("Modern.Vertical.TScrollbar",
                  background=[('active', self.colors['bg_hover'])],
                  arrowcolor=[('active', self.colors['text_primary'])]
                  )

        style.configure("Modern.TSeparator",
                        background=self.colors['border'],
                        foreground=self.colors['border']
                        )