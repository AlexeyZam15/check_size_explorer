"""Вкладка «Результаты»: таблица + навигация по папкам."""
import os
import threading
import time
import gc

from tkinter import *
from tkinter import ttk, messagebox

from ..utils import debug_print, format_size


class ResultsTabMixin:
    """Таблица результатов, отображение, пакетная вставка, навигация."""

    # ---------- создание таблицы ----------

    def create_results_tab(self, parent):
        # Панель действий упаковываем ПЕРВОЙ через side=BOTTOM — тогда она
        # всегда получает свою высоту, а таблица забирает всё остальное.
        actions_frame = ttk.Frame(parent, style="Modern.TFrame")
        actions_frame.pack(side=BOTTOM, fill=X, pady=(6, 0))

        ttk.Button(actions_frame, text="📂 Открыть папку",
                   command=self.open_folder,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))
        ttk.Button(actions_frame, text="📋 Копировать путь",
                   command=self.copy_path_from_tree,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))
        ttk.Button(actions_frame, text="📊 Детали",
                   command=self.show_details,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))
        ttk.Button(actions_frame, text="🗑️ Очистить",
                   command=self.clear_results,
                   style="Secondary.TButton").pack(side=LEFT)

        ttk.Label(actions_frame,
                  text="💡 Двойной клик - переход в папку | Ctrl+C - копировать путь",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']).pack(side=RIGHT)

        table_frame = ttk.Frame(parent, style="Modern.TFrame")
        table_frame.pack(fill=BOTH, expand=True)

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        columns = ("#", "📁 Имя", "📦 Размер", "⚡ Источник", "🔗 Путь")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                 style="Table.Treeview")

        self.tree.heading("#", text="#", anchor=CENTER)
        self.tree.heading("📁 Имя", text="📁 Имя")
        self.tree.heading("📦 Размер", text="📦 Размер", anchor=E)
        self.tree.heading("⚡ Источник", text="⚡ Источник", anchor=CENTER)
        self.tree.heading("🔗 Путь", text="🔗 Путь")

        self.tree.column("#", width=50, anchor=CENTER, minwidth=40)
        self.tree.column("📁 Имя", width=230, minwidth=150)
        self.tree.column("📦 Размер", width=130, anchor=E, minwidth=100)
        self.tree.column("⚡ Источник", width=80, anchor=CENTER, minwidth=70)
        self.tree.column("🔗 Путь", width=470, minwidth=250)

        v_scroll = ttk.Scrollbar(table_frame, orient=VERTICAL, command=self.tree.yview,
                                 style="Modern.Vertical.TScrollbar")
        h_scroll = ttk.Scrollbar(table_frame, orient=HORIZONTAL, command=self.tree.xview,
                                 style="Modern.Vertical.TScrollbar")
        self.tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")

        self.tree.bind("<Double-1>", self.navigate_to_folder)
        self.tree.bind("<Button-3>", self.show_context_menu)

    # ---------- отображение ----------

    def _display_folder_items(self, items, source_label=""):
        if not items:
            self.tree.delete(*self.tree.get_children())
            self.results = []
            self.scan_status.config(text="📂 Папка пуста")
            self.set_status("Папка пуста", "info")
            return

        current_path = self.current_nav_path
        existing_items = self.tree.get_children()
        if existing_items and len(existing_items) == len(items):
            first_item = self.tree.item(existing_items[0], 'values')
            if first_item and len(first_item) >= 5:
                first_path = first_item[4]
                if items and items[0].get('path', '') == first_path:
                    debug_print(f"✅ Данные уже загружены, пропускаем вставку для {current_path}")
                    self.results = items
                    self.scan_status.config(
                        text=f"✅ {source_label}: {len(items)} элементов" if source_label
                        else f"✅ {len(items)} элементов")
                    self.set_status(f"{len(items)} элементов", "success")
                    self.stage_label.config(text="✅ Готово",
                                            foreground=self.colors['success'])
                    if self.progress_var.get() < 100:
                        self.progress_var.set(100)
                        self.progress_percent.config(text="100%")
                        self.folder_progress_var.set(100)
                        self.folder_progress_percent.config(text="100%")
                    return

        self.tree.delete(*self.tree.get_children())
        self.results = []

        total_items = len(items)
        debug_print(f"📊 Отображение {total_items} элементов для {current_path}")

        if total_items <= 500:
            self._insert_items_immediate(items)
            self._update_restore_status(total_items)
            self.table_state_cache[current_path] = items
            debug_print(f"✅ Добавлено {total_items} строк (мгновенно)")
            return

        self._insert_items_batched(items, source_label, total_items)

    def _insert_items_immediate(self, items_data):
        self.tree.configure(selectmode='none')

        for i, item in enumerate(items_data, 1):
            if isinstance(item, dict):
                name = item.get('name', '')
                size_str = item.get('size_str', '0 Б')
                source = item.get('source', '📁')
                item_path = item.get('path', '')
                size = item.get('size', 0)
                is_file = item.get('is_file', False)

                if is_file:
                    ext = os.path.splitext(name)[1].lower()
                    emoji_map = {
                        '.txt': '📄', '.log': '📄', '.md': '📄',
                        '.py': '🐍', '.js': '📜', '.html': '🌐', '.css': '🎨',
                        '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️',
                        '.bmp': '🖼️', '.svg': '🖼️',
                        '.mp3': '🎵', '.wav': '🎵', '.flac': '🎵',
                        '.mp4': '🎬', '.avi': '🎬', '.mkv': '🎬', '.mov': '🎬',
                        '.zip': '📦', '.rar': '📦', '.7z': '📦', '.tar': '📦', '.gz': '📦',
                        '.exe': '⚙️', '.msi': '⚙️', '.dll': '🔧',
                        '.pdf': '📕', '.doc': '📘', '.docx': '📘',
                        '.xls': '📊', '.xlsx': '📊',
                        '.ppt': '📽️', '.pptx': '📽️',
                        '.iso': '💿', '.img': '💿',
                        '.psd': '🎨', '.ai': '🎨',
                        '.json': '📋', '.xml': '📋', '.yaml': '📋', '.yml': '📋',
                        '.sql': '🗄️', '.db': '🗄️',
                        '.sh': '💻', '.bat': '💻', '.cmd': '💻',
                    }
                    emoji = emoji_map.get(ext, '📄')
                else:
                    if size > 1024 ** 4:
                        emoji = "🔴📁"
                    elif size > 1024 ** 3:
                        emoji = "🟡📁"
                    elif size > 1024 ** 2:
                        emoji = "🟢📁"
                    else:
                        emoji = "⚪📁"
            else:
                if len(item) >= 5:
                    name = item[1].split(' ', 1)[-1] if ' ' in item[1] else item[1]
                    size_str = item[2]
                    source = item[3]
                    item_path = item[4]
                    emoji = item[1].split(' ')[0] if item[1].startswith(('🔴', '🟡', '🟢', '⚪')) else "📁"
                else:
                    continue

            self.tree.insert("", END, values=(i, f"{emoji} {name}", size_str,
                                              source, item_path))

        self.tree.configure(selectmode='extended')
        self.root.update_idletasks()

        self.results = items_data
        self._update_restore_status(len(items_data))

    def _insert_items_batched(self, items, source_label, total_items):
        batch_size = 200
        current_index = 0

        self.scan_status.config(text=f"⏳ Загрузка: 0/{total_items}")
        self.stage_label.config(text=f"📊 {source_label}: загрузка...",
                                foreground=self.colors['stage_scan'])
        self.progress_var.set(0)
        self.progress_percent.config(text="0%")
        self.folder_progress_var.set(0)
        self.folder_progress_percent.config(text="0%")

        def insert_batch():
            nonlocal current_index
            start = current_index
            end = min(current_index + batch_size, total_items)
            batch = items[start:end]

            for i, item in enumerate(batch, start + 1):
                if isinstance(item, dict):
                    name = item.get('name', '')
                    size_str = item.get('size_str', '0 Б')
                    source = item.get('source', '📁')
                    item_path = item.get('path', '')
                    size = item.get('size', 0)
                    is_file = item.get('is_file', False)

                    if is_file:
                        emoji = '📄'
                    else:
                        if size > 1024 ** 4:
                            emoji = "🔴📁"
                        elif size > 1024 ** 3:
                            emoji = "🟡📁"
                        elif size > 1024 ** 2:
                            emoji = "🟢📁"
                        else:
                            emoji = "⚪📁"
                else:
                    continue

                self.tree.insert("", END, values=(i, f"{emoji} {name}", size_str,
                                                  source, item_path))

            current_index = end

            if total_items > 0:
                progress = int((current_index / total_items) * 100)
                self.progress_var.set(progress)
                self.progress_percent.config(text=f"{progress}%")
                self.folder_progress_var.set(progress)
                self.folder_progress_percent.config(text=f"{progress}%")
                self.scan_status.config(text=f"⏳ Загрузка: {current_index}/{total_items} ({progress}%)")

            if current_index < total_items:
                self.root.after(5, insert_batch)
            else:
                self.results = items
                self.scan_status.config(
                    text=f"✅ {source_label}: {total_items} элементов" if source_label
                    else f"✅ {total_items} элементов")
                self.set_status(f"{total_items} элементов", "success")
                self.progress_var.set(100)
                self.progress_percent.config(text="100%")
                self.folder_progress_var.set(100)
                self.folder_progress_percent.config(text="100%")
                self.stage_label.config(text="✅ Готово",
                                        foreground=self.colors['success'])
                self.scanned_folders_cache[self.current_nav_path] = items

        self.root.after(10, insert_batch)

    def _update_restore_status(self, count):
        self.scan_status.config(text=f"✅ {count} папок")
        self.set_status(f"{count} папок", "success")
        self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])

        if self.progress_var.get() < 100:
            self.progress_var.set(100)
            self.progress_percent.config(text="100%")
            self.folder_progress_var.set(100)
            self.folder_progress_percent.config(text="100%")

    # ---------- навигация ----------

    def navigate_to_folder(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], 'values')
        if not values or len(values) < 5:
            return
        path = values[4]
        if not os.path.exists(path) or not os.path.isdir(path):
            self.add_log(f"⚠️ Папка не существует или недоступна: {path}", "warning")
            return
        self.navigate_to_path(path)

    def navigate_to_path(self, path):
        debug_print(f"Навигация в: {path}")
        if not os.path.exists(path) or not os.path.isdir(path):
            self.add_log(f"⚠️ Невозможно перейти в: {path}", "warning")
            return

        if self.current_nav_path and self.current_nav_path != path:
            if self.current_nav_path != self.last_scan_root:
                current_items = self.tree.get_children()
                if current_items:
                    items_data = []
                    for item_id in current_items:
                        values = self.tree.item(item_id, 'values')
                        if values and len(values) >= 5:
                            name = values[1].split(' ', 1)[-1] if ' ' in values[1] else values[1]
                            items_data.append({
                                'name': name,
                                'size_str': values[2],
                                'source': values[3],
                                'path': values[4],
                            })
                    self.table_state_cache[self.current_nav_path] = items_data

            self.navigation_history.append(self.current_nav_path)

        self.current_nav_path = path
        self.update_navigation_ui()
        self.add_log(f"📂 Переход в папку: {path}", "info")
        self.path_label.config(text=f"📁 {path}")
        self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)

        self.root.after(100, lambda: self.scan_current_folder(path))

    def go_back(self):
        if not self.navigation_history:
            self.add_log("⚠️ История пуста", "warning")
            return

        previous_path = self.navigation_history[-1]

        if previous_path == self.last_scan_root and self.last_scan_root_subfolders:
            self.navigation_history.pop()
            self.current_nav_path = previous_path
            self.update_navigation_ui()
            self.path_label.config(text=f"📁 {previous_path}")
            self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)
            self.add_log(f"◀ Возврат в корень: {previous_path}", "info")
            self._display_folder_items(self.last_scan_root_subfolders,
                                       "📊 Результаты сканирования")
            return

        if self.current_nav_path and self.current_nav_path != self.last_scan_root:
            current_items = self.tree.get_children()
            if current_items:
                items_data = []
                for item_id in current_items:
                    values = self.tree.item(item_id, 'values')
                    if values and len(values) >= 5:
                        name = values[1].split(' ', 1)[-1] if ' ' in values[1] else values[1]
                        items_data.append({
                            'name': name,
                            'size_str': values[2],
                            'source': values[3],
                            'path': values[4],
                        })
                self.table_state_cache[self.current_nav_path] = items_data

        previous_path = self.navigation_history.pop()
        self.current_nav_path = previous_path
        self.update_navigation_ui()
        self.add_log(f"◀ Возврат в: {previous_path}", "info")
        self.path_label.config(text=f"📁 {previous_path}")
        self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)

        self.root.after(100, lambda: self.scan_current_folder(previous_path))

    def update_navigation_ui(self):
        self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)

    def scan_current_folder(self, path):
        debug_print(f"Загрузка папки из кэша: {path}")

        if self.last_scan_root and path == self.last_scan_root and self.last_scan_root_subfolders:
            self.root.after(0, lambda: self._display_folder_items(
                self.last_scan_root_subfolders, "📊 Результаты сканирования"))
            return

        try:
            import sqlite3
            conn = sqlite3.connect(self.cache.cache_file, timeout=30)
            cursor = conn.cursor()
            key = self.cache.get_folder_key(path)
            cursor.execute('''
                           SELECT COUNT(*)
                           FROM cache
                           WHERE path LIKE ?
                              OR path_normalized LIKE ?
                           ''', (path + '%', key + '%'))
            count = cursor.fetchone()[0]
            conn.close()

            if count > 0:
                self._load_folder_async(path)
                return
        except Exception as e:
            debug_print(f"Ошибка проверки SQLite: {e}")

        if path in self.table_state_cache:
            items_data = self.table_state_cache[path]
            self.root.after(0, lambda: self._restore_table_state(items_data, path))
            return

        self._load_folder_async(path)

    def _restore_table_state(self, items_data, path):
        if not items_data:
            self.tree.delete(*self.tree.get_children())
            self.results = []
            self.scan_status.config(text="📂 Папка пуста")
            self.set_status("Папка пуста", "info")
            return
        self._update_table_data(items_data, path)

    def _update_table_data(self, items_data, path):
        if not items_data:
            self.tree.delete(*self.tree.get_children())
            self.results = []
            self.scan_status.config(text="📂 Папка пуста")
            self.set_status("Папка пуста", "info")
            return

        current_items = self.tree.get_children()
        current_count = len(current_items)
        target_count = len(items_data)

        if target_count < current_count:
            to_delete = current_items[target_count:]
            if to_delete:
                self.tree.delete(*to_delete)
            current_items = self.tree.get_children()
            current_count = len(current_items)

        for i, (item_id, item_data) in enumerate(
                zip(current_items, items_data[:current_count]), 1):
            self._update_row(item_id, i, item_data)

        if target_count > current_count:
            self._add_rows_batched(items_data, current_count, target_count, path)

        self.results = items_data
        self._update_restore_status(len(items_data))

    def _update_row(self, item_id, index, item_data):
        if isinstance(item_data, dict):
            name = item_data.get('name', '')
            size_str = item_data.get('size_str', '0 Б')
            source = item_data.get('source', '📁')
            item_path = item_data.get('path', '')
            size = item_data.get('size', 0)
            if size > 1024 ** 4:
                emoji = "🔴"
            elif size > 1024 ** 3:
                emoji = "🟡"
            elif size > 1024 ** 2:
                emoji = "🟢"
            else:
                emoji = "⚪"
        else:
            return
        self.tree.item(item_id, values=(index, f"{emoji} {name}", size_str,
                                        source, item_path))

    def _add_rows_batched(self, items_data, start_index, target_count, path):
        batch_size = 100
        current_index = start_index

        def add_batch():
            nonlocal current_index
            end = min(current_index + batch_size, target_count)
            batch = items_data[current_index:end]
            for i, item_data in enumerate(batch, current_index + 1):
                item_id = self.tree.insert("", END, values=("", "", "", "", ""))
                self._update_row(item_id, i, item_data)
            current_index = end
            if current_index < target_count:
                self.root.after(5, add_batch)
            else:
                self._update_restore_status(target_count)

        if current_index < target_count:
            self.root.after(10, add_batch)
        else:
            self._update_restore_status(target_count)

    def _load_folder_async(self, path):
        debug_print(f"📂 Асинхронная загрузка папки с файлами: {path}")

        def load_folder():
            try:
                if path in self.scanned_folders_cache:
                    items = self.scanned_folders_cache[path]
                    items.sort(key=lambda x: x['size'], reverse=True)
                    self.root.after(0, lambda: self._display_folder_items(items))
                    return

                items = []
                file_items = []

                try:
                    entries_list = []
                    with os.scandir(path) as entries:
                        entries_list = list(entries)

                    import sqlite3
                    conn = sqlite3.connect(self.cache.cache_file, timeout=30)
                    cursor = conn.cursor()

                    for i, entry in enumerate(entries_list):
                        if i % 100 == 0:
                            self.root.update_idletasks()

                        entry_name = entry.name
                        if entry.is_dir() and entry_name in self.system_folders:
                            continue

                        if entry.is_file():
                            try:
                                stat_info = entry.stat(follow_symlinks=False)
                                size = stat_info.st_size
                                file_items.append({
                                    'name': entry_name,
                                    'size': size,
                                    'size_str': format_size(size),
                                    'path': entry.path,
                                    'source': '📄 Файл',
                                    'is_file': True,
                                    'is_dir': False,
                                })
                            except (PermissionError, OSError):
                                continue
                        else:
                            key = self.cache.get_folder_key(entry.path)
                            cursor.execute('SELECT total_size FROM cache '
                                           'WHERE path_normalized = ?', (key,))
                            row = cursor.fetchone()
                            if row:
                                size = row[0]
                                items.append({
                                    'name': entry_name, 'size': size,
                                    'size_str': format_size(size),
                                    'path': entry.path,
                                    'source': '💾 Кэш',
                                    'is_file': False, 'is_dir': True,
                                })
                            else:
                                items.append({
                                    'name': entry_name, 'size': 0,
                                    'size_str': '0 Б', 'path': entry.path,
                                    'source': '❓ Нет данных',
                                    'is_file': False, 'is_dir': True,
                                })

                    conn.close()

                    dirs = [x for x in items]
                    files = [x for x in file_items]
                    dirs.sort(key=lambda x: x['size'], reverse=True)
                    files.sort(key=lambda x: x['size'], reverse=True)
                    all_items = dirs + files

                    self.scanned_folders_cache[path] = all_items
                    self.root.after(0, lambda: self._display_folder_items(all_items))

                except PermissionError:
                    self.root.after(0, lambda: self.add_log(
                        f"⚠️ Нет доступа к папке: {path}", "warning"))
                    return
                except Exception as e:
                    self.root.after(0, lambda: self.add_log(
                        f"⚠️ Ошибка загрузки: {e}", "warning"))
                    return

            except Exception as e:
                debug_print(f"Ошибка загрузки папки: {e}")
                self.root.after(0, lambda: self.add_log(f"❌ Ошибка: {e}", "error"))

        thread = threading.Thread(target=load_folder)
        thread.daemon = True
        thread.start()

    def _start_scan_current_folder(self, path):
        if hasattr(self, '_scan_thread') and self._scan_thread and self._scan_thread.is_alive():
            self._scanning_folder = False
            self._scan_thread.join(timeout=0.5)
        self._scanning_folder = True
        self._scan_thread = threading.Thread(target=self.scan_current_folder, args=(path,))
        self._scan_thread.daemon = True
        self._scan_thread.start()

    def refresh_current_folder(self):
        if self.current_nav_path:
            if self.current_nav_path in self.scanned_folders_cache:
                del self.scanned_folders_cache[self.current_nav_path]
            self.scan_status.config(text="⏳ Обновление...")
            self.progress_var.set(0)
            self.progress_percent.config(text="0%")
            self.root.after(100, lambda: self._start_scan_current_folder(self.current_nav_path))
            self.add_log("🔄 Принудительное обновление папки...", "info")
        else:
            self.add_log("⚠️ Нет активной папки", "warning")

    def scan_all_from_current(self):
        if not self.current_nav_path:
            self.add_log("⚠️ Сначала перейдите в папку", "warning")
            return
        self.root_path.set(self.current_nav_path)
        self.settings.set('last_path', self.current_nav_path)
        self.start_scan()