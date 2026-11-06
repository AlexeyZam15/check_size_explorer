"""Состояние, переменные, горячие клавиши, copy-операции."""
import os
import re
import queue

from tkinter import *
from tkinter import ttk

from ..utils import debug_print


class StateMixin:
    """Инициализация переменных, hotkeys, copy."""

    def init_variables(self):
        debug_print("Инициализация переменных")
        self.scanning = False
        self.root_path = StringVar(value=self.settings.get('last_path', ''))
        self.results = []
        self.total_size = 0
        self.log_queue = queue.Queue()
        self.log_counter = 0
        self.current_filter = "Все"
        self.use_cache = BooleanVar(value=self.settings.get('use_cache', True))
        self.cache_hits = 0
        self.cache_misses = 0

        self.last_scan_root = ""
        self.last_scan_results = []
        self.last_scan_root_subfolders = []
        self.last_scan_total_size = 0

        self._root_data_loaded = False
        self._root_item_ids = []
        self._root_display_data = []

        self.table_state_cache = {}

        self.scan_stage = "idle"
        self.current_folder = ""
        self.current_file = ""
        self.files_processed = 0
        self.total_files_in_folder = 0
        self.folder_progress = 0
        self.folders_found = 0
        self.folders_processed = 0

        self.executor = None
        self.future_results = []
        self.scan_start_time = 0
        self.last_ui_update = 0
        self.ui_update_interval = 0.1
        self.error_count = 0

        self.batch_size = self.settings.get('batch_size', 50)
        self.max_workers = min(self.settings.get('max_workers', 4), os.cpu_count() or 1)
        self.system_folders = {
            'Documents and Settings', 'System Volume Information',
            '$Recycle.Bin', 'Config.Msi', 'Windows', 'ProgramData',
            'System32', 'SysWOW64', 'Recovery', 'Boot', 'PerfLogs'
        }
        self.exclude_patterns = [
            r'^\.', r'^System Volume Information$',
            r'^\$Recycle\.Bin$', r'^Config\.Msi$'
        ]
        self.compiled_patterns = [re.compile(p) for p in self.exclude_patterns]
        self.update_threshold = 5
        self.last_update_time = 0
        self.min_update_interval = 0.3

        self.navigation_history = []
        self.current_nav_path = ""
        self.scanned_folders_cache = {}

        self._scan_thread = None
        self._scanning_folder = False

        # Мультивыбор дисков + топ папок
        self.selected_drives = {}
        self.drives_frame = None
        self.selected_custom_path = BooleanVar(value=False)
        # Мин. глубина восстанавливается из настроек
        try:
            saved_md = int(self.settings.get('top_folders_min_depth', 3))
            if saved_md < 1:
                saved_md = 3
        except Exception:
            saved_md = 3
        self.top_folders_min_depth = saved_md
        self.top_folders = []
        saved_roots = self.settings.get('last_scan_roots', []) or []
        if isinstance(saved_roots, list):
            self.last_scan_roots = [r for r in saved_roots if isinstance(r, str)]
        else:
            self.last_scan_roots = []
        self._last_folder_sizes = {}
        self._last_folder_counts = {}
        self._last_root_of = {}

        debug_print("Переменные инициализированы")

    def bind_hotkeys(self):
        self.log_text.bind('<Control-c>', self.copy_selected_text)
        self.log_text.bind('<Control-C>', self.copy_selected_text)
        self.log_text.bind('<Control-a>', self.select_all_text)
        self.log_text.bind('<Control-A>', self.select_all_text)
        self.tree.bind('<Control-c>', self.copy_path_from_tree)
        self.tree.bind('<Control-C>', self.copy_path_from_tree)
        self.tree.bind('<Control-a>', self.select_all_rows)
        self.tree.bind('<Control-A>', self.select_all_rows)
        self.root.bind('<Control-c>', self.global_copy)
        self.root.bind('<Control-C>', self.global_copy)
        self.root.focus_set()

    def copy_selected_text(self, event=None):
        try:
            if self.log_text.tag_ranges("sel"):
                selected = self.log_text.get("sel.first", "sel.last")
                if selected:
                    self.root.clipboard_clear()
                    self.root.clipboard_append(selected)
                    self.root.update()
                    self.add_log(f"📋 Скопировано {len(selected)} символов из логов", "info")
                    return "break"
        except TclError:
            pass
        return None

    def select_all_text(self, event=None):
        self.log_text.tag_add(SEL, "1.0", END)
        self.log_text.mark_set(INSERT, "1.0")
        self.log_text.see(INSERT)
        return "break"

    def copy_path_from_tree(self, event=None):
        selection = self.tree.selection()
        if selection:
            paths = []
            for item in selection:
                values = self.tree.item(item, 'values')
                if values and len(values) > 4:
                    paths.append(values[4])

            if paths:
                text_to_copy = '\n'.join(paths)
                self.root.clipboard_clear()
                self.root.clipboard_append(text_to_copy)

                if len(paths) == 1:
                    self.add_log(f"📋 Скопирован путь: {paths[0]}", "success")
                else:
                    self.add_log(f"📋 Скопировано {len(paths)} путей", "success")
                self.set_status(f"Скопировано {len(paths)} путей", "success")
        return "break"

    def select_all_rows(self, event=None):
        self.tree.selection_set(self.tree.get_children())
        self.add_log("📋 Выделены все строки в таблице", "info")
        return "break"

    def global_copy(self, event=None):
        focused = self.root.focus_get()
        if focused == self.log_text:
            return self.copy_selected_text(event)
        if focused == self.tree:
            return self.copy_path_from_tree(event)
        if isinstance(focused, (Entry, ttk.Entry)):
            return None
        return self.copy_selected_text(event)