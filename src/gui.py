import os
import sys
import threading
import queue
import time
import json
import traceback
import re
from pathlib import Path
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText
from concurrent.futures import ThreadPoolExecutor, as_completed
import gc

from .cache_manager import SmartCacheManager
from .settings_manager import SettingsManager
from .utils import debug_print, format_size


class ProfessionalDiskAnalyzer:
    def __init__(self, root):
        debug_print("Инициализация ProfessionalDiskAnalyzer")
        self.root = root
        self.root.title("Disk Analyzer Pro - Умный кэш v2")

        # Загружаем настройки
        self.settings = SettingsManager("settings.json")

        # Применяем сохраненную геометрию окна
        geometry = self.settings.get('window_geometry', '1200x850')
        self.root.geometry(geometry)

        # Восстанавливаем состояние окна
        state = self.settings.get('window_state', 'normal')
        if state == 'zoomed':
            self.root.state('zoomed')

        self.root.minsize(1000, 750)

        # Используем умный кэш с SQLite (.db)
        self.cache = SmartCacheManager("folder_cache.db")

        # Цветовая схема
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
            'stage_prepare': '#ff9800'
        }

        self.setup_styles()
        self.init_variables()
        self.create_layout()

        # Статистика
        stats = self.cache.get_cache_stats()
        self.add_log("🚀 Программа запущена (частичное обновление кэша)", "highlight")
        self.add_log(f"💾 Кэш: {stats['total_entries']} записей, {stats['cache_size_mb']:.1f} МБ", "info")
        self.add_log(f"💻 Система: {sys.platform}", "info")

        # Проверяем, пустой ли кэш
        if stats['total_entries'] == 0:
            cache_file_exists = os.path.exists("folder_cache.db")
            cache_file_size = os.path.getsize("folder_cache.db") if cache_file_exists else 0

            if cache_file_exists and cache_file_size > 0:
                self.add_log("⚠️ Кэш повреждён или пуст, требуется пересканирование", "warning")
                self.add_log("💡 Нажмите 'Сканировать все' или 'Начать сканирование' для создания кэша", "info")
            else:
                self.add_log("💡 Кэш пуст. Нажмите 'Сканировать все' для создания кэша", "info")

        # Загружаем последнюю папку из настроек
        last_path = self.settings.get('last_path', '')
        if last_path and os.path.exists(last_path):
            self.root_path.set(last_path)
            self.add_log(f"📁 Загружена последняя папка: {last_path}", "info")
        else:
            # Если нет сохраненной папки - загружаем диск по умолчанию
            self.load_default_drive()

        # Привязка горячих клавиш
        self.bind_hotkeys()

        # Автоматический переход в последнюю папку
        if self.root_path.get() and os.path.exists(self.root_path.get()):
            self.root.after(100, lambda: self.navigate_to_path(self.root_path.get()))

        # Привязываем закрытие
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        debug_print("Инициализация завершена")

    def _insert_items_batched(self, items, source_label, total_items):
        """Пакетная вставка для большого количества элементов"""
        batch_size = 200
        current_index = 0

        self.scan_status.config(text=f"⏳ Загрузка: 0/{total_items}")
        self.stage_label.config(text=f"📊 {source_label}: загрузка...", foreground=self.colors['stage_scan'])
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
                size = item['size']
                if size > 1024 ** 4:
                    emoji = "🔴"
                elif size > 1024 ** 3:
                    emoji = "🟡"
                elif size > 1024 ** 2:
                    emoji = "🟢"
                else:
                    emoji = "⚪"

                source = item.get('source', '📊')
                self.tree.insert("", END, values=(
                    i,
                    f"{emoji} {item['name']}",
                    item['size_str'],
                    source,
                    item['path']
                ))

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
                    text=f"✅ {source_label}: {total_items} папок" if source_label else f"✅ {total_items} папок")
                self.set_status(f"{total_items} папок", "success")
                self.progress_var.set(100)
                self.progress_percent.config(text="100%")
                self.folder_progress_var.set(100)
                self.folder_progress_percent.config(text="100%")
                self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
                self.scanned_folders_cache[self.current_nav_path] = items
                self.table_state_cache[self.current_nav_path] = items
                debug_print(f"✅ Добавлено {total_items} строк (пакетно)")

        self.root.after(10, insert_batch)

    def _add_rows_batched(self, items_data, start_index, target_count, path):
        """Пакетное добавление строк (для больших объёмов)"""
        batch_size = 100
        current_index = start_index

        # Обновляем статус
        self.scan_status.config(text=f"⏳ Загрузка: {current_index}/{target_count}")
        self.stage_label.config(text="📊 Добавление строк...", foreground=self.colors['stage_scan'])
        self.progress_var.set(int((current_index / target_count) * 100) if target_count > 0 else 0)

        def add_batch():
            nonlocal current_index

            end = min(current_index + batch_size, target_count)
            batch = items_data[current_index:end]

            # Добавляем пакет строк
            for i, item_data in enumerate(batch, current_index + 1):
                # Создаём пустую строку
                item_id = self.tree.insert("", END, values=("", "", "", "", ""))
                # Заполняем её данными
                self._update_row(item_id, i, item_data)

            current_index = end

            # Обновляем прогресс
            if target_count > 0:
                progress = int((current_index / target_count) * 100)
                self.progress_var.set(progress)
                self.progress_percent.config(text=f"{progress}%")
                self.folder_progress_var.set(progress)
                self.folder_progress_percent.config(text=f"{progress}%")
                self.scan_status.config(text=f"⏳ Загрузка: {current_index}/{target_count} ({progress}%)")

            # Если есть ещё — продолжаем
            if current_index < target_count:
                self.root.after(5, add_batch)
            else:
                # Завершено
                self.progress_var.set(100)
                self.progress_percent.config(text="100%")
                self.folder_progress_var.set(100)
                self.folder_progress_percent.config(text="100%")
                self.scan_status.config(text=f"✅ {len(items_data)} папок")
                self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
                debug_print(f"✅ Добавлено {target_count - start_index} строк")

        # Запускаем пакетное добавление
        if current_index < target_count:
            self.root.after(10, add_batch)
        else:
            # Если ничего не добавляем
            self.progress_var.set(100)
            self.progress_percent.config(text="100%")
            self.folder_progress_var.set(100)
            self.folder_progress_percent.config(text="100%")

    def _update_row(self, item_id, index, item_data):
        """Обновление одной строки таблицы"""
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
            if len(item_data) >= 5:
                name = item_data[1].split(' ', 1)[-1] if ' ' in item_data[1] else item_data[1]
                size_str = item_data[2]
                source = item_data[3]
                item_path = item_data[4]
                emoji = item_data[1].split(' ')[0] if item_data[1].startswith(('🔴', '🟡', '🟢', '⚪')) else "⚪"
            else:
                return

        self.tree.item(item_id, values=(
            index,
            f"{emoji} {name}",
            size_str,
            source,
            item_path
        ))

    def _update_table_data(self, items_data, path):
        """
        ОБНОВЛЕНИЕ данных таблицы БЕЗ ОЧИСТКИ
        С пакетной вставкой для больших объёмов
        """
        if not items_data:
            self.tree.delete(*self.tree.get_children())
            self.results = []
            self.scan_status.config(text="📂 Папка пуста")
            self.set_status("Папка пуста", "info")
            return

        current_items = self.tree.get_children()
        current_count = len(current_items)
        target_count = len(items_data)

        # ========== НОВАЯ ПРОВЕРКА: если данные уже совпадают ==========
        if current_count == target_count and current_count > 0:
            # Проверяем, что первые элементы совпадают (быстрая проверка)
            first_item = self.tree.item(current_items[0], 'values')
            if first_item and len(first_item) >= 5:
                first_path = first_item[4]
                if items_data and items_data[0].get('path', '') == first_path:
                    debug_print(f"✅ Данные уже загружены, пропускаем обновление для {path}")
                    # Просто обновляем статус
                    self.scan_status.config(text=f"✅ {len(items_data)} папок")
                    self.set_status(f"{len(items_data)} папок", "success")
                    self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
                    if self.progress_var.get() < 100:
                        self.progress_var.set(100)
                        self.progress_percent.config(text="100%")
                        self.folder_progress_var.set(100)
                        self.folder_progress_percent.config(text="100%")
                    return

        debug_print(f"🔄 Обновление таблицы: {current_count} -> {target_count} элементов для {path}")

        # 1. Если нужно удалить лишние строки
        if target_count < current_count:
            to_delete = current_items[target_count:]
            if to_delete:
                self.tree.delete(*to_delete)
            current_items = self.tree.get_children()
            current_count = len(current_items)

        # 2. Обновляем существующие строки
        for i, (item_id, item_data) in enumerate(zip(current_items, items_data[:current_count]), 1):
            self._update_row(item_id, i, item_data)

        # 3. Если нужно добавить строки — делаем это ПАКЕТАМИ
        if target_count > current_count:
            self._add_rows_batched(items_data, current_count, target_count, path)

        self.results = items_data
        self._update_restore_status(len(items_data))
        debug_print(f"✅ Таблица обновлена: {len(items_data)} элементов")

    def _insert_items_immediate(self, items_data):
        """Быстрая вставка для малого количества элементов"""
        # Отключаем обновление UI на время вставки
        self.tree.configure(selectmode='none')

        for i, item in enumerate(items_data, 1):
            if isinstance(item, dict):
                name = item.get('name', '')
                size_str = item.get('size_str', '0 Б')
                source = item.get('source', '📁')
                item_path = item.get('path', '')
                size = item.get('size', 0)

                if size > 1024 ** 4:
                    emoji = "🔴"
                elif size > 1024 ** 3:
                    emoji = "🟡"
                elif size > 1024 ** 2:
                    emoji = "🟢"
                else:
                    emoji = "⚪"
            else:
                if len(item) >= 5:
                    name = item[1].split(' ', 1)[-1] if ' ' in item[1] else item[1]
                    size_str = item[2]
                    source = item[3]
                    item_path = item[4]
                    emoji = item[1].split(' ')[0] if item[1].startswith(('🔴', '🟡', '🟢', '⚪')) else "⚪"
                else:
                    continue

            self.tree.insert("", END, values=(
                i,
                f"{emoji} {name}",
                size_str,
                source,
                item_path
            ))

        # Включаем обновление UI
        self.tree.configure(selectmode='extended')
        self.root.update_idletasks()

        self.results = items_data
        self._update_restore_status(len(items_data))

    def _clear_table_gradually(self):
        """Постепенная очистка таблицы (без зависания)"""
        children = self.tree.get_children()
        total = len(children)

        if total == 0:
            return

        # Если элементов мало — удаляем сразу
        if total <= 100:
            self.tree.delete(*children)
            return

        # Если много — удаляем пакетами
        debug_print(f"🗑️ Постепенная очистка {total} элементов...")
        batch_size = 50

        def clear_batch():
            nonlocal children, total
            if not children:
                return

            # Берём пакет для удаления
            batch = children[:batch_size]
            children = children[batch_size:]

            try:
                self.tree.delete(*batch)
            except Exception as e:
                debug_print(f"Ошибка при очистке: {e}")
                return

            # Если остались элементы — продолжаем
            if children:
                self.root.after(5, clear_batch)
            else:
                debug_print(f"✅ Очистка завершена")

        # Запускаем пакетную очистку
        self.root.after(1, clear_batch)

    def _update_restore_status(self, count):
        """Обновление статуса после восстановления таблицы"""
        self.scan_status.config(text=f"✅ {count} папок")
        self.set_status(f"{count} папок", "success")
        self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])

        if self.progress_var.get() < 100:
            self.progress_var.set(100)
            self.progress_percent.config(text="100%")
            self.folder_progress_var.set(100)
            self.folder_progress_percent.config(text="100%")

        debug_print(f"✅ Статус обновлён: {count} папок")

    def _display_scan_results_instant(self, items, source_label):
        """
        МГНОВЕННОЕ отображение результатов сканирования (с пакетной вставкой)
        БЕЗ ПОДВИСАНИЙ — использует тот же механизм, что и обычная загрузка
        """
        if not items:
            self.tree.delete(*self.tree.get_children())
            self.scan_status.config(text="📂 Нет данных")
            self.set_status("Нет данных", "info")
            return

        # Используем тот же механизм, что и для обычных папок — пакетная вставка
        self._display_folder_items(items, source_label)

    def _restore_table_state(self, items_data, path):
        """Восстановление состояния таблицы для ПОДПАПОК (без очистки)"""
        if not items_data:
            self.tree.delete(*self.tree.get_children())
            self.results = []
            self.scan_status.config(text="📂 Папка пуста")
            self.set_status("Папка пуста", "info")
            return

        # ОБНОВЛЯЕМ данные без очистки
        self._update_table_data(items_data, path)

    def _load_folder_async(self, path):
        """Асинхронная загрузка папки (когда данных нет в таблице)"""
        debug_print(f"📂 Асинхронная загрузка папки: {path}")

        def load_folder():
            try:
                # ПРОВЕРЯЕМ ЛОКАЛЬНЫЙ КЭШ НАВИГАЦИИ
                if path in self.scanned_folders_cache:
                    items = self.scanned_folders_cache[path]
                    debug_print(f"✅ Загружено из локального кэша: {len(items)} элементов")
                    self.root.after(0, lambda: self.add_log(f"💾 Загружено из кэша: {len(items)} папок", "cache"))
                    items.sort(key=lambda x: x['size'], reverse=True)
                    self.root.after(0, lambda: self._display_folder_items(items))
                    return

                # ПОЛУЧАЕМ ДАННЫЕ ИЗ ОСНОВНОГО КЭША (SQLite)
                debug_print(f"📂 Чтение данных из основного кэша: {path}")
                items = []

                try:
                    entries_list = []
                    with os.scandir(path) as entries:
                        entries_list = [entry for entry in entries if entry.is_dir()]

                    total_entries = len(entries_list)

                    if total_entries > 100:
                        self.root.after(0, lambda: self.scan_status.config(
                            text=f"⏳ Чтение из кэша: {total_entries} элементов..."
                        ))

                    import sqlite3
                    conn = sqlite3.connect(self.cache.cache_file, timeout=30)
                    cursor = conn.cursor()

                    for i, entry in enumerate(entries_list):
                        if i % 100 == 0:
                            self.root.update_idletasks()

                        folder_name = entry.name
                        if folder_name in self.system_folders:
                            continue

                        key = self.cache.get_folder_key(entry.path)
                        cursor.execute('''
                                       SELECT total_size
                                       FROM cache
                                       WHERE path = ?
                                          OR path_normalized = ?
                                       ''', (entry.path, key))

                        row = cursor.fetchone()

                        if row:
                            size = row[0]
                            size_str = format_size(size)
                            items.append({
                                'name': folder_name,
                                'size': size,
                                'size_str': size_str,
                                'path': entry.path,
                                'source': '💾 Кэш'
                            })
                        else:
                            items.append({
                                'name': folder_name,
                                'size': 0,
                                'size_str': '0 Б',
                                'path': entry.path,
                                'source': '❓ Нет данных'
                            })

                    conn.close()

                except PermissionError:
                    self.root.after(0, lambda: self.add_log(f"⚠️ Нет доступа к папке: {path}", "warning"))
                    self.root.after(0, lambda: self.scan_status.config(text="⚠️ Нет доступа"))
                    return
                except Exception as e:
                    debug_print(f"Ошибка чтения БД: {e}")
                    self.root.after(0, lambda: self.add_log(f"⚠️ Ошибка чтения кэша: {e}", "warning"))
                    return

                # Сохраняем в локальный кэш и отображаем
                if items:
                    self.scanned_folders_cache[path] = items
                    items.sort(key=lambda x: x['size'], reverse=True)
                    self.root.after(0, lambda: self._display_folder_items(items))
                else:
                    self.scanned_folders_cache[path] = []
                    self.root.after(0, lambda: self.add_log("📂 Папка пуста", "info"))
                    self.root.after(0, lambda: self.scan_status.config(text="📂 Папка пуста"))

            except Exception as e:
                debug_print(f"Ошибка загрузки папки: {str(e)}")
                self.root.after(0, lambda: self.add_log(f"❌ Ошибка: {str(e)}", "error"))
                self.root.after(0, lambda: self.scan_status.config(text="❌ Ошибка"))

        # Запускаем в потоке
        thread = threading.Thread(target=load_folder)
        thread.daemon = True
        thread.start()

    def _update_status_only(self, source_label, count):
        """Только обновляет статус, НЕ ТРОГАЕТ таблицу"""
        self.scan_status.config(text=f"✅ {source_label}: {count} папок")
        self.set_status(f"{source_label}: {count} папок", "success")
        self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
        self.path_label.config(text=f"📁 {self.current_nav_path}")

        debug_print(f"✅ Статус обновлён: {source_label}: {count} папок")

    def _display_first_items(self, items, count):
        """Быстрое отображение первых N элементов"""
        for i, item in enumerate(items[:count], 1):
            size = item['size']
            if size > 1024 ** 4:
                emoji = "🔴"
            elif size > 1024 ** 3:
                emoji = "🟡"
            elif size > 1024 ** 2:
                emoji = "🟢"
            else:
                emoji = "⚪"

            source = item.get('source', '📊')

            self.tree.insert("", END, values=(
                i,
                f"{emoji} {item['name']}",
                item['size_str'],
                source,
                item['path']
            ))

        self.root.update_idletasks()  # Принудительное обновление UI

    def _display_folder_items_batched(self, items, source_label=""):
        """
        Пакетное отображение элементов в таблице (для большого количества папок)
        """
        # ПРОВЕРКА: если данные уже загружены — не пересоздаём
        existing_items = self.tree.get_children()
        if existing_items and len(existing_items) == len(items):
            first_item = self.tree.item(existing_items[0], 'values')
            if first_item and len(first_item) >= 5:
                first_path = first_item[4]
                if items and items[0]['path'] == first_path:
                    debug_print(f"✅ Данные уже загружены, пропускаем вставку")
                    self.results = items
                    self.scan_status.config(text=f"✅ {source_label}: {len(items)} папок")
                    self.set_status(f"{source_label}: {len(items)} папок", "success")
                    self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
                    return

        # Очищаем таблицу
        self.tree.delete(*self.tree.get_children())
        self.results = []

        if not items:
            self.scan_status.config(text="📂 Нет данных")
            self.set_status("Нет данных", "info")
            self.add_log("📂 Нет данных для отображения", "info")
            return

        total_items = len(items)

        # Сразу показываем первые элементы, чтобы пользователь видел прогресс
        self._display_first_items(items, min(50, total_items))

        # Остальные вставляем пакетами
        batch_size = 200
        current_index = min(50, total_items)

        # Общая статистика (только если не было в логах)
        total_size = sum(item['size'] for item in items)
        self.add_log(f"📦 Общий размер: {format_size(total_size)}", "info")
        debug_print(f"Общий размер: {format_size(total_size)}")

        # Топ-5 в логах (только если не было)
        top_items = items[:5]
        if top_items:
            self.add_log("🏆 Топ-5 самых больших папок:", "highlight")
            for j, item in enumerate(top_items, 1):
                self.add_log(f"  {j}. {item['name']} - {item['size_str']}", "info")

        # Обновляем статус
        self.scan_status.config(text=f"⏳ Загрузка: {current_index}/{total_items}")
        self.stage_label.config(text=f"📊 {source_label}: загрузка...", foreground=self.colors['stage_scan'])

        # Устанавливаем начальный прогресс
        if current_index > 0:
            initial_progress = int((current_index / total_items) * 100)
            self.progress_var.set(initial_progress)
            self.progress_percent.config(text=f"{initial_progress}%")
            self.folder_progress_var.set(initial_progress)
            self.folder_progress_percent.config(text=f"{initial_progress}%")

        def insert_batch():
            nonlocal current_index
            start = current_index
            end = min(current_index + batch_size, total_items)
            batch = items[start:end]

            # Вставляем пакет
            for i, item in enumerate(batch, start + 1):
                size = item['size']
                if size > 1024 ** 4:
                    emoji = "🔴"
                elif size > 1024 ** 3:
                    emoji = "🟡"
                elif size > 1024 ** 2:
                    emoji = "🟢"
                else:
                    emoji = "⚪"

                source = item.get('source', '📊')

                self.tree.insert("", END, values=(
                    i,
                    f"{emoji} {item['name']}",
                    item['size_str'],
                    source,
                    item['path']
                ))

            current_index = end

            # Обновляем прогресс
            if total_items > 0:
                progress = int((current_index / total_items) * 100)
                self.progress_var.set(progress)
                self.progress_percent.config(text=f"{progress}%")
                self.folder_progress_var.set(progress)
                self.folder_progress_percent.config(text=f"{progress}%")
                self.scan_status.config(text=f"⏳ Загрузка: {current_index}/{total_items} ({progress}%)")

            # Если есть ещё элементы - планируем следующий пакет
            if current_index < total_items:
                self.root.after(5, insert_batch)
            else:
                # Завершено
                self.results = items
                self.scan_status.config(text=f"✅ {source_label}: {total_items} папок")
                self.set_status(f"{source_label}: {total_items} папок", "success")
                self.progress_var.set(100)
                self.progress_percent.config(text="100%")
                self.folder_progress_var.set(100)
                self.folder_progress_percent.config(text="100%")
                self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
                self.add_log(f"✅ Отображено {total_items} папок", "success")

                # Сохраняем в локальный кэш навигации
                self.scanned_folders_cache[self.current_nav_path] = items

        # Запускаем пакетную вставку
        if current_index < total_items:
            self.root.after(10, insert_batch)
        else:
            # Если все элементы уже показаны
            self.results = items
            self.scan_status.config(text=f"✅ {source_label}: {total_items} папок")
            self.set_status(f"{source_label}: {total_items} папок", "success")
            self.progress_var.set(100)
            self.progress_percent.config(text="100%")
            self.folder_progress_var.set(100)
            self.folder_progress_percent.config(text="100%")
            self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])

    def _display_folder_items_with_source(self, items, source_label):
        """Отображение элементов с указанием источника (результаты сканирования)"""
        # Очищаем таблицу
        self.tree.delete(*self.tree.get_children())
        self.results = []

        # Проверяем, есть ли элементы
        if not items:
            self.scan_status.config(text="📂 Нет данных")
            self.set_status("Нет данных", "info")
            self.add_log("📂 Нет данных для отображения", "info")
            return

        # Отображаем элементы
        for i, item in enumerate(items, 1):
            size = item['size']
            if size > 1024 ** 4:  # > 1 ТБ
                emoji = "🔴"
            elif size > 1024 ** 3:  # > 1 ГБ
                emoji = "🟡"
            elif size > 1024 ** 2:  # > 1 МБ
                emoji = "🟢"
            else:
                emoji = "⚪"

            source = item.get('source', '📊')

            self.tree.insert("", END, values=(
                i,
                f"{emoji} {item['name']}",
                item['size_str'],
                source,
                item['path']
            ))

        self.results = items
        self.scan_status.config(text=f"✅ {source_label}: {len(items)} папок")
        self.set_status(f"{source_label}: {len(items)} папок", "success")

        # Общая статистика
        if items:
            total_size = sum(item['size'] for item in items)
            self.add_log(f"📦 Общий размер: {format_size(total_size)}", "info")
            debug_print(f"Общий размер: {format_size(total_size)}")

            # Показываем топ-5 самых больших
            top_items = items[:5]
            if top_items:
                self.add_log("🏆 Топ-5 самых больших папок:", "highlight")
                for j, item in enumerate(top_items, 1):
                    self.add_log(f"  {j}. {item['name']} - {item['size_str']}", "info")

    def _update_scan_progress(self, total_progress, stage, stage_progress, message):
        """
        Обновление общего прогресса в интерфейсе
        total_progress: 0-100% общий прогресс
        stage: название текущего этапа
        stage_progress: прогресс этапа (0-100%)
        message: дополнительное сообщение
        """
        # Общий прогресс
        self.root.after(0, lambda p=total_progress: self.progress_var.set(p))
        self.root.after(0, lambda p=total_progress: self.progress_percent.config(text=f"{p:.0f}%"))

        # Прогресс подэтапа (детальный)
        self.root.after(0, lambda p=stage_progress: self.folder_progress_var.set(p))
        self.root.after(0, lambda p=stage_progress: self.folder_progress_percent.config(text=f"{p:.0f}%"))

        # Статус
        self.root.after(0, lambda s=stage, m=message: self.scan_status.config(
            text=f"{s}: {m}"
        ))

        # Этап
        self.root.after(0, lambda s=stage: self.stage_label.config(
            text=f"🔄 {s}",
            foreground=self.colors['stage_scan']
        ))

    def collect_all_folders_cached(self, path):
        """Сбор всех папок с использованием кэша"""
        # Проверяем кэш списка папок
        cached_folders = self.cache.get_cached_folder_list(path)

        if cached_folders is not None:
            debug_print(f"📂 Загружено {len(cached_folders)} папок из кэша списка")
            self.add_log(f"💾 Загружено {len(cached_folders)} папок из кэша", "cache")
            return cached_folders

        # Если нет в кэше - собираем заново
        debug_print(f"📂 Сбор папок (кэш отсутствует)...")
        self.add_log(f"📂 Сбор всех папок (первый раз, это может занять время)...", "info")

        all_folders = []
        system_folders = self.system_folders
        collected_count = 0

        try:
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [d for d in dirs if d not in system_folders]
                for d in dirs:
                    folder_path = os.path.join(root, d)
                    all_folders.append(folder_path)
                    collected_count += 1
                    # Обновляем UI каждые 500 папок
                    if collected_count % 500 == 0:
                        self.root.after(0, lambda c=collected_count: self.scan_status.config(
                            text=f"⏳ Сбор папок... (найдено: {c})"
                        ))
        except (PermissionError, OSError):
            pass

        # Сохраняем в кэш
        if all_folders:
            self.cache.save_folder_list(path, all_folders)
            debug_print(f"💾 Сохранено {len(all_folders)} папок в кэш списка")
            self.add_log(f"💾 Сохранено {len(all_folders)} папок в кэш", "cache")

        return all_folders

    def repair_cache(self):
        """Восстановление повреждённого кэша"""
        if messagebox.askyesno("Подтверждение",
                               "Восстановление кэша может занять некоторое время.\n"
                               "Продолжить?"):

            self.add_log("🔧 Начало восстановления кэша...", "info")
            self.scan_status.config(text="⏳ Восстановление кэша...")
            self.root.update()

            try:
                # Выполняем восстановление
                self.cache._repair_database()

                # Проверяем целостность
                valid_count, total_size = self.cache.validate_cache()

                self.cache.save_cache()
                self.refresh_cache_list()

                self.add_log(f"✅ Восстановление завершено: {valid_count} записей, {format_size(total_size)}", "success")
                self.scan_status.config(text=f"✅ Восстановлено {valid_count} записей")

                messagebox.showinfo("Успех",
                                    f"Восстановление кэша завершено!\n"
                                    f"Записей: {valid_count}\n"
                                    f"Размер: {format_size(total_size)}")
            except Exception as e:
                self.add_log(f"❌ Ошибка восстановления: {str(e)}", "error")
                messagebox.showerror("Ошибка", f"Не удалось восстановить кэш:\n{str(e)}")

    def create_cache_tab(self, parent):
        """Создание вкладки кэша"""
        info_frame = ttk.LabelFrame(parent,
                                    text="📊 Статистика кэша",
                                    style="Card.TLabelframe",
                                    padding=(20, 15)
                                    )
        info_frame.pack(fill=X, pady=(0, 15))

        stats = self.cache.get_cache_stats()

        stats_grid = ttk.Frame(info_frame, style="Modern.TFrame")
        stats_grid.pack(fill=X)

        stats_items = [
            ("📁 Всего записей:", f"{stats['total_entries']:,}"),
            ("💾 Размер кэша:", f"{stats['cache_size_mb']:.2f} МБ"),
            ("🎯 Попаданий в кэш:", f"{stats['hits']:,}"),
            ("❌ Промахов кэша:", f"{stats['misses']:,}"),
            ("📊 Точность кэша:", f"{stats['hit_rate']:.1f}%"),
            ("🔄 Частичных обновлений:", f"{stats['partial_updates']:,}"),
            ("📦 Полных обновлений:", f"{stats['full_updates']:,}")
        ]

        for i, (label, value) in enumerate(stats_items):
            row = ttk.Frame(stats_grid, style="Modern.TFrame")
            row.pack(fill=X, pady=3)

            ttk.Label(row,
                      text=label,
                      font=('Segoe UI', 10),
                      foreground=self.colors['text_secondary'],
                      width=20
                      ).pack(side=LEFT)

            ttk.Label(row,
                      text=value,
                      font=('Segoe UI', 10, 'bold'),
                      foreground=self.colors['text_primary']
                      ).pack(side=LEFT)

        control_frame = ttk.LabelFrame(parent,
                                       text="🔧 Управление кэшем",
                                       style="Card.TLabelframe",
                                       padding=(20, 15)
                                       )
        control_frame.pack(fill=X)

        btn_frame = ttk.Frame(control_frame, style="Modern.TFrame")
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame,
                   text="🗑️ Очистить кэш",
                   command=self.clear_cache,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(btn_frame,
                   text="💾 Сохранить кэш",
                   command=self.save_cache,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(btn_frame,
                   text="🔧 Восстановить кэш",
                   command=self.repair_cache,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(btn_frame,
                   text="📊 Обновить статистику",
                   command=self.refresh_cache_list,
                   style="Secondary.TButton"
                   ).pack(side=LEFT)

        # Список кэшированных папок
        list_frame = ttk.LabelFrame(parent,
                                    text="📋 Кэшированные папки (последние 100)",
                                    style="Card.TLabelframe",
                                    padding=(20, 15)
                                    )
        list_frame.pack(fill=BOTH, expand=True, pady=(15, 0))

        columns = ("#", "📁 Папка", "📦 Размер", "📄 Файлы", "🕐 Последнее обновление")
        self.cache_tree = ttk.Treeview(list_frame,
                                       columns=columns,
                                       show="headings",
                                       style="Table.Treeview",
                                       height=8
                                       )

        self.cache_tree.heading("#", text="#", anchor=CENTER)
        self.cache_tree.heading("📁 Папка", text="📁 Папка")
        self.cache_tree.heading("📦 Размер", text="📦 Размер", anchor=E)
        self.cache_tree.heading("📄 Файлы", text="📄 Файлы", anchor=E)
        self.cache_tree.heading("🕐 Последнее обновление", text="🕐 Последнее обновление")

        self.cache_tree.column("#", width=50, anchor=CENTER, minwidth=40)
        self.cache_tree.column("📁 Папка", width=350, minwidth=150)
        self.cache_tree.column("📦 Размер", width=130, anchor=E, minwidth=100)
        self.cache_tree.column("📄 Файлы", width=80, anchor=E, minwidth=70)
        self.cache_tree.column("🕐 Последнее обновление", width=180, anchor=CENTER, minwidth=150)

        v_scroll = ttk.Scrollbar(list_frame, orient=VERTICAL, command=self.cache_tree.yview,
                                 style="Modern.Vertical.TScrollbar")
        self.cache_tree.configure(yscrollcommand=v_scroll.set)

        self.cache_tree.pack(side=LEFT, fill=BOTH, expand=True)
        v_scroll.pack(side=RIGHT, fill=Y)

        self.refresh_cache_list()

    def open_current_folder_in_explorer(self):
        """Открыть текущую папку в проводнике Windows"""
        path = self.current_nav_path
        if not path:
            self.add_log("⚠️ Нет активной папки для открытия", "warning")
            return

        if not os.path.exists(path):
            self.add_log(f"⚠️ Папка не существует: {path}", "warning")
            return

        try:
            if os.name == 'nt':  # Windows
                os.startfile(path)
            else:  # Linux/Mac
                import subprocess
                subprocess.Popen(['xdg-open', path])
            self.add_log(f"📂 Открыта папка: {path}", "info")
        except Exception as e:
            self.add_log(f"❌ Ошибка открытия папки: {str(e)}", "error")

    def _collect_all_folders_only_with_progress(self, path, result_list, counter):
        """Сбор ВСЕХ папок рекурсивно с обновлением счетчика для UI"""
        try:
            if not os.access(path, os.R_OK):
                return

            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if not self.scanning:
                            return
                        if entry.is_dir():
                            folder_name = entry.name
                            # Проверяем, не системная ли папка
                            if folder_name in self.system_folders:
                                continue

                            # Проверяем по регулярным выражениям
                            skip = False
                            for pattern in self.compiled_patterns:
                                if pattern.search(folder_name):
                                    skip = True
                                    break
                            if skip:
                                continue

                            # Добавляем папку и увеличиваем счетчик
                            result_list.append(entry.path)
                            counter[0] += 1

                            # Обновляем UI каждые 50 папок
                            if counter[0] % 50 == 0:
                                self.root.after(0, lambda c=counter[0]: self.scan_status.config(
                                    text=f"⏳ Сбор папок... (найдено: {c})"
                                ))
                                # Показываем анимацию прогресса
                                progress = min(95, (counter[0] % 100) * 0.5)
                                self.root.after(0, lambda p=progress: self.folder_progress_var.set(p))
                                self.root.after(0, lambda p=progress: self.folder_progress_percent.config(
                                    text=f"{p:.0f}%"
                                ))

                            # Рекурсивно обходим подпапки
                            self._collect_all_folders_only_with_progress(entry.path, result_list, counter)

            except (PermissionError, OSError):
                pass

        except Exception:
            pass

    def _collect_all_folders_only(self, path, result_list):
        """Сбор ВСЕХ папок рекурсивно (стандартный метод, если быстрый не сработал)"""
        try:
            if not os.access(path, os.R_OK):
                return

            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if not self.scanning:
                            return
                        if entry.is_dir():
                            folder_name = entry.name
                            # Проверяем, не системная ли папка
                            if folder_name in self.system_folders:
                                continue

                            # Проверяем по регулярным выражениям
                            skip = False
                            for pattern in self.compiled_patterns:
                                if pattern.search(folder_name):
                                    skip = True
                                    break
                            if skip:
                                continue

                            # Добавляем папку
                            result_list.append(entry.path)

                            # Рекурсивно обходим подпапки
                            self._collect_all_folders_only(entry.path, result_list)

            except (PermissionError, OSError):
                pass

        except Exception:
            pass

    def on_closing(self):
        """Сохранение настроек при закрытии"""
        try:
            self.settings.update(
                use_cache=self.use_cache.get(),
                last_path=self.root_path.get(),
                batch_size=self.batch_size,
                max_workers=self.max_workers,
                window_geometry=self.root.geometry(),
                window_state='zoomed' if self.root.state() == 'zoomed' else 'normal'
            )
        except:
            pass

        # Сохраняем кэш
        self.cache.save_cache()
        debug_print("Настройки и кэш сохранены, программа закрывается")
        self.root.destroy()

    def setup_styles(self):
        """Настройка стилей"""
        style = ttk.Style()
        style.theme_use('clam')

        style.configure(".",
                        background=self.colors['bg_primary'],
                        foreground=self.colors['text_primary'],
                        font=('Segoe UI', 10)
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
                  background=[('active', self.colors['accent_hover']), ('disabled', '#2a3a5e')],
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

        # Стиль для Spinbox
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

        # Стиль для Checkbutton
        style.configure("Modern.TCheckbutton",
                        background=self.colors['bg_secondary'],
                        foreground=self.colors['text_primary'],
                        font=('Segoe UI', 10)
                        )
        style.map("Modern.TCheckbutton",
                  background=[('active', self.colors['bg_hover'])],
                  foreground=[('active', self.colors['text_primary'])]
                  )

        # Стиль для Combobox
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

        # Стиль для Notebook
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

        # Стиль для Scrollbar
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

        # Стиль для Separator
        style.configure("Modern.TSeparator",
                        background=self.colors['border'],
                        foreground=self.colors['border']
                        )

    def init_variables(self):
        """Инициализация переменных"""
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

        # Хранилище результатов последнего сканирования
        self.last_scan_root = ""
        self.last_scan_results = []  # Все папки рекурсивно (для деталей)
        self.last_scan_root_subfolders = []  # ТОЛЬКО прямые подпапки корня (для отображения)
        self.last_scan_total_size = 0

        # ========== ДАННЫЕ ДЛЯ БЫСТРОГО ВОССТАНОВЛЕНИЯ КОРНЯ ==========
        self._root_data_loaded = False  # Флаг: данные корня загружены
        self._root_item_ids = []  # ID строк таблицы для корня
        self._root_display_data = []  # Данные корня для отображения

        # Кэш состояний таблицы для каждой папки
        self.table_state_cache = {}

        # Статус сканирования
        self.scan_stage = "idle"
        self.current_folder = ""
        self.current_file = ""
        self.files_processed = 0
        self.total_files_in_folder = 0
        self.folder_progress = 0
        self.folders_found = 0
        self.folders_processed = 0

        # Для оптимизации
        self.executor = None
        self.future_results = []
        self.scan_start_time = 0
        self.last_ui_update = 0
        self.ui_update_interval = 0.1
        self.error_count = 0

        # Дополнительные оптимизации
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

        # Для навигации по папкам
        self.navigation_history = []
        self.current_nav_path = ""
        self.scanned_folders_cache = {}

        # Для управления потоками
        self._scan_thread = None
        self._scanning_folder = False

        debug_print("Переменные инициализированы")

    def bind_hotkeys(self):
        """Привязка горячих клавиш"""
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

    def create_layout(self):
        """Создание основного макета"""
        debug_print("Создание интерфейса")
        self.root.configure(bg=self.colors['bg_primary'])

        main_frame = ttk.Frame(self.root, style="Modern.TFrame")
        main_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)

        self.create_header(main_frame)
        self.create_control_panel(main_frame)
        self.create_progress_bars(main_frame)
        self.create_navigation_panel(main_frame)
        self.create_tabs(main_frame)
        self.create_status_bar(main_frame)

        # Подсказка о горячих клавишах
        self.add_log("💡 Горячие клавиши:", "info")
        self.add_log("   • Ctrl+C - копировать выделенный текст (в логах)", "info")
        self.add_log("   • Ctrl+C - копировать путь (в таблице результатов)", "info")
        self.add_log("   • Ctrl+A - выделить всё (в логах или таблице)", "info")
        self.add_log("   • Двойной клик по папке - переход в неё", "info")
        self.add_log(f"⚡ Оптимизация: {self.max_workers} потоков, батч {self.batch_size} папок", "info")

    def create_header(self, parent):
        """Создание заголовка"""
        header_frame = ttk.Frame(parent, style="Modern.TFrame")
        header_frame.pack(fill=X, pady=(0, 20))

        logo_frame = ttk.Frame(header_frame, style="Modern.TFrame")
        logo_frame.pack(side=LEFT)

        ttk.Label(logo_frame,
                  text="📂",
                  font=('Segoe UI', 28)
                  ).pack(side=LEFT, padx=(0, 10))

        ttk.Label(logo_frame,
                  text="Disk Analyzer",
                  font=('Segoe UI', 20, 'bold'),
                  foreground=self.colors['text_primary']
                  ).pack(side=LEFT)

        ttk.Label(logo_frame,
                  text="Pro",
                  font=('Segoe UI', 14, 'bold'),
                  foreground=self.colors['accent']
                  ).pack(side=LEFT, padx=(5, 0))

        ttk.Label(logo_frame,
                  text="🧠 Умный кэш",
                  font=('Segoe UI', 10),
                  foreground=self.colors['stage_scan']
                  ).pack(side=LEFT, padx=(10, 0))

        status_frame = ttk.Frame(header_frame, style="Modern.TFrame")
        status_frame.pack(side=RIGHT)

        self.status_indicator = Canvas(status_frame, width=10, height=10,
                                       bg=self.colors['bg_primary'], highlightthickness=0)
        self.status_indicator.pack(side=LEFT, padx=(0, 8))
        self.status_indicator.create_oval(2, 2, 8, 8, fill=self.colors['success'], tags="indicator")

        self.status_text = ttk.Label(status_frame,
                                     text="Готов к работе",
                                     font=('Segoe UI', 10),
                                     foreground=self.colors['text_secondary']
                                     )
        self.status_text.pack(side=LEFT)

    def create_control_panel(self, parent):
        """Создание панели управления"""
        control_frame = ttk.LabelFrame(parent,
                                       text="Параметры сканирования",
                                       style="Card.TLabelframe",
                                       padding=(20, 15)
                                       )
        control_frame.pack(fill=X, pady=(0, 15))

        top_row = ttk.Frame(control_frame, style="Modern.TFrame")
        top_row.pack(fill=X, pady=(0, 12))

        path_frame = ttk.Frame(top_row, style="Modern.TFrame")
        path_frame.pack(side=LEFT, fill=X, expand=True, padx=(0, 15))

        ttk.Label(path_frame,
                  text="Целевая папка",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']
                  ).pack(anchor=W, pady=(0, 4))

        path_input_frame = ttk.Frame(path_frame, style="Modern.TFrame")
        path_input_frame.pack(fill=X)

        self.path_entry = ttk.Entry(path_input_frame,
                                    textvariable=self.root_path,
                                    style="Modern.TEntry"
                                    )
        self.path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 8))

        ttk.Button(path_input_frame,
                   text="📁 Обзор",
                   command=self.browse_folder,
                   style="Secondary.TButton",
                   width=12
                   ).pack(side=LEFT)

        settings_frame = ttk.Frame(top_row, style="Modern.TFrame")
        settings_frame.pack(side=LEFT, padx=(10, 0))

        # УДАЛЯЕМ БЛОК С МИНИМАЛЬНЫМ РАЗМЕРОМ

        # Ряд с кэшем
        cache_frame = ttk.Frame(settings_frame, style="Modern.TFrame")
        cache_frame.pack(anchor=W, pady=(2, 0))

        self.cache_check = ttk.Checkbutton(cache_frame,
                                           text="Использовать кэш ⚡",
                                           variable=self.use_cache,
                                           style="Modern.TCheckbutton"
                                           )
        self.cache_check.pack(anchor=W)

        ttk.Label(cache_frame,
                  text="(сканирует только новые папки)",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']
                  ).pack(anchor=W)

        # Кнопки
        actions_frame = ttk.Frame(top_row, style="Modern.TFrame")
        actions_frame.pack(side=LEFT, padx=(15, 0))

        self.scan_btn = ttk.Button(actions_frame,
                                   text="⚡ Начать сканирование",
                                   command=self.start_scan,
                                   style="Primary.TButton"
                                   )
        self.scan_btn.pack(side=LEFT, padx=(0, 8))

        self.cancel_btn = ttk.Button(actions_frame,
                                     text="⏹ Остановить",
                                     command=self.cancel_scan,
                                     style="Secondary.TButton",
                                     state=DISABLED
                                     )
        self.cancel_btn.pack(side=LEFT)

        # УДАЛЯЕМ ПОДСКАЗКУ ПРО МИНИМАЛЬНЫЙ РАЗМЕР

    def create_navigation_panel(self, parent):
        """Создание панели навигации"""
        nav_frame = ttk.Frame(parent, style="Modern.TFrame")
        nav_frame.pack(fill=X, pady=(0, 10))

        # Кнопка назад
        self.back_btn = ttk.Button(nav_frame,
                                   text="◀ Назад",
                                   command=self.go_back,
                                   style="Secondary.TButton",
                                   state=DISABLED
                                   )
        self.back_btn.pack(side=LEFT, padx=(0, 10))

        # Текущий путь
        self.path_label = ttk.Label(nav_frame,
                                    text="📁 Текущая папка: не выбрана",
                                    font=('Segoe UI', 10),
                                    foreground=self.colors['text_secondary']
                                    )
        self.path_label.pack(side=LEFT, fill=X, expand=True)

        # Кнопка открыть папку в проводнике
        ttk.Button(nav_frame,
                   text="📂 Открыть папку",
                   command=self.open_current_folder_in_explorer,
                   style="Secondary.TButton"
                   ).pack(side=RIGHT, padx=(5, 0))

        # Кнопка обновить текущую папку
        ttk.Button(nav_frame,
                   text="🔄 Обновить",
                   command=self.refresh_current_folder,
                   style="Secondary.TButton"
                   ).pack(side=RIGHT, padx=(5, 0))

        # Кнопка сканировать все
        ttk.Button(nav_frame,
                   text="📊 Сканировать все",
                   command=self.scan_all_from_current,
                   style="Secondary.TButton"
                   ).pack(side=RIGHT)

    def create_progress_bars(self, parent):
        """Создание прогресс-баров"""
        progress_container = ttk.Frame(parent, style="Modern.TFrame")
        progress_container.pack(fill=X, pady=(0, 15))

        main_progress_frame = ttk.Frame(progress_container, style="Modern.TFrame")
        main_progress_frame.pack(fill=X, pady=(0, 8))

        ttk.Label(main_progress_frame,
                  text="📊 Общий прогресс:",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']
                  ).pack(anchor=W, pady=(0, 2))

        progress_row = ttk.Frame(main_progress_frame, style="Modern.TFrame")
        progress_row.pack(fill=X)

        self.progress_var = DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_row,
                                            variable=self.progress_var,
                                            maximum=100,
                                            style="Modern.Horizontal.TProgressbar"
                                            )
        self.progress_bar.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))

        self.progress_percent = ttk.Label(progress_row,
                                          text="0%",
                                          font=('Segoe UI', 9, 'bold'),
                                          foreground=self.colors['accent'],
                                          width=6
                                          )
        self.progress_percent.pack(side=RIGHT)

        detail_progress_frame = ttk.Frame(progress_container, style="Modern.TFrame")
        detail_progress_frame.pack(fill=X)

        folder_info_frame = ttk.Frame(detail_progress_frame, style="Modern.TFrame")
        folder_info_frame.pack(fill=X, pady=(0, 2))

        self.stage_label = ttk.Label(folder_info_frame,
                                     text="🔄 Этап: Ожидание",
                                     font=('Segoe UI', 9, 'bold'),
                                     foreground=self.colors['text_secondary']
                                     )
        self.stage_label.pack(side=LEFT)

        self.current_folder_label = ttk.Label(folder_info_frame,
                                              text="📁 Папка: -",
                                              font=('Segoe UI', 9),
                                              foreground=self.colors['text_secondary']
                                              )
        self.current_folder_label.pack(side=LEFT, padx=(15, 0))

        self.files_count_label = ttk.Label(folder_info_frame,
                                           text="📄 Файлов: 0",
                                           font=('Segoe UI', 9),
                                           foreground=self.colors['text_muted']
                                           )
        self.files_count_label.pack(side=RIGHT)

        detail_row = ttk.Frame(detail_progress_frame, style="Modern.TFrame")
        detail_row.pack(fill=X, pady=(2, 0))

        self.folder_progress_var = DoubleVar()
        self.folder_progress_bar = ttk.Progressbar(detail_row,
                                                   variable=self.folder_progress_var,
                                                   maximum=100,
                                                   style="Detail.Horizontal.TProgressbar"
                                                   )
        self.folder_progress_bar.pack(side=LEFT, fill=X, expand=True, padx=(0, 10))

        self.folder_progress_percent = ttk.Label(detail_row,
                                                 text="0%",
                                                 font=('Segoe UI', 9, 'bold'),
                                                 foreground=self.colors['cache_hit'],
                                                 width=6
                                                 )
        self.folder_progress_percent.pack(side=RIGHT)

        file_info_frame = ttk.Frame(detail_progress_frame, style="Modern.TFrame")
        file_info_frame.pack(fill=X, pady=(2, 0))

        self.current_file_label = ttk.Label(file_info_frame,
                                            text="📄 Файл: -",
                                            font=('Segoe UI', 8),
                                            foreground=self.colors['text_muted']
                                            )
        self.current_file_label.pack(side=LEFT)

        self.scan_status = ttk.Label(file_info_frame,
                                     text="⏳ Ожидание",
                                     font=('Segoe UI', 8),
                                     foreground=self.colors['text_muted']
                                     )
        self.scan_status.pack(side=RIGHT)

    def create_tabs(self, parent):
        """Создание вкладок"""
        notebook = ttk.Notebook(parent, style="Modern.TNotebook")
        notebook.pack(fill=BOTH, expand=True)

        results_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(results_tab, text="📊 Результаты")
        self.create_results_tab(results_tab)

        logs_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(logs_tab, text="📝 Логи")
        self.create_logs_tab(logs_tab)

        cache_tab = ttk.Frame(notebook, style="Modern.TFrame")
        notebook.add(cache_tab, text="💾 Кэш")
        self.create_cache_tab(cache_tab)

    def create_results_tab(self, parent):
        """Создание вкладки результатов"""
        table_frame = ttk.Frame(parent, style="Modern.TFrame")
        table_frame.pack(fill=BOTH, expand=True)

        columns = ("#", "📁 Имя", "📦 Размер", "⚡ Источник", "🔗 Путь")
        self.tree = ttk.Treeview(table_frame,
                                 columns=columns,
                                 show="headings",
                                 style="Table.Treeview"
                                 )

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

        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        actions_frame = ttk.Frame(parent, style="Modern.TFrame")
        actions_frame.pack(fill=X, pady=(10, 0))

        ttk.Button(actions_frame,
                   text="📂 Открыть папку",
                   command=self.open_folder,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(actions_frame,
                   text="📋 Копировать путь",
                   command=self.copy_path_from_tree,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(actions_frame,
                   text="📊 Детали",
                   command=self.show_details,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(actions_frame,
                   text="🗑️ Очистить",
                   command=self.clear_results,
                   style="Secondary.TButton"
                   ).pack(side=LEFT)

        ttk.Label(actions_frame,
                  text="💡 Двойной клик - переход в папку | Ctrl+C - копировать путь",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']
                  ).pack(side=RIGHT)

        # Двойной клик для перехода в папку
        self.tree.bind("<Double-1>", self.navigate_to_folder)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def create_logs_tab(self, parent):
        """Создание вкладки логов"""
        log_control = ttk.Frame(parent, style="Modern.TFrame")
        log_control.pack(fill=X, pady=(0, 10))

        ttk.Label(log_control,
                  text="Фильтр:",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']
                  ).pack(side=LEFT, padx=(0, 8))

        self.log_filter = StringVar(value="Все")
        filter_combo = ttk.Combobox(log_control,
                                    textvariable=self.log_filter,
                                    values=["Все", "Инфо", "Предупреждение", "Ошибка", "Успех", "Детали", "Кэш"],
                                    style="Modern.TCombobox",
                                    width=15,
                                    state="readonly"
                                    )
        filter_combo.pack(side=LEFT, padx=(0, 15))
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_log_filter())

        ttk.Button(log_control,
                   text="🧹 Очистить логи",
                   command=self.clear_logs,
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 8))

        ttk.Button(log_control,
                   text="💾 Сохранить логи",
                   command=self.save_logs,
                   style="Secondary.TButton"
                   ).pack(side=LEFT)

        self.log_counter_label = ttk.Label(log_control,
                                           text="Записей: 0",
                                           font=('Segoe UI', 9),
                                           foreground=self.colors['text_secondary']
                                           )
        self.log_counter_label.pack(side=RIGHT)

        log_frame = ttk.Frame(parent, style="Modern.TFrame")
        log_frame.pack(fill=BOTH, expand=True)

        self.log_text = ScrolledText(log_frame,
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'],
                                     insertbackground=self.colors['accent'],
                                     font=('Consolas', 10),
                                     relief='flat',
                                     borderwidth=1,
                                     wrap=WORD,
                                     padx=12,
                                     pady=8
                                     )
        self.log_text.pack(fill=BOTH, expand=True)

        # Настройка тегов
        self.log_text.tag_configure("info", foreground=self.colors['text_secondary'])
        self.log_text.tag_configure("success", foreground=self.colors['success'])
        self.log_text.tag_configure("warning", foreground=self.colors['warning'])
        self.log_text.tag_configure("error", foreground=self.colors['error'])
        self.log_text.tag_configure("highlight", foreground=self.colors['accent'])
        self.log_text.tag_configure("detail", foreground=self.colors['cache_hit'])
        self.log_text.tag_configure("cache", foreground=self.colors['cache_hit'])
        self.log_text.tag_configure("timestamp", foreground=self.colors['text_muted'])

        # Подсказка для логов
        ttk.Label(log_control,
                  text="💡 Ctrl+C - копировать выделенный текст",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']
                  ).pack(side=RIGHT, padx=(10, 0))

    def create_status_bar(self, parent):
        """Создание статус-бара"""
        status_frame = ttk.Frame(parent, style="Modern.TFrame")
        status_frame.pack(fill=X, pady=(15, 0))

        ttk.Separator(status_frame, orient='horizontal', style="Modern.TSeparator").pack(fill=X, pady=(0, 8))

        info_frame = ttk.Frame(status_frame, style="Modern.TFrame")
        info_frame.pack(fill=X)

        self.status_info = ttk.Label(info_frame,
                                     text="Готов к работе ⚡",
                                     font=('Segoe UI', 9),
                                     foreground=self.colors['text_secondary']
                                     )
        self.status_info.pack(side=LEFT)

        ttk.Label(info_frame,
                  text=f"💾 Кэш: {self.cache.get_cache_stats()['total_entries']} записей",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']
                  ).pack(side=RIGHT, padx=(0, 15))

        ttk.Label(info_frame,
                  text="v5.1 • Частичное обновление",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']
                  ).pack(side=RIGHT)

    def load_default_drive(self):
        """Загрузка диска по умолчанию (если нет сохраненной папки)"""
        debug_print("Загрузка диска по умолчанию")
        if os.name == 'nt':
            drives = [f"{d}:\\" for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ' if os.path.exists(f"{d}:\\")]
            if drives:
                self.root_path.set(drives[0])
                self.add_log(f"Выбран диск по умолчанию: {drives[0]}", "info")
                debug_print(f"Выбран диск: {drives[0]}")
        else:
            self.root_path.set(os.path.expanduser("~"))
            self.add_log(f"Выбрана домашняя папка: {self.root_path.get()}", "info")
            debug_print(f"Выбрана домашняя папка: {self.root_path.get()}")

    def browse_folder(self):
        """Выбор папки через диалог"""
        debug_print("Открытие диалога выбора папки")
        folder = filedialog.askdirectory(
            title="Выберите папку для анализа",
            initialdir=self.root_path.get() if self.root_path.get() else "/"
        )
        if folder:
            debug_print(f"Выбрана папка: {folder}")
            self.root_path.set(folder)  # <-- ТОЛЬКО ЗДЕСЬ МЕНЯЕТСЯ ЦЕЛЕВАЯ ПАПКА
            self.settings.set('last_path', folder)  # <-- ТОЛЬКО ЗДЕСЬ СОХРАНЯЕТСЯ
            self.add_log(f"📁 Выбрана папка: {folder}", "info")
            self.set_status("Папка выбрана", "info")

            self.scan_status.config(text="⏳ Загрузка папки...")
            self.progress_var.set(0)
            self.progress_percent.config(text="0%")

            self.root.after(100, lambda: self.navigate_to_path(folder))
        else:
            debug_print("Выбор папки отменен")

    # ==================== НАВИГАЦИЯ ПО ПАПКАМ ====================

    def navigate_to_folder(self, event=None):
        """Переход в выбранную папку по двойному клику"""
        debug_print("Навигация по двойному клику")
        selection = self.tree.selection()
        if not selection:
            debug_print("Нет выделенных элементов")
            return

        values = self.tree.item(selection[0], 'values')
        if not values or len(values) < 5:
            debug_print("Некорректные данные в таблице")
            return

        path = values[4]  # Путь в 5-й колонке
        debug_print(f"Переход в папку: {path}")

        if not os.path.exists(path) or not os.path.isdir(path):
            self.add_log(f"⚠️ Папка не существует или недоступна: {path}", "warning")
            debug_print(f"Папка не существует: {path}")
            return

        self.navigate_to_path(path)

    def navigate_to_path(self, path):
        """Переход в указанную папку (асинхронно) - НЕ меняет целевую папку"""
        debug_print(f"Навигация в: {path}")

        if not os.path.exists(path) or not os.path.isdir(path):
            self.add_log(f"⚠️ Невозможно перейти в: {path}", "warning")
            debug_print(f"Невозможно перейти: {path}")
            return

        # ========== СОХРАНЯЕМ ТЕКУЩЕЕ СОСТОЯНИЕ ТАБЛИЦЫ (ЕСЛИ НЕ КОРЕНЬ СКАНИРОВАНИЯ) ==========
        if self.current_nav_path and self.current_nav_path != path:
            # НЕ СОХРАНЯЕМ корень сканирования — он уже есть в last_scan_results
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
                                'path': values[4]
                            })
                    self.table_state_cache[self.current_nav_path] = items_data
                    debug_print(
                        f"💾 Сохранено состояние таблицы для: {self.current_nav_path} ({len(items_data)} элементов)")

            self.navigation_history.append(self.current_nav_path)
            debug_print(f"История: добавлен {self.current_nav_path}")

        self.current_nav_path = path
        self.update_navigation_ui()
        self.add_log(f"📂 Переход в папку: {path}", "info")
        self.path_label.config(text=f"📁 {path}")

        self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)
        debug_print(f"Кнопка Назад: {'включена' if self.navigation_history else 'выключена'}")

        self.root.after(100, lambda: self.scan_current_folder(path))

    def go_back(self):
        """Возврат на предыдущий уровень"""
        debug_print("Возврат назад")
        if not self.navigation_history:
            self.add_log("⚠️ История пуста", "warning")
            debug_print("История пуста")
            return

        previous_path = self.navigation_history[-1]

        # ========== ЕСЛИ ВОЗВРАЩАЕМСЯ В КОРЕНЬ СКАНИРОВАНИЯ ==========
        if previous_path == self.last_scan_root and self.last_scan_root_subfolders:
            debug_print(f"📊 ВОЗВРАТ В КОРЕНЬ СКАНИРОВАНИЯ: {previous_path}")

            # Удаляем текущий путь из истории
            self.navigation_history.pop()
            self.current_nav_path = previous_path
            self.update_navigation_ui()
            self.path_label.config(text=f"📁 {previous_path}")
            self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)

            # ========== ПОКАЗЫВАЕМ ТОЛЬКО ПРЯМЫЕ ПОДПАПКИ ==========
            self.add_log(f"◀ Возврат в корень: {previous_path}", "info")
            self._display_folder_items(self.last_scan_root_subfolders, "📊 Результаты сканирования")
            return

        # Сохраняем текущее состояние (для подпапок)
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
                            'path': values[4]
                        })
                self.table_state_cache[self.current_nav_path] = items_data
                debug_print(f"💾 Сохранено состояние для: {self.current_nav_path}")

        previous_path = self.navigation_history.pop()
        debug_print(f"Возврат в: {previous_path}")
        self.current_nav_path = previous_path
        self.update_navigation_ui()
        self.add_log(f"◀ Возврат в: {previous_path}", "info")
        self.path_label.config(text=f"📁 {previous_path}")

        self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)

        # ВОССТАНАВЛИВАЕМ состояние для подпапки
        self.root.after(100, lambda: self.scan_current_folder(previous_path))

    def update_navigation_ui(self):
        """Обновление интерфейса навигации"""
        self.back_btn.config(state=NORMAL if self.navigation_history else DISABLED)
        if self.current_nav_path:
            # УБИРАЕМ изменение root_path
            # self.root_path.set(self.current_nav_path)  # <-- УДАЛЕНО
            # self.path_entry.delete(0, END)  # <-- УДАЛЕНО
            # self.path_entry.insert(0, self.current_nav_path)  # <-- УДАЛЕНО
            debug_print(f"UI обновлен: {self.current_nav_path}")

    def _start_scan_current_folder(self, path):
        """Запуск сканирования папки в отдельном потоке"""
        # Проверяем, не запущено ли уже сканирование
        if hasattr(self, '_scan_thread') and self._scan_thread and self._scan_thread.is_alive():
            debug_print("Сканирование уже выполняется, отменяем предыдущее")
            self._scanning_folder = False
            # Ждем завершения потока
            self._scan_thread.join(timeout=0.5)

        # Сбрасываем флаг
        self._scanning_folder = True

        # Запускаем новое сканирование
        self._scan_thread = threading.Thread(target=self.scan_current_folder, args=(path,))
        self._scan_thread.daemon = True
        self._scan_thread.start()
        debug_print(f"Поток сканирования запущен для: {path}")

    def scan_current_folder(self, path):
        """Загрузка содержимого папки из кэша (БЕЗ СКАНИРОВАНИЯ)"""
        debug_print(f"Загрузка папки из кэша: {path}")

        # ========== КОРЕНЬ СКАНИРОВАНИЯ ==========
        if self.last_scan_root and path == self.last_scan_root and self.last_scan_root_subfolders:
            debug_print(f"📊 КОРЕНЬ СКАНИРОВАНИЯ: {path}")
            # ========== ПОКАЗЫВАЕМ ТОЛЬКО ПРЯМЫЕ ПОДПАПКИ ==========
            self.root.after(0, lambda: self._display_folder_items(
                self.last_scan_root_subfolders,
                "📊 Результаты сканирования"
            ))
            return

        # ========== ДЛЯ ПОДПАПОК ==========
        if path in self.table_state_cache:
            items_data = self.table_state_cache[path]
            debug_print(f"✅ ВОССТАНОВЛЕНИЕ СОСТОЯНИЯ ТАБЛИЦЫ для: {path} ({len(items_data)} элементов)")
            self.root.after(0, lambda: self._restore_table_state(items_data, path))
            return

        # ========== НЕТ В КЭШЕ ==========
        self._load_folder_async(path)

    def _display_folder_items(self, items, source_label=""):
        """
        Отображение элементов папки в таблице с ПАКЕТНОЙ ВСТАВКОЙ
        (универсальный метод для всех случаев)
        """
        if not items:
            self.tree.delete(*self.tree.get_children())
            self.results = []
            self.scan_status.config(text="📂 Папка пуста")
            self.set_status("Папка пуста", "info")
            return

        current_path = self.current_nav_path

        # Проверяем, не загружены ли уже эти данные
        existing_items = self.tree.get_children()
        if existing_items and len(existing_items) == len(items):
            first_item = self.tree.item(existing_items[0], 'values')
            if first_item and len(first_item) >= 5:
                first_path = first_item[4]
                if items and items[0].get('path', '') == first_path:
                    debug_print(f"✅ Данные уже загружены, пропускаем вставку для {current_path}")
                    self.results = items
                    self.scan_status.config(
                        text=f"✅ {source_label}: {len(items)} папок" if source_label else f"✅ {len(items)} папок")
                    self.set_status(f"{len(items)} папок", "success")
                    self.stage_label.config(text="✅ Готово", foreground=self.colors['success'])
                    if self.progress_var.get() < 100:
                        self.progress_var.set(100)
                        self.progress_percent.config(text="100%")
                        self.folder_progress_var.set(100)
                        self.folder_progress_percent.config(text="100%")
                    return

        # Очищаем таблицу
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

        # Для большого количества — пакетная вставка
        self._insert_items_batched(items, source_label, total_items)

    def refresh_current_folder(self):
        """Обновление текущей папки (принудительное пересканирование)"""
        debug_print("Обновление текущей папки")
        if self.current_nav_path:
            # Очищаем кэш для этой папки, чтобы принудительно пересканировать
            if self.current_nav_path in self.scanned_folders_cache:
                del self.scanned_folders_cache[self.current_nav_path]
                debug_print(f"Кэш очищен для: {self.current_nav_path}")

            # Также очищаем основной кэш для этой папки
            key = self.cache.get_folder_key(self.current_nav_path)
            if key in self.cache.cache:
                del self.cache.cache[key]
                self.cache.save_cache()
                debug_print(f"Основной кэш очищен для: {self.current_nav_path}")

            # Показываем статус
            self.scan_status.config(text="⏳ Обновление...")
            self.progress_var.set(0)
            self.progress_percent.config(text="0%")

            # Запускаем сканирование с задержкой
            self.root.after(100, lambda: self._start_scan_current_folder(self.current_nav_path))
            self.add_log("🔄 Принудительное обновление папки...", "info")
        else:
            self.add_log("⚠️ Нет активной папки", "warning")
            debug_print("Нет активной папки")

    def scan_all_from_current(self):
        """Сканирование всех папок начиная с текущей"""
        debug_print("Запуск полного сканирования из текущей папки")
        if not self.current_nav_path:
            self.add_log("⚠️ Сначала перейдите в папку", "warning")
            debug_print("Нет активной папки для сканирования")
            return

        # МЕНЯЕМ ЦЕЛЕВУЮ ПАПКУ на текущую (при ручном действии)
        self.root_path.set(self.current_nav_path)
        self.settings.set('last_path', self.current_nav_path)
        self.start_scan()

    # ==================== ПОЛНОЕ СКАНИРОВАНИЕ ====================

    def start_scan(self):
        """Запуск сканирования целевой папки"""
        if self.scanning:
            debug_print("Сканирование уже выполняется")
            return

        path = self.root_path.get().strip()
        if not path:
            messagebox.showerror("Ошибка", "Выберите папку для сканирования")
            debug_print("Путь не выбран")
            return

        if not os.path.exists(path):
            messagebox.showerror("Ошибка", "Указанный путь не существует")
            debug_print(f"Путь не существует: {path}")
            return

        # Очищаем предыдущие результаты сканирования
        self.last_scan_root = ""
        self.last_scan_results = []
        self.last_scan_total_size = 0

        debug_print(f"Запуск сканирования: {path}")
        self.clear_results()
        self.error_count = 0
        self.add_log("=" * 70, "info")
        self.add_log("⚡ НАЧАЛО ОПТИМИЗИРОВАННОГО СКАНИРОВАНИЯ", "highlight")
        self.add_log(f"📁 Путь: {path}", "info")
        self.add_log(f"💾 Кэш: {'ВКЛЮЧЕН ⚡' if self.use_cache.get() else 'ВЫКЛЮЧЕН'}", "info")
        self.add_log(f"⚡ Потоков: {self.max_workers}, Батч: {self.batch_size}", "info")
        self.add_log("=" * 70, "info")

        self.scanning = True
        self.scan_start_time = time.time()
        self.scan_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.set_status("Сканирование...", "scanning")

        # Сбрасываем прогресс
        self.progress_var.set(0)
        self.progress_percent.config(text="0%")
        self.folder_progress_var.set(0)
        self.folder_progress_percent.config(text="0%")
        self.stage_label.config(text="🔄 Этап: Подготовка...", foreground=self.colors['stage_prepare'])
        self.current_folder_label.config(text="📁 Папка: Сбор информации...")
        self.current_file_label.config(text="📄 Подготовка...")
        self.files_count_label.config(text="📄 Файлов: 0")
        self.scan_status.config(text="⏳ Подготовка...")

        # Запускаем сканирование в отдельном потоке
        thread = threading.Thread(target=self.scan_folder_optimized, args=(path,))
        thread.daemon = True
        thread.start()
        debug_print("Поток сканирования запущен")

    def _collect_all_folders(self, path, result_list, current_count, min_size_mb):
        """Сбор ВСЕХ папок с полным рекурсивным обходом"""
        try:
            if not os.access(path, os.R_OK):
                return

            # Обновляем UI
            self.root.after(0, lambda: self.current_folder_label.config(
                text=f"📁 Сканирование: {os.path.basename(path)}"
            ))

            # ПОЛНОЕ сканирование папки (как раньше)
            try:
                # Получаем точный размер ВСЕХ файлов (рекурсивно)
                total_size, file_count = self.cache.scan_folder_full(path)
            except Exception as e:
                debug_print(f"Ошибка при сканировании {path}: {e}")
                return

            # Если папка достаточно большая - добавляем в список
            if total_size > min_size_mb * 1024 * 1024:
                result_list.append(path)
                current_count[0] += 1

                size_str = format_size(total_size)
                self.root.after(0, lambda c=current_count[0], p=path, s=size_str:
                self.scan_status.config(text=f"📁 Найдено: {c} ({os.path.basename(p)}) - {s}")
                                )
                self.root.after(0, lambda p=path, s=size_str:
                self.add_log(f"📁 {os.path.basename(p)} - {s}", "detail")
                                )

                # Сохраняем в кэш сразу
                self.cache.update_cache_full(path)

            # Рекурсивно заходим во ВСЕ подпапки
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if not self.scanning:
                            return
                        if entry.is_dir():
                            folder_name = entry.name
                            if folder_name in self.system_folders:
                                continue
                            self._collect_all_folders(entry.path, result_list, current_count, min_size_mb)
            except (PermissionError, OSError):
                pass

        except (PermissionError, OSError):
            pass

    def scan_folder_optimized(self, path):
        """СУПЕР-БЫСТРОЕ сканирование через ОДИН ПРОХОД scandir"""
        debug_print(f"Начало сканирования в потоке: {path}")
        try:
            start_time = time.time()
            use_cache = self.use_cache.get()

            self.root.after(0, lambda: self.stage_label.config(
                text="🚀 Этап 1/3: Один проход сканирования...",
                foreground=self.colors['stage_scan']
            ))
            self.root.after(0, lambda: self.scan_status.config(text="⏳ Сканирование в один проход..."))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: self.progress_percent.config(text="0%"))
            self.root.after(0, lambda: self.folder_progress_var.set(0))
            self.root.after(0, lambda: self.folder_progress_percent.config(text="0%"))

            self.add_log(f"📂 Один проход сканирования...", "info")

            def is_scanning():
                return self.scanning

            import threading
            result = {'sizes': None, 'counts': None, 'error': None, 'stopped': False}

            def scan_thread():
                try:
                    sizes, counts = self.cache.scan_all_folders_one_pass(
                        path,
                        progress_callback=self._update_scan_progress,
                        scanning_flag=is_scanning
                    )
                    if not is_scanning():
                        result['stopped'] = True
                        return
                    result['sizes'] = sizes
                    result['counts'] = counts
                except Exception as e:
                    result['error'] = str(e)

            thread = threading.Thread(target=scan_thread)
            thread.daemon = True
            thread.start()

            while thread.is_alive():
                self.root.update_idletasks()
                time.sleep(0.1)

            if result['error']:
                self.add_log(f"❌ Ошибка: {result['error']}", "error")
                self.root.after(0, self.scan_complete)
                return

            if result['stopped'] or not self.scanning:
                self.add_log("⏹️ Сканирование остановлено пользователем", "warning")
                self.root.after(0, self.scan_complete)
                return

            folder_sizes = result['sizes']
            folder_counts = result['counts']
            total = len(folder_sizes)

            if total == 0:
                self.add_log("⚠️ Папок не найдено", "warning")
                self.root.after(0, self.scan_complete)
                return

            self.add_log(f"📊 Просканировано {total} папок за {time.time() - start_time:.1f} сек", "success")
            debug_print(f"Просканировано {total} папок")

            # ========== ЭТАП 2: Сохранение в кэш ==========
            if use_cache and folder_sizes:
                self.root.after(0, lambda: self.stage_label.config(
                    text="💾 Этап 2/3: Сохранение в кэш...",
                    foreground=self.colors['stage_cache']
                ))

                self.add_log(f"💾 Сохранение {len(folder_sizes)} папок в кэш...", "info")

                cache_items = []
                for folder, size in folder_sizes.items():
                    if size > 0:
                        cache_items.append((folder, size, folder_counts.get(folder, 0)))

                if cache_items:
                    # Сохраняем с обновлением прогресса (80-95%)
                    self.cache.save_cache_batch_with_progress(cache_items, self._update_scan_progress)
                    self.add_log(f"💾 Сохранено {len(cache_items)} папок в кэш", "success")

            # ========== ЭТАП 3: Формирование результатов ==========
            self.root.after(0, lambda: self.stage_label.config(
                text="📊 Этап 3/3: Формирование результатов...",
                foreground=self.colors['stage_prepare']
            ))
            self.root.after(0, lambda: self.scan_status.config(text="⏳ Формирование результатов..."))
            self.root.after(0, lambda: self.progress_var.set(95))
            self.root.after(0, lambda: self.progress_percent.config(text="95%"))

            self.add_log(f"📊 Формирование списка {len(folder_sizes)} папок...", "info")

            # ========== СОХРАНЯЕМ ВСЕ ПАПКИ (для деталей) ==========
            all_results = []
            for folder, size in folder_sizes.items():
                if size > 0:
                    all_results.append({
                        'name': os.path.basename(folder),
                        'size': size,
                        'size_str': format_size(size),
                        'path': folder,
                        'source': '🔄 Сканирование',
                        'file_count': folder_counts.get(folder, 0)
                    })

            all_results.sort(key=lambda x: x['size'], reverse=True)

            # ========== СОХРАНЯЕМ ТОЛЬКО ПРЯМЫЕ ПОДПАПКИ КОРНЯ (для отображения) ==========
            root_subfolders = []
            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if not self.scanning:
                            break
                        if entry.is_dir():
                            folder_name = entry.name
                            if folder_name in self.system_folders:
                                continue
                            # Находим размер этой папки из результатов сканирования
                            size = folder_sizes.get(entry.path, 0)
                            if size > 0:
                                root_subfolders.append({
                                    'name': folder_name,
                                    'size': size,
                                    'size_str': format_size(size),
                                    'path': entry.path,
                                    'source': '🔄 Сканирование',
                                    'file_count': folder_counts.get(entry.path, 0)
                                })
                root_subfolders.sort(key=lambda x: x['size'], reverse=True)
                debug_print(f"📂 Прямых подпапок корня: {len(root_subfolders)}")
            except Exception as e:
                debug_print(f"Ошибка получения прямых подпапок: {e}")
                # Если ошибка — используем все папки как запасной вариант
                root_subfolders = all_results[:500]  # Ограничиваем до 500

            # ========== СОХРАНЯЕМ РЕЗУЛЬТАТЫ ==========
            self.last_scan_root = path
            self.last_scan_results = all_results  # Все папки (для деталей)
            self.last_scan_root_subfolders = root_subfolders  # Только прямые подпапки (для отображения)
            self.last_scan_total_size = sum(r['size'] for r in all_results)

            # Прогресс 100% - готово!
            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_percent.config(text="100%"))
            self.root.after(0, lambda: self.folder_progress_var.set(100))
            self.root.after(0, lambda: self.folder_progress_percent.config(text="100%"))
            self.root.after(0, lambda: self.scan_status.config(text="✅ Готово!"))
            self.root.after(0, lambda: self.stage_label.config(
                text="✅ Готово!",
                foreground=self.colors['success']
            ))

            elapsed_time = time.time() - start_time
            self.add_log("=" * 70, "info")
            self.add_log(f"⏱️ Завершено за {elapsed_time:.1f} сек", "success")
            self.add_log(f"📊 Найдено {len(all_results)} папок", "success")
            self.add_log(f"📂 Прямых подпапок: {len(root_subfolders)}", "success")
            if elapsed_time > 0:
                self.add_log(f"⚡ Скорость: {len(all_results) / elapsed_time:.1f} папок/сек", "success")
            self.add_log("=" * 70, "info")

            # ========== ОТОБРАЖАЕМ ТОЛЬКО ПРЯМЫЕ ПОДПАПКИ ==========
            self.root.after(0, lambda: self._display_folder_items(root_subfolders, "📊 Результаты сканирования"))

            # СКАНИРОВАНИЕ ЗАВЕРШЕНО (после отображения)
            self.root.after(100, self.scan_complete)

        except Exception as e:
            debug_print(f"Ошибка: {str(e)}")
            import traceback
            self.add_log(f"❌ Ошибка: {str(e)}", "error")
            traceback.print_exc()
            self.root.after(0, self.scan_complete)
        finally:
            gc.collect()

    def _build_results_from_cache(self, folders):
        """Создает результаты из папок в кэше"""
        results = []
        for folder in folders:
            key = self.cache.get_folder_key(folder)
            if key in self.cache.cache:
                entry = self.cache.cache[key]
                size = entry.get('total_size', 0)
                results.append({
                    'name': os.path.basename(folder),
                    'size': size,
                    'size_str': format_size(size),
                    'path': folder,
                    'source': '💾 Кэш',
                    'depth': 0,
                    'file_count': entry.get('file_count', 0)
                })
        return results

    def process_batch(self, batch, use_cache):
        """Обработка пакета папок с прогрессом"""
        results = []
        hits = 0
        misses = 0
        errors = []
        total = len(batch)

        for idx, folder in enumerate(batch):
            if not self.scanning:
                break

            # Обновляем статус каждые 5 папок
            if idx % 5 == 0:
                self.root.after(0, lambda i=idx, t=total, f=os.path.basename(folder):
                self.scan_status.config(text=f"⏳ Сканирование: {i + 1}/{t} - {f}")
                                )
                self.root.after(0, lambda i=idx, t=total:
                self.current_file_label.config(text=f"📄 Обработка: {i + 1}/{t}")
                                )

            try:
                if use_cache:
                    cached_size = self.cache.get_folder_size_cached(folder)
                    if cached_size is not None:
                        hits += 1
                        results.append({
                            'name': os.path.basename(folder),
                            'size': cached_size,
                            'size_str': format_size(cached_size),
                            'path': folder,
                            'source': '💾 Кэш',
                            'depth': 0,
                            'file_count': 0
                        })
                        continue
                    misses += 1

                # Сканируем папку с обновлением статуса
                self.root.after(0, lambda f=os.path.basename(folder):
                self.current_folder_label.config(text=f"📁 Сканирование: {f}")
                                )

                size, file_count = self.cache.scan_folder_full(folder)
                if size is not None:
                    results.append({
                        'name': os.path.basename(folder),
                        'size': size,
                        'size_str': format_size(size),
                        'path': folder,
                        'source': '🔄 Сканирование',
                        'depth': 0,
                        'file_count': file_count
                    })

                    if use_cache:
                        self.cache.update_cache_full(folder)

                    # Показываем найденную папку
                    self.root.after(0, lambda f=os.path.basename(folder), s=format_size(size):
                    self.add_log(f"  📁 {f} - {s}", "detail")
                                    )

            except Exception as e:
                errors.append(f"{os.path.basename(folder)}: {str(e)}")
                continue

            # Обновляем прогресс-бар
            progress = ((idx + 1) / total) * 100
            self.root.after(0, lambda p=progress: self.folder_progress_var.set(p))
            self.root.after(0, lambda p=progress: self.folder_progress_percent.config(text=f"{p:.0f}%"))

        return results, hits, misses, errors

    def display_results(self, results):
        """Отображение результатов"""
        self.results = results

        # ========== ОЧИЩАЕМ ТАБЛИЦУ И ПОКАЗЫВАЕМ РЕЗУЛЬТАТЫ ==========
        self.tree.delete(*self.tree.get_children())

        for i, item in enumerate(results, 1):
            if item['size'] > 1024 ** 4:
                emoji = "🔴"
            elif item['size'] > 1024 ** 3:
                emoji = "🟡"
            else:
                emoji = "🟢"

            source_emoji = "💾" if "Кэш" in item.get('source', '') else "🔄"

            self.tree.insert("", END, values=(
                i,
                f"{emoji} {item['name']}",
                item['size_str'],
                source_emoji,
                item['path']
            ))

        # ========== СОХРАНЯЕМ ДАННЫЕ КОРНЯ ==========
        self._root_data_loaded = True
        self._root_item_ids = self.tree.get_children()
        self._root_display_data = results.copy()
        self.last_scan_results = results.copy()
        self.last_scan_root = self.current_nav_path

        if results:
            total_size = sum(r['size'] for r in results)
            self.total_size = total_size

            self.add_log("🏆 ТОП-5 САМЫХ БОЛЬШИХ ПАПОК:", "highlight")
            for i, item in enumerate(results[:5], 1):
                self.add_log(
                    f"  {i}. {item['name']} - {item['size_str']} {'⚡' if 'Кэш' in item.get('source', '') else ''}",
                    "info"
                )

            largest = results[0]
            self.add_log(f"🏆 САМАЯ БОЛЬШАЯ: {largest['name']} ({largest['size_str']})", "highlight")

            self.scan_status.config(text=f"✅ Готово! Найдено {len(results)} папок")
            self.set_status("Готово ⚡", "success")

            self.progress_var.set(100)
            self.progress_percent.config(text="100%")
            self.folder_progress_var.set(100)
            self.folder_progress_percent.config(text="100%")
            self.stage_label.config(text="✅ Сканирование завершено", foreground=self.colors['success'])
            self.current_folder_label.config(text="📁 Готово!")
            self.current_file_label.config(text="✅ Все папки обработаны")
        else:
            self.scan_status.config(text="⚠️ Папок не найдено")
            self.set_status("Готово", "info")

    def cancel_scan(self):
        if self.scanning:
            self.scanning = False
            debug_print("Сканирование остановлено пользователем")
            self.add_log("⏹️ СКАНИРОВАНИЕ ОСТАНОВЛЕНО", "warning")
            self.set_status("Остановлено", "error")
            self.scan_btn.config(state=NORMAL)
            self.cancel_btn.config(state=DISABLED)
            self.scan_status.config(text="⏹️ Остановлено")
            self.stage_label.config(text="⏹️ Остановлено", foreground=self.colors['error'])

        # Отменяем сканирование папки
        if hasattr(self, '_scan_thread') and self._scan_thread and self._scan_thread.is_alive():
            self._scanning_folder = False
            debug_print("Сканирование папки остановлено")

    def scan_complete(self):
        self.scanning = False
        debug_print("Сканирование завершено")
        self.scan_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)

        if not self.tree.get_children():
            self.scan_status.config(text="Сканирование завершено. Папок не найдено.")

        self.refresh_cache_list()
        gc.collect()

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
                    except:
                        try:
                            import subprocess
                            subprocess.Popen(['explorer', path])
                        except:
                            messagebox.showerror("Ошибка", "Не удалось открыть папку")
                else:
                    messagebox.showerror("Ошибка", "Папка не существует")

    def show_details(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Информация", "Выберите папку для просмотра деталей")
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
            if item['path'] == path:
                size_bytes = item['size']
                depth = item.get('depth', 0)
                file_count = item.get('file_count', 0)
                break

        self.add_log(f"📊 Просмотр деталей: {name}", "info")

        details_window = Toplevel(self.root)
        details_window.title(f"Детали: {name}")
        details_window.geometry("550x480")
        details_window.configure(bg=self.colors['bg_secondary'])
        details_window.resizable(False, False)

        main_frame = ttk.Frame(details_window, style="Modern.TFrame")
        main_frame.pack(fill=BOTH, expand=True, padx=25, pady=25)

        ttk.Label(main_frame,
                  text=f"📁 {name}",
                  font=('Segoe UI', 16, 'bold'),
                  foreground=self.colors['text_primary']
                  ).pack(anchor=W, pady=(0, 20))

        info_frame = ttk.Frame(main_frame, style="Modern.TFrame")
        info_frame.pack(fill=X, pady=(0, 20))

        info_items = [
            ("Размер:", size_str),
            ("В байтах:", f"{size_bytes:,}"),
            ("Источник:", source),
            ("Файлов:", f"{file_count:,}" if file_count > 0 else "н/д"),
            ("Уровень вложенности:", f"{depth}"),
            ("Путь:", path)
        ]

        for label, value in info_items:
            row = ttk.Frame(info_frame, style="Modern.TFrame")
            row.pack(fill=X, pady=5)

            ttk.Label(row,
                      text=label,
                      font=('Segoe UI', 10, 'bold'),
                      foreground=self.colors['text_secondary'],
                      width=16
                      ).pack(side=LEFT)

            ttk.Label(row,
                      text=value,
                      font=('Segoe UI', 10),
                      foreground=self.colors['text_primary'],
                      wraplength=350
                      ).pack(side=LEFT, fill=X, expand=True)

        btn_frame = ttk.Frame(main_frame, style="Modern.TFrame")
        btn_frame.pack(fill=X)

        ttk.Button(btn_frame,
                   text="📂 Открыть папку",
                   command=lambda: self.open_folder_from_path(path),
                   style="Secondary.TButton"
                   ).pack(side=LEFT, padx=(0, 10))

        ttk.Button(btn_frame,
                   text="📋 Копировать путь",
                   command=lambda: self.copy_path_from_path(path),
                   style="Secondary.TButton"
                   ).pack(side=LEFT)

        if self.total_size > 0 and size_bytes > 0:
            percentage = (size_bytes / self.total_size) * 100
            ttk.Label(main_frame,
                      text=f"Это {percentage:.1f}% от общего размера",
                      font=('Segoe UI', 9),
                      foreground=self.colors['text_muted']
                      ).pack(anchor=W, pady=(20, 0))

        ttk.Label(main_frame,
                  text="✅ Размер вычислен рекурсивно со всеми вложенными файлами",
                  font=('Segoe UI', 8),
                  foreground=self.colors['success']
                  ).pack(anchor=W, pady=(10, 0))

    def open_folder_from_path(self, path):
        if os.path.exists(path):
            try:
                os.startfile(path)
            except:
                try:
                    import subprocess
                    subprocess.Popen(['explorer', path])
                except:
                    pass

    def copy_path_from_path(self, path):
        self.root.clipboard_clear()
        self.root.clipboard_append(path)
        self.add_log(f"📋 Скопирован путь: {path}", "success")

    def clear_results(self):
        """Ручная очистка результатов (по кнопке)"""
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
        self.stage_label.config(text="🔄 Этап: Ожидание", foreground=self.colors['text_secondary'])
        self.current_folder_label.config(text="📁 Папка: -")
        self.current_file_label.config(text="📄 Файл: -")
        self.files_count_label.config(text="📄 Файлов: 0")
        self.add_log("🗑️ Результаты очищены", "info")
        gc.collect()

    def show_context_menu(self, event):
        selection = self.tree.selection()
        if selection:
            menu = Menu(self.root, tearoff=0,
                        bg=self.colors['bg_secondary'],
                        fg=self.colors['text_primary'],
                        activebackground=self.colors['bg_selected'],
                        activeforeground=self.colors['text_light'])
            menu.add_command(label="📂 Перейти в папку", command=self.navigate_to_folder)
            menu.add_command(label="📂 Открыть папку", command=lambda: self.open_folder(None))
            menu.add_command(label="📋 Копировать путь (Ctrl+C)", command=self.copy_path_from_tree)
            menu.add_command(label="📊 Показать детали", command=self.show_details)
            menu.add_separator()
            menu.add_command(label="📋 Выделить всё (Ctrl+A)", command=self.select_all_rows)
            menu.post(event.x_root, event.y_root)

    def refresh_cache_list(self):
        """Обновление списка кэшированных папок"""
        self.cache_tree.delete(*self.cache_tree.get_children())

        try:
            # Получаем данные из SQLite
            import sqlite3
            conn = sqlite3.connect(self.cache.cache_file, timeout=30)
            cursor = conn.cursor()

            # Получаем последние 100 записей по timestamp
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
                timestamp_str = datetime.fromtimestamp(timestamp).strftime(
                    "%Y-%m-%d %H:%M:%S") if timestamp else "Неизвестно"
                folder_name = os.path.basename(path) if path else "Корень"

                self.cache_tree.insert("", END, values=(
                    i,
                    folder_name,
                    size_str,
                    f"{file_count:,}",
                    timestamp_str
                ))

        except Exception as e:
            debug_print(f"Ошибка обновления списка кэша: {e}")
            # Если ошибка - показываем пустой список
            pass

    def clear_cache(self):
        """Очистка кэша"""
        if messagebox.askyesno("Подтверждение", "Вы уверены, что хотите очистить весь кэш?"):
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

    def add_log(self, message, log_type="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_counter += 1

        self.log_queue.put({
            'timestamp': timestamp,
            'message': message,
            'type': log_type,
            'id': self.log_counter
        })

        self.log_counter_label.config(text=f"Записей: {self.log_counter}")
        self.root.after(10, self.process_logs)

    def process_logs(self):
        try:
            while not self.log_queue.empty():
                log_entry = self.log_queue.get_nowait()
                self.display_log(log_entry)
        except queue.Empty:
            pass

    def display_log(self, log_entry):
        timestamp = log_entry['timestamp']
        message = log_entry['message']
        log_type = log_entry['type']

        current_filter = self.log_filter.get()
        if current_filter != "Все":
            type_map = {
                "Инфо": "info",
                "Предупреждение": "warning",
                "Ошибка": "error",
                "Успех": "success",
                "Детали": "detail",
                "Кэш": "cache"
            }
            if log_type != type_map.get(current_filter, ""):
                return

        self.log_text.insert(END, f"[{timestamp}] ", "timestamp")

        emojis = {
            "info": "ℹ️",
            "success": "✅",
            "warning": "⚠️",
            "error": "❌",
            "highlight": "🔹",
            "detail": "📌",
            "cache": "💾"
        }
        self.log_text.insert(END, f"{emojis.get(log_type, '•')} ", "timestamp")
        self.log_text.insert(END, f"{message}\n", log_type)

        self.log_text.see(END)

        if self.log_counter > 500:
            content = self.log_text.get(1.0, END)
            lines = content.split('\n')
            if len(lines) > 500:
                self.log_text.delete(1.0, f"{len(lines) - 500}.0")

    def apply_log_filter(self):
        self.log_text.delete(1.0, END)

        temp_queue = []
        while not self.log_queue.empty():
            temp_queue.append(self.log_queue.get())

        for entry in temp_queue:
            self.display_log(entry)
            self.log_queue.put(entry)

    def clear_logs(self):
        self.log_text.delete(1.0, END)
        self.log_counter = 0
        self.log_counter_label.config(text="Записей: 0")

        while not self.log_queue.empty():
            try:
                self.log_queue.get_nowait()
            except queue.Empty:
                break

        self.add_log("🧹 Логи очищены", "info")

    def save_logs(self):
        try:
            content = self.log_text.get(1.0, END)
            if not content.strip():
                self.add_log("⚠️ Нет логов для сохранения", "warning")
                return

            filename = f"logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)

            self.add_log(f"💾 Логи сохранены в {filename}", "success")
            messagebox.showinfo("Успех", f"Логи сохранены в файл:\n{filename}")
        except Exception as e:
            self.add_log(f"❌ Ошибка сохранения: {str(e)}", "error")
            messagebox.showerror("Ошибка", f"Не удалось сохранить логи: {str(e)}")
