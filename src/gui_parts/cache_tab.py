"""Вкладка «Кэш»: статистика, управление, список кэшированных папок."""
import os
import gc
from datetime import datetime

from tkinter import *
from tkinter import ttk, messagebox

from ..utils import debug_print, format_size


class CacheTabMixin:
    """create_cache_tab + refresh/clear/save/repair."""

    def create_cache_tab(self, parent):
        # Верх: статистика (компактный grid 4 в ряд)
        info_frame = ttk.LabelFrame(parent, text="📊 Статистика кэша",
                                    style="Card.TLabelframe", padding=(12, 8))
        info_frame.pack(fill=X, pady=(0, 6))

        stats = self.cache.get_cache_stats()
        stats_grid = ttk.Frame(info_frame, style="Modern.TFrame")
        stats_grid.pack(fill=X)

        stats_items = [
            ("📁 Всего записей:", f"{stats['total_entries']:,}"),
            ("💾 Размер кэша:", f"{stats['cache_size_mb']:.2f} МБ"),
            ("🎯 Попаданий:", f"{stats['hits']:,}"),
            ("❌ Промахов:", f"{stats['misses']:,}"),
            ("📊 Точность:", f"{stats['hit_rate']:.1f}%"),
            ("🔄 Частичных:", f"{stats['partial_updates']:,}"),
            ("📦 Полных:", f"{stats['full_updates']:,}"),
        ]

        PER_ROW = 4
        for idx, (label, value) in enumerate(stats_items):
            r = idx // PER_ROW
            c = idx % PER_ROW
            cell = ttk.Frame(stats_grid, style="Modern.TFrame")
            cell.grid(row=r, column=c, sticky="w", padx=(0, 18), pady=1)
            ttk.Label(cell, text=label, font=('Segoe UI', 9),
                      foreground=self.colors['text_secondary']).pack(side=LEFT)
            ttk.Label(cell, text=value, font=('Segoe UI', 9, 'bold'),
                      foreground=self.colors['text_primary']).pack(side=LEFT, padx=(4, 0))

        # Кнопки управления (фикс. высота)
        control_frame = ttk.Frame(parent, style="Modern.TFrame")
        control_frame.pack(fill=X, pady=(0, 6))

        ttk.Button(control_frame, text="🗑️ Очистить кэш",
                   command=self.clear_cache,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))
        ttk.Button(control_frame, text="💾 Сохранить кэш",
                   command=self.save_cache,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))
        ttk.Button(control_frame, text="🔧 Восстановить кэш",
                   command=self.repair_cache,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))
        ttk.Button(control_frame, text="📊 Обновить статистику",
                   command=self.refresh_cache_list,
                   style="Secondary.TButton").pack(side=LEFT)

        # Таблица — на всё оставшееся место
        list_frame = ttk.LabelFrame(parent, text="📋 Кэшированные папки (последние 100)",
                                    style="Card.TLabelframe", padding=(8, 6))
        list_frame.pack(fill=BOTH, expand=True)

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        columns = ("#", "📁 Папка", "📦 Размер", "📄 Файлы", "🕐 Последнее обновление")
        self.cache_tree = ttk.Treeview(list_frame, columns=columns,
                                       show="headings",
                                       style="Table.Treeview", height=5)

        self.cache_tree.heading("#", text="#", anchor=CENTER)
        self.cache_tree.heading("📁 Папка", text="📁 Папка")
        self.cache_tree.heading("📦 Размер", text="📦 Размер", anchor=E)
        self.cache_tree.heading("📄 Файлы", text="📄 Файлы", anchor=E)
        self.cache_tree.heading("🕐 Последнее обновление", text="🕐 Последнее обновление")

        self.cache_tree.column("#", width=50, anchor=CENTER, minwidth=40)
        self.cache_tree.column("📁 Папка", width=350, minwidth=150)
        self.cache_tree.column("📦 Размер", width=130, anchor=E, minwidth=100)
        self.cache_tree.column("📄 Файлы", width=80, anchor=E, minwidth=70)
        self.cache_tree.column("🕐 Последнее обновление", width=180, anchor=CENTER,
                               minwidth=150)

        v_scroll = ttk.Scrollbar(list_frame, orient=VERTICAL,
                                 command=self.cache_tree.yview,
                                 style="Modern.Vertical.TScrollbar")
        self.cache_tree.configure(yscrollcommand=v_scroll.set)

        self.cache_tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")

        self.refresh_cache_list()

    def refresh_cache_list(self):
        self.cache_tree.delete(*self.cache_tree.get_children())
        try:
            import sqlite3
            conn = sqlite3.connect(self.cache.cache_file, timeout=30)
            cursor = conn.cursor()
            cursor.execute('''
                           SELECT path, total_size, file_count, timestamp
                           FROM cache
                           ORDER BY timestamp DESC
                               LIMIT 100
                           ''')
            rows = cursor.fetchall()
            conn.close()

            for i, row in enumerate(rows, 1):
                path, total_size, file_count, timestamp = row
                size_str = format_size(total_size)
                timestamp_str = (datetime.fromtimestamp(timestamp)
                                 .strftime("%Y-%m-%d %H:%M:%S") if timestamp
                                 else "Неизвестно")
                folder_name = os.path.basename(path) if path else "Корень"
                self.cache_tree.insert("", END, values=(
                    i, folder_name, size_str, f"{file_count:,}", timestamp_str))
        except Exception as e:
            debug_print(f"Ошибка обновления списка кэша: {e}")

    def clear_cache(self):
        if messagebox.askyesno("Подтверждение",
                               "Вы уверены, что хотите очистить весь кэш?"):
            self.cache.clear_cache()
            self.cache_hits = 0
            self.cache_misses = 0
            self.scanned_folders_cache = {}
            self.refresh_cache_list()
            self.add_log("🗑️ Кэш полностью очищен", "warning")
            messagebox.showinfo("Успех", "Кэш успешно очищен")
            gc.collect()

    def save_cache(self):
        self.cache.save_cache()
        self.add_log("💾 Кэш сохранен в файл", "success")
        messagebox.showinfo("Успех", "Кэш сохранен")

    def repair_cache(self):
        if messagebox.askyesno("Подтверждение",
                               "Восстановление кэша может занять некоторое время.\n"
                               "Продолжить?"):
            self.add_log("🔧 Начало восстановления кэша...", "info")
            self.scan_status.config(text="⏳ Восстановление кэша...")
            self.root.update()
            try:
                self.cache._repair_database()
                valid_count, total_size = self.cache.validate_cache()
                self.cache.save_cache()
                self.refresh_cache_list()
                self.add_log(
                    f"✅ Восстановление завершено: {valid_count} записей, "
                    f"{format_size(total_size)}", "success")
                self.scan_status.config(text=f"✅ Восстановлено {valid_count} записей")
                messagebox.showinfo(
                    "Успех",
                    f"Восстановление кэша завершено!\n"
                    f"Записей: {valid_count}\n"
                    f"Размер: {format_size(total_size)}")
            except Exception as e:
                self.add_log(f"❌ Ошибка восстановления: {e}", "error")
                messagebox.showerror("Ошибка",
                                     f"Не удалось восстановить кэш:\n{e}")

    def collect_all_folders_cached(self, path):
        cached_folders = self.cache.get_cached_folder_list(path)
        if cached_folders is not None:
            self.add_log(f"💾 Загружено {len(cached_folders)} папок из кэша", "cache")
            return cached_folders

        self.add_log("📂 Сбор всех папок (первый раз, это может занять время)...",
                     "info")
        all_folders = []
        collected_count = 0
        try:
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [d for d in dirs if d not in self.system_folders]
                for d in dirs:
                    all_folders.append(os.path.join(root, d))
                    collected_count += 1
                    if collected_count % 500 == 0:
                        self.root.after(0, lambda c=collected_count:
                        self.scan_status.config(
                            text=f"⏳ Сбор папок... (найдено: {c})"))
        except (PermissionError, OSError):
            pass

        if all_folders:
            self.cache.save_folder_list(path, all_folders)
            self.add_log(f"💾 Сохранено {len(all_folders)} папок в кэш", "cache")
        return all_folders