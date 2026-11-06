"""
Тонкий фасад: собирает ProfessionalDiskAnalyzer из миксинов.

Модули:
    gui_parts/styles.py      — цвета и ttk-стили
    gui_parts/state.py       — init_variables, hotkeys, copy
    gui_parts/layout.py      — create_layout, header, control, progress, nav, tabs, status
    gui_parts/results_tab.py — таблица результатов + навигация
    gui_parts/logs_tab.py    — вкладка логов
    gui_parts/cache_tab.py   — вкладка кэша
    gui_parts/scan.py        — сканирование корней
    gui_parts/drives_top.py  — чекбоксы дисков, топ папок/файлов
    gui_parts/details.py     — детали, контекст-меню, on_closing
"""
import os
import sys

from .cache_manager import SmartCacheManager
from .settings_manager import SettingsManager
from .utils import debug_print, format_size, get_app_data_path

from .gui_parts import (
    StylesMixin, StateMixin, LayoutMixin, ResultsTabMixin,
    LogsTabMixin, CacheTabMixin, ScanMixin, DrivesTopMixin, DetailsMixin,
)


class ProfessionalDiskAnalyzer(
    StylesMixin,
    StateMixin,
    LayoutMixin,
    ResultsTabMixin,
    LogsTabMixin,
    CacheTabMixin,
    ScanMixin,
    DrivesTopMixin,
    DetailsMixin,
):
    """Disk Analyzer Pro v5.2 — собирается из миксинов в gui_parts/."""

    def __init__(self, root):
        debug_print("Инициализация ProfessionalDiskAnalyzer")
        self.root = root
        self.root.title("Disk Analyzer Pro - Умный кэш v2")

        self.settings = SettingsManager()

        geometry = self.settings.get('window_geometry', '1200x850')
        self.root.geometry(geometry)

        state = self.settings.get('window_state', 'normal')
        if state == 'zoomed':
            self.root.state('zoomed')

        self.root.minsize(1000, 750)

        self.cache = SmartCacheManager()

        self._init_colors()
        self.setup_styles()
        self.init_variables()
        self.create_layout()

        stats = self.cache.get_cache_stats()
        self.add_log("🚀 Программа запущена (частичное обновление кэша)",
                     "highlight")
        self.add_log(
            f"💾 Кэш: {stats['total_entries']} записей, "
            f"{stats['cache_size_mb']:.1f} МБ", "info")
        self.add_log(
            f"📁 Файлы данных хранятся в: {get_app_data_path('DiskAnalyzer')}",
            "info")
        self.add_log(f"💻 Система: {sys.platform}", "info")

        if stats['total_entries'] == 0:
            cache_file_exists = os.path.exists(self.cache.cache_file)
            cache_file_size = (os.path.getsize(self.cache.cache_file)
                               if cache_file_exists else 0)
            if cache_file_exists and cache_file_size > 0:
                self.add_log(
                    "⚠️ Кэш повреждён или пуст, требуется пересканирование",
                    "warning")
            else:
                self.add_log(
                    "💡 Кэш пуст. Нажмите 'Сканировать все' для создания кэша",
                    "info")

        last_path = self.settings.get('last_path', '')
        if last_path and os.path.exists(last_path):
            self.root_path.set(last_path)
            self.add_log(f"📁 Загружена последняя папка: {last_path}", "info")
        else:
            self.load_default_drive()

        self.bind_hotkeys()

        if self.root_path.get() and os.path.exists(self.root_path.get()):
            self.root.after(100, lambda: self.navigate_to_path(
                self.root_path.get()))

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        debug_print("Инициализация завершена")