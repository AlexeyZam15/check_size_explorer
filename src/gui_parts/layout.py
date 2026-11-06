"""Основной макет: header, панели, progress, tabs, status_bar."""
from tkinter import *
from tkinter import ttk

from ..utils import debug_print
from .collapsible import CollapsibleFrame


class LayoutMixin:
    """create_layout и все create_* для общей обвязки."""

    def create_layout(self):
        debug_print("Создание интерфейса")
        self.root.configure(bg=self.colors['bg_primary'])

        outer = ttk.Frame(self.root, style="Modern.TFrame")
        outer.pack(fill=BOTH, expand=True, padx=16, pady=12)

        self.create_header(outer)

        # Восстанавливаем состояние спойлеров из настроек
        ctrl_expanded = bool(self.settings.get('spoiler_control_expanded', True))
        prog_expanded = bool(self.settings.get('spoiler_progress_expanded', True))

        self.control_collapse = CollapsibleFrame(
            outer,
            title="⚙️ Параметры сканирования",
            expanded=ctrl_expanded,
            on_toggle=lambda exp: self.settings.set(
                'spoiler_control_expanded', bool(exp))
        )
        self.control_collapse.pack(fill=X, pady=(0, 6))
        self.create_control_panel(self.control_collapse.body)

        self.progress_collapse = CollapsibleFrame(
            outer,
            title="📊 Прогресс",
            expanded=prog_expanded,
            on_toggle=lambda exp: self.settings.set(
                'spoiler_progress_expanded', bool(exp))
        )
        self.progress_collapse.pack(fill=X, pady=(0, 6))
        self.create_progress_bars(self.progress_collapse.body)

        self.create_navigation_panel(outer)
        self.create_tabs(outer)
        self.create_status_bar(outer)

        self.add_log("💡 Горячие клавиши:", "info")
        self.add_log("   • Ctrl+C - копировать выделенный текст (в логах)", "info")
        self.add_log("   • Ctrl+C - копировать путь (в таблице результатов)", "info")
        self.add_log("   • Ctrl+A - выделить всё (в логах или таблице)", "info")
        self.add_log("   • Двойной клик по папке - переход в неё", "info")
        self.add_log("   • Клик по заголовку ⚙️ / 📊 — свернуть/развернуть блок", "info")
        self.add_log("   • Состояние спойлеров и мин. глубина запоминаются", "info")
        self.add_log(f"⚡ Оптимизация: {self.max_workers} потоков, батч {self.batch_size} папок", "info")

    def create_header(self, parent):
        header_frame = ttk.Frame(parent, style="Modern.TFrame")
        header_frame.pack(fill=X, pady=(0, 8))

        logo_frame = ttk.Frame(header_frame, style="Modern.TFrame")
        logo_frame.pack(side=LEFT)

        ttk.Label(logo_frame, text="📂", font=('Segoe UI', 22)).pack(side=LEFT, padx=(0, 6))
        ttk.Label(logo_frame, text="Disk Analyzer",
                  font=('Segoe UI', 16, 'bold'),
                  foreground=self.colors['text_primary']).pack(side=LEFT)
        ttk.Label(logo_frame, text="Pro",
                  font=('Segoe UI', 11, 'bold'),
                  foreground=self.colors['accent']).pack(side=LEFT, padx=(4, 0))
        ttk.Label(logo_frame, text="🧠 Умный кэш",
                  font=('Segoe UI', 9),
                  foreground=self.colors['stage_scan']).pack(side=LEFT, padx=(8, 0))

        status_frame = ttk.Frame(header_frame, style="Modern.TFrame")
        status_frame.pack(side=RIGHT)

        self.status_indicator = Canvas(status_frame, width=10, height=10,
                                       bg=self.colors['bg_primary'], highlightthickness=0)
        self.status_indicator.pack(side=LEFT, padx=(0, 6))
        self.status_indicator.create_oval(2, 2, 8, 8, fill=self.colors['success'], tags="indicator")

        self.status_text = ttk.Label(status_frame, text="Готов к работе",
                                     font=('Segoe UI', 10),
                                     foreground=self.colors['text_secondary'])
        self.status_text.pack(side=LEFT)

    def create_control_panel(self, body):
        ttk.Label(body, text="Диски для сканирования:",
                  font=('Segoe UI', 9, 'bold'),
                  foreground=self.colors['text_secondary']).pack(anchor=W, pady=(0, 2))

        self.drives_frame = ttk.Frame(body, style="Modern.TFrame")
        self.drives_frame.pack(fill=X, pady=(0, 6))
        self._populate_drive_checkboxes()

        manual_top = ttk.Frame(body, style="Modern.TFrame")
        manual_top.pack(fill=X)

        ttk.Checkbutton(manual_top, text="Или сканировать конкретную папку:",
                        variable=self.selected_custom_path,
                        style="Modern.TCheckbutton").pack(side=LEFT)

        path_input_frame = ttk.Frame(body, style="Modern.TFrame")
        path_input_frame.pack(fill=X, pady=(4, 6))

        self.path_entry = ttk.Entry(path_input_frame,
                                    textvariable=self.root_path,
                                    style="Modern.TEntry")
        self.path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 6))

        ttk.Button(path_input_frame, text="📁 Обзор",
                   command=self.browse_folder,
                   style="Secondary.TButton", width=12).pack(side=LEFT)

        bottom_row = ttk.Frame(body, style="Modern.TFrame")
        bottom_row.pack(fill=X)

        opts_frame = ttk.Frame(bottom_row, style="Modern.TFrame")
        opts_frame.pack(side=LEFT, anchor=N)

        self.cache_check = ttk.Checkbutton(opts_frame,
                                           text="Использовать кэш ⚡",
                                           variable=self.use_cache,
                                           style="Modern.TCheckbutton")
        self.cache_check.pack(anchor=W)

        ttk.Label(opts_frame, text="(сканирует только новые папки)",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']).pack(anchor=W, padx=(20, 0))

        actions_frame = ttk.Frame(bottom_row, style="Modern.TFrame")
        actions_frame.pack(side=RIGHT, anchor=N)

        self.scan_btn = ttk.Button(actions_frame, text="⚡ Начать сканирование",
                                   command=self.start_scan, style="Primary.TButton")
        self.scan_btn.pack(side=LEFT, padx=(0, 6))

        self.cancel_btn = ttk.Button(actions_frame, text="⏹ Остановить",
                                     command=self.cancel_scan,
                                     style="Secondary.TButton", state=DISABLED)
        self.cancel_btn.pack(side=LEFT)

    def create_progress_bars(self, body):
        row1 = ttk.Frame(body, style="Modern.TFrame")
        row1.pack(fill=X, pady=(0, 4))

        ttk.Label(row1, text="Общий:",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']).pack(side=LEFT, padx=(0, 6))

        self.progress_var = DoubleVar()
        self.progress_bar = ttk.Progressbar(row1, variable=self.progress_var,
                                            maximum=100,
                                            style="Modern.Horizontal.TProgressbar")
        self.progress_bar.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        self.progress_percent = ttk.Label(row1, text="0%",
                                          font=('Segoe UI', 9, 'bold'),
                                          foreground=self.colors['accent'], width=6)
        self.progress_percent.pack(side=RIGHT)

        row2 = ttk.Frame(body, style="Modern.TFrame")
        row2.pack(fill=X, pady=(0, 2))

        ttk.Label(row2, text="Этап:",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']).pack(side=LEFT, padx=(0, 6))

        self.folder_progress_var = DoubleVar()
        self.folder_progress_bar = ttk.Progressbar(row2,
                                                   variable=self.folder_progress_var,
                                                   maximum=100,
                                                   style="Detail.Horizontal.TProgressbar")
        self.folder_progress_bar.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        self.folder_progress_percent = ttk.Label(row2, text="0%",
                                                 font=('Segoe UI', 9, 'bold'),
                                                 foreground=self.colors['cache_hit'], width=6)
        self.folder_progress_percent.pack(side=RIGHT)

        row3 = ttk.Frame(body, style="Modern.TFrame")
        row3.pack(fill=X)

        self.stage_label = ttk.Label(row3, text="🔄 Ожидание",
                                     font=('Segoe UI', 8, 'bold'),
                                     foreground=self.colors['text_secondary'])
        self.stage_label.pack(side=LEFT)

        self.current_folder_label = ttk.Label(row3, text="",
                                              font=('Segoe UI', 8),
                                              foreground=self.colors['text_secondary'])
        self.current_folder_label.pack(side=LEFT, padx=(10, 0))

        self.files_count_label = ttk.Label(row3, text="📄 0",
                                           font=('Segoe UI', 8),
                                           foreground=self.colors['text_muted'])
        self.files_count_label.pack(side=RIGHT, padx=(10, 0))

        self.scan_status = ttk.Label(row3, text="⏳ Ожидание",
                                     font=('Segoe UI', 8),
                                     foreground=self.colors['text_muted'])
        self.scan_status.pack(side=RIGHT)

    def create_navigation_panel(self, parent):
        nav_frame = ttk.Frame(parent, style="Modern.TFrame")
        nav_frame.pack(fill=X, pady=(0, 6))

        left = ttk.Frame(nav_frame, style="Modern.TFrame")
        left.pack(side=LEFT)
        self.back_btn = ttk.Button(left, text="◀ Назад",
                                   command=self.go_back,
                                   style="Secondary.TButton", state=DISABLED)
        self.back_btn.pack(side=LEFT, padx=(0, 8))

        right = ttk.Frame(nav_frame, style="Modern.TFrame")
        right.pack(side=RIGHT)

        ttk.Button(right, text="📊 Сканировать все",
                   command=self.scan_all_from_current,
                   style="Secondary.TButton").pack(side=LEFT, padx=(4, 0))
        ttk.Button(right, text="🔄 Обновить",
                   command=self.refresh_current_folder,
                   style="Secondary.TButton").pack(side=LEFT, padx=(4, 0))
        ttk.Button(right, text="📂 Открыть папку",
                   command=self.open_current_folder_in_explorer,
                   style="Secondary.TButton").pack(side=LEFT, padx=(4, 0))
        ttk.Button(right, text="🏠 Корень",
                   command=self.go_to_scan_root,
                   style="Secondary.TButton").pack(side=LEFT, padx=(4, 0))

        self.path_label = ttk.Label(nav_frame, text="📁 Текущая папка: не выбрана",
                                    font=('Segoe UI', 9),
                                    foreground=self.colors['text_secondary'])
        self.path_label.pack(side=LEFT, fill=X, expand=True, padx=(6, 6))

    def create_tabs(self, parent):
        notebook = ttk.Notebook(parent, style="Modern.TNotebook")
        notebook.pack(fill=BOTH, expand=True)

        results_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(results_tab, text="📊 Результаты")
        self.create_results_tab(results_tab)

        top_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(top_tab, text="🔥 Самые большие")
        self.create_top_tab(top_tab)

        logs_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(logs_tab, text="📝 Логи")
        self.create_logs_tab(logs_tab)

        cache_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(cache_tab, text="💾 Кэш")
        self.create_cache_tab(cache_tab)

    def create_status_bar(self, parent):
        status_frame = ttk.Frame(parent, style="Modern.TFrame")
        status_frame.pack(fill=X, pady=(6, 0))

        ttk.Separator(status_frame, orient='horizontal',
                      style="Modern.TSeparator").pack(fill=X, pady=(0, 4))

        info_frame = ttk.Frame(status_frame, style="Modern.TFrame")
        info_frame.pack(fill=X)

        self.status_info = ttk.Label(info_frame, text="Готов к работе ⚡",
                                     font=('Segoe UI', 9),
                                     foreground=self.colors['text_secondary'])
        self.status_info.pack(side=LEFT)

        ttk.Label(info_frame,
                  text=f"💾 Кэш: {self.cache.get_cache_stats()['total_entries']} записей",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']).pack(side=RIGHT, padx=(0, 12))

        ttk.Label(info_frame, text="v5.8 • Спойлеры + глубина запоминаются",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']).pack(side=RIGHT)