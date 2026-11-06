"""Детали, контекстное меню, открытие папок, on_closing, browse."""
import os
import gc

from tkinter import *
from tkinter import ttk, messagebox, filedialog

from ..utils import debug_print, format_size


class DetailsMixin:
    """Остальные обработчики: окно деталей, контекст-меню, открытие, close."""

    def open_current_folder_in_explorer(self):
        path = self.current_nav_path
        if not path:
            self.add_log("⚠️ Нет активной папки для открытия", "warning")
            return
        if not os.path.exists(path):
            self.add_log(f"⚠️ Папка не существует: {path}", "warning")
            return
        try:
            if os.name == 'nt':
                os.startfile(path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', path])
            self.add_log(f"📂 Открыта папка: {path}", "info")
        except Exception as e:
            self.add_log(f"❌ Ошибка открытия папки: {e}", "error")

    def open_folder(self, event=None):
        selection = self.tree.selection()
        if selection:
            values = self.tree.item(selection[0], 'values')
            if values and len(values) > 4:
                path = values[4]
                if os.path.exists(path):
                    try:
                        os.startfile(path)
                        self.add_log(f"📂 Открыта папка: {path}", "info")
                    except Exception:
                        try:
                            import subprocess
                            subprocess.Popen(['explorer', path])
                        except Exception:
                            messagebox.showerror("Ошибка",
                                                 "Не удалось открыть папку")
                else:
                    messagebox.showerror("Ошибка", "Папка не существует")

    def open_folder_from_path(self, path):
        if os.path.exists(path):
            try:
                os.startfile(path)
            except Exception:
                try:
                    import subprocess
                    subprocess.Popen(['explorer', path])
                except Exception:
                    pass

    def copy_path_from_path(self, path):
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        self.add_log(f"📋 Скопирован путь: {path}", "success")

    def show_details(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Информация",
                                "Выберите папку для просмотра деталей")
            return

        values = self.tree.item(selection[0], 'values')
        if not values or len(values) < 5:
            return

        name = values[1].split(' ', 1)[-1] if ' ' in values[1] else values[1]
        size_str = values[2]
        source = values[3]
        path = values[4]

        size_bytes = 0
        depth = 0
        file_count = 0
        for item in self.results:
            if item.get('path') == path:
                size_bytes = item.get('size', 0)
                depth = item.get('depth', 0)
                file_count = item.get('file_count', 0)
                break

        details_window = Toplevel(self.root)
        details_window.title(f"Детали: {name}")
        details_window.geometry("550x480")
        details_window.configure(bg=self.colors['bg_secondary'])
        details_window.resizable(False, False)

        main_frame = ttk.Frame(details_window, style="Modern.TFrame")
        main_frame.pack(fill=BOTH, expand=True, padx=25, pady=25)

        ttk.Label(main_frame, text=f"📁 {name}",
                  font=('Segoe UI', 16, 'bold'),
                  foreground=self.colors['text_primary']).pack(
            anchor=W, pady=(0, 20))

        info_frame = ttk.Frame(main_frame, style="Modern.TFrame")
        info_frame.pack(fill=X, pady=(0, 20))

        info_items = [
            ("Размер:", size_str),
            ("В байтах:", f"{size_bytes:,}"),
            ("Источник:", source),
            ("Файлов:", f"{file_count:,}" if file_count > 0 else "н/д"),
            ("Уровень вложенности:", f"{depth}"),
            ("Путь:", path),
        ]

        for label, value in info_items:
            row = ttk.Frame(info_frame, style="Modern.TFrame")
            row.pack(fill=X, pady=5)
            ttk.Label(row, text=label, font=('Segoe UI', 10, 'bold'),
                      foreground=self.colors['text_secondary'],
                      width=16).pack(side=LEFT)
            ttk.Label(row, text=value, font=('Segoe UI', 10),
                      foreground=self.colors['text_primary'],
                      wraplength=350).pack(side=LEFT, fill=X, expand=True)

        btn_frame = ttk.Frame(main_frame, style="Modern.TFrame")
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame, text="📂 Открыть папку",
                   command=lambda: self.open_folder_from_path(path),
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="📋 Копировать путь",
                   command=lambda: self.copy_path_from_path(path),
                   style="Secondary.TButton").pack(side=LEFT)

    def show_context_menu(self, event):
        selection = self.tree.selection()
        if selection:
            menu = Menu(self.root, tearoff=0,
                        bg=self.colors['bg_secondary'],
                        fg=self.colors['text_primary'],
                        activebackground=self.colors['bg_selected'],
                        activeforeground=self.colors['text_light'])
            menu.add_command(label="📂 Перейти в папку",
                             command=self.navigate_to_folder)
            menu.add_command(label="📂 Открыть папку",
                             command=lambda: self.open_folder(None))
            menu.add_command(label="📋 Копировать путь (Ctrl+C)",
                             command=self.copy_path_from_tree)
            menu.add_command(label="📊 Показать детали",
                             command=self.show_details)
            menu.add_separator()
            menu.add_command(label="📋 Выделить всё (Ctrl+A)",
                             command=self.select_all_rows)
            menu.post(event.x_root, event.y_root)

    def set_status(self, text, status_type="info"):
        if status_type == "scanning":
            color = self.colors['warning']
        elif status_type == "success":
            color = self.colors['success']
        elif status_type == "error":
            color = self.colors['error']
        else:
            color = self.colors['text_secondary']

        self.status_indicator.delete("indicator")
        self.status_indicator.create_oval(2, 2, 8, 8, fill=color, tags="indicator")
        self.status_text.config(text=text)
        self.status_info.config(text=text)

    def clear_results(self):
        """Очистка результатов. current_file_label больше не создаётся —
        в новом layout прогресс компактный, отдельной строки 'Файл:' нет."""
        self.tree.delete(*self.tree.get_children())
        self.results = []
        self.total_size = 0
        self.last_scan_root = ""
        self.last_scan_results = []
        self.last_scan_total_size = 0
        self.table_state_cache = {}
        self.progress_var.set(0)
        self.progress_percent.config(text="0%")
        self.folder_progress_var.set(0)
        self.folder_progress_percent.config(text="0%")
        self.scan_status.config(text="Результаты очищены")
        self.stage_label.config(text="🔄 Ожидание",
                                foreground=self.colors['text_secondary'])
        if hasattr(self, 'current_folder_label'):
            try:
                self.current_folder_label.config(text="")
            except Exception:
                pass
        if hasattr(self, 'files_count_label'):
            try:
                self.files_count_label.config(text="📄 0")
            except Exception:
                pass
        self.add_log("🗑️ Результаты очищены", "info")
        gc.collect()

    def load_default_drive(self):
        debug_print("Загрузка диска по умолчанию")
        if os.name == 'nt':
            drives = [f"{d}:\\" for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                      if os.path.exists(f"{d}:\\")]
            if drives:
                self.root_path.set(drives[0])
                self.add_log(f"Выбран диск по умолчанию: {drives[0]}", "info")
        else:
            self.root_path.set(os.path.expanduser("~"))
            self.add_log(
                f"Выбрана домашняя папка: {self.root_path.get()}", "info")

    def browse_folder(self):
        folder = filedialog.askdirectory(
            title="Выберите папку для анализа",
            initialdir=self.root_path.get() if self.root_path.get() else "/")
        if folder:
            self.root_path.set(folder)
            self.settings.set('last_path', folder)
            self.add_log(f"📁 Выбрана папка: {folder}", "info")
            self.set_status("Папка выбрана", "info")
            self.scan_status.config(text="⏳ Загрузка папки...")
            self.progress_var.set(0)
            self.progress_percent.config(text="0%")
            self.root.after(100, lambda: self.navigate_to_path(folder))

    def on_closing(self):
        try:
            try:
                saved_drives = [d for d, v in (self.selected_drives or {}).items()
                                if v.get()]
            except Exception:
                saved_drives = []
            self.settings.update(
                use_cache=self.use_cache.get(),
                last_path=self.root_path.get(),
                batch_size=self.batch_size,
                max_workers=self.max_workers,
                window_geometry=self.root.geometry(),
                window_state='zoomed' if self.root.state() == 'zoomed' else 'normal',
                selected_drives=saved_drives,
                top_folders_min_depth=self.top_folders_min_depth,
                spoiler_control_expanded=self.control_collapse.is_expanded,
                spoiler_progress_expanded=self.progress_collapse.is_expanded
            )
        except Exception:
            pass

        self.cache.save_cache()
        debug_print("Настройки и кэш сохранены, программа закрывается")
        self.root.destroy()