import os
import time
import json
import threading
import sqlite3
from .utils import debug_print, format_size


class SmartCacheManager:
    """Умный менеджер кэша с SQLite хранилищем"""

    def __init__(self, cache_file="folder_cache.db"):
        self.cache_file = cache_file
        self.lock = threading.RLock()
        self.cache_hit_count = 0
        self.cache_miss_count = 0
        self.partial_updates = 0
        self.full_updates = 0

        # Инициализируем базу данных
        self._init_database()

        # Загружаем статистику
        stats = self.get_cache_stats()
        debug_print(f"SmartCacheManager инициализирован: {stats['total_entries']} записей")

    def save_cache_batch_with_progress(self, items, progress_callback):
        """
        Сохранение в кэш с обновлением прогресса (80-95%)
        """
        if not items:
            return

        total = len(items)
        batch_size = 10000
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = MEMORY")
            cursor.execute("BEGIN TRANSACTION")

            for i in range(0, total, batch_size):
                batch = items[i:i + batch_size]

                values = []
                for path, total_size, file_count in batch:
                    key = self.get_folder_key(path)
                    values.append((path, total_size, file_count, time.time(), time.time(), '{}', key))

                cursor.executemany('''
                    INSERT OR REPLACE INTO cache 
                    (path, total_size, file_count, last_modified, timestamp, file_signatures, path_normalized)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', values)

                processed = min(i + batch_size, total)
                stage_progress = (processed / total) * 100
                total_progress = 80 + 15 * (stage_progress / 100)  # 80-95%

                if progress_callback:
                    progress_callback(
                        total_progress,
                        "Сохранение в кэш",
                        stage_progress,
                        f"{processed}/{total} ({stage_progress:.0f}%)"
                    )

                if processed % 50000 == 0 or processed >= total:
                    debug_print(f"  Сохранено {processed}/{total} ({stage_progress:.0f}%)")

            conn.commit()
            conn.close()

            elapsed = time.time() - start_time
            debug_print(f"✅ Сохранено {len(items)} папок за {elapsed:.1f} сек")

        except Exception as e:
            debug_print(f"❌ Ошибка сохранения: {e}")
            try:
                conn.rollback()
            except:
                pass

    def _save_cache_batch_with_progress(self, items, progress_callback):
        """
        Сохранение в кэш с обновлением прогресса
        """
        if not items:
            return

        total = len(items)
        batch_size = 10000

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = MEMORY")
            cursor.execute("BEGIN TRANSACTION")

            for i in range(0, total, batch_size):
                batch = items[i:i + batch_size]

                values = []
                for path, total_size, file_count in batch:
                    key = self.get_folder_key(path)
                    values.append((path, total_size, file_count, time.time(), time.time(), '{}', key))

                cursor.executemany('''
                    INSERT OR REPLACE INTO cache 
                    (path, total_size, file_count, last_modified, timestamp, file_signatures, path_normalized)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', values)

                processed = min(i + batch_size, total)
                stage_progress = (processed / total) * 100
                total_progress = 80 + 20 * (stage_progress / 100)  # 20% от общего

                if progress_callback:
                    progress_callback(
                        total_progress,
                        "Сохранение в кэш",
                        stage_progress,
                        f"{processed}/{total} ({stage_progress:.0f}%)"
                    )

                if processed % 50000 == 0 or processed >= total:
                    debug_print(f"  Сохранено {processed}/{total} ({stage_progress:.0f}%)")

            conn.commit()
            conn.close()

        except Exception as e:
            debug_print(f"❌ Ошибка сохранения: {e}")
            try:
                conn.rollback()
            except:
                pass

    def save_cache_batch(self, items):
        """
        ПАКЕТНОЕ сохранение множества папок в кэш (ОПТИМИЗИРОВАННО)
        items: список кортежей (path, total_size, file_count)
        """
        if not items:
            return

        debug_print(f"💾 Пакетное сохранение {len(items)} папок в кэш...")
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ОПТИМИЗАЦИЯ: отключаем синхронизацию для скорости
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = MEMORY")

            # Начинаем транзакцию
            cursor.execute("BEGIN TRANSACTION")

            batch_size = 20000  # УВЕЛИЧИЛИ ДО 20000
            total = len(items)

            for i in range(0, total, batch_size):
                batch = items[i:i + batch_size]

                values = []
                for path, total_size, file_count in batch:
                    key = self.get_folder_key(path)
                    values.append((
                        path,
                        total_size,
                        file_count,
                        time.time(),
                        time.time(),
                        '{}',
                        key
                    ))

                cursor.executemany('''
                    INSERT OR REPLACE INTO cache 
                    (path, total_size, file_count, last_modified, timestamp, file_signatures, path_normalized)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', values)

                processed = min(i + batch_size, total)
                if processed % 100000 == 0 or processed >= total:
                    progress = int(processed / total * 100)
                    debug_print(f"  Сохранено {processed}/{total} ({progress}%)")

            conn.commit()
            conn.close()

            elapsed = time.time() - start_time
            debug_print(f"✅ Сохранено {len(items)} папок за {elapsed:.1f} сек")

        except Exception as e:
            debug_print(f"❌ Ошибка пакетного сохранения: {e}")
            try:
                conn.rollback()
            except:
                pass

    def get_cached_local_sizes(self, root_path):
        """
        Получение локальных размеров для ВСЕХ папок из кэша
        Возвращает словарь {путь: (размер, количество_файлов)} или None
        """
        try:
            conn = sqlite3.connect(self.cache_file, timeout=30)
            cursor = conn.cursor()

            # Получаем все локальные размеры для папок, начинающихся с root_path
            cursor.execute('''
                           SELECT path, local_size, local_count, timestamp
                           FROM local_sizes
                           WHERE path LIKE ? OR path_normalized LIKE ?
                           ''', (root_path + '%', root_path.lower().replace('\\', '/') + '%'))

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return None

            # Проверяем актуальность (не старше 7 дней)
            result = {}
            for path, local_size, local_count, timestamp in rows:
                if time.time() - timestamp < 86400 * 7:  # 7 дней
                    result[path] = (local_size, local_count)

            if result:
                debug_print(f"📂 Загружено {len(result)} локальных размеров из кэша")
                return result

            return None

        except Exception as e:
            debug_print(f"Ошибка чтения локальных размеров: {e}")
            return None

    def save_local_sizes(self, local_sizes, local_counts):
        """
        Сохранение локальных размеров в кэш (ОПТИМИЗИРОВАННО)
        """
        if not local_sizes:
            return

        debug_print(f"💾 Сохранение {len(local_sizes)} локальных размеров в кэш...")
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ОПТИМИЗАЦИЯ: отключаем синхронизацию для скорости
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = MEMORY")

            cursor.execute("BEGIN TRANSACTION")

            batch_size = 20000
            items = list(local_sizes.items())
            total = len(items)

            for i in range(0, total, batch_size):
                batch = items[i:i + batch_size]

                values = []
                for path, size in batch:
                    count = local_counts.get(path, 0)
                    key = self.get_folder_key(path)
                    values.append((path, size, count, time.time(), key))

                cursor.executemany('''
                    INSERT OR REPLACE INTO local_sizes 
                    (path, local_size, local_count, timestamp, path_normalized)
                    VALUES (?, ?, ?, ?, ?)
                ''', values)

                processed = min(i + batch_size, total)
                if processed % 100000 == 0 or processed >= total:
                    progress = int(processed / total * 100)
                    debug_print(f"  Сохранено {processed}/{total} ({progress}%)")

            conn.commit()
            conn.close()

            elapsed = time.time() - start_time
            debug_print(f"✅ Сохранено {len(local_sizes)} локальных размеров за {elapsed:.1f} сек")

        except Exception as e:
            debug_print(f"❌ Ошибка сохранения локальных размеров: {e}")
            try:
                conn.rollback()
            except:
                pass

    def scan_all_folders_one_pass(self, root_path, progress_callback=None, scanning_flag=None):
        """
        ОДИН ПРОХОД scandir по всему дереву папок
        progress_callback(total_progress, stage, stage_progress, message)
        """
        debug_print(f"📂 Один проход scandir: {root_path}")
        start_time = time.time()

        system_folders = {
            'Documents and Settings', 'System Volume Information',
            '$Recycle.Bin', 'Config.Msi', 'Windows', 'ProgramData',
            'System32', 'SysWOW64', 'Recovery', 'Boot', 'PerfLogs'
        }

        import sys

        # ========== ЭТАП 1: Сбор списка папок (5%) ==========
        if progress_callback:
            progress_callback(0, "Сбор списка папок", 0, "Начинаем сбор...")

        if scanning_flag is not None and not scanning_flag():
            return {}, {}

        all_paths = self.get_cached_folder_list(root_path)

        if all_paths is not None:
            debug_print(f"📂 Загружено {len(all_paths)} папок из кэша списка")
            if progress_callback:
                progress_callback(5, "Сбор списка папок", 100, f"Загружено {len(all_paths)} папок (кэш)")
        else:
            debug_print("📂 Сбор списка папок (кэш отсутствует)...")
            all_paths = []
            stack = [root_path]
            last_update = time.time()

            while stack:
                if scanning_flag is not None and not scanning_flag():
                    return {}, {}

                path = stack.pop()
                all_paths.append(path)
                try:
                    with os.scandir(path) as entries:
                        for entry in entries:
                            if entry.is_dir():
                                folder_name = entry.name
                                if folder_name not in system_folders:
                                    stack.append(entry.path)
                except (PermissionError, OSError):
                    continue

                current_time = time.time()
                if current_time - last_update >= 0.5:
                    stage_progress = min(100, int(len(all_paths) / 1000))
                    total_progress = stage_progress * 0.05

                    if progress_callback:
                        progress_callback(total_progress, "Сбор списка папок", stage_progress,
                                          f"Найдено {len(all_paths)} папок")

                    sys.stdout.write(f"\r📊 Сбор списка папок... {len(all_paths)}")
                    sys.stdout.flush()
                    last_update = current_time

            sys.stdout.write(f"\r📊 Сбор списка папок... {len(all_paths)} ✅\n")
            sys.stdout.flush()

            self.save_folder_list(root_path, all_paths)
            if progress_callback:
                progress_callback(5, "Сбор списка папок", 100, f"Собрано {len(all_paths)} папок")

        total_folders = len(all_paths)
        debug_print(f"  Всего папок: {total_folders}")

        # ========== ЭТАП 2: Локальные размеры (45%) ==========
        if progress_callback:
            progress_callback(5, "Сбор локальных размеров", 0, "Начинаем сбор...")

        if scanning_flag is not None and not scanning_flag():
            return {}, {}

        local_sizes = {}
        local_counts = {}

        cached_local = self.get_cached_local_sizes(root_path)

        if cached_local is not None and len(cached_local) == total_folders:
            for path, (size, count) in cached_local.items():
                local_sizes[path] = size
                local_counts[path] = count
            debug_print(f"📂 Загружено {len(local_sizes)} локальных размеров из кэша")
            if progress_callback:
                progress_callback(50, "Сбор локальных размеров", 100, f"Загружено {len(local_sizes)} (кэш)")
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def get_local_size(folder_path):
                if scanning_flag is not None and not scanning_flag():
                    return folder_path, 0, 0
                try:
                    size = 0
                    count = 0
                    with os.scandir(folder_path) as entries:
                        for entry in entries:
                            if entry.is_file():
                                try:
                                    size += entry.stat().st_size
                                    count += 1
                                except:
                                    pass
                    return folder_path, size, count
                except (PermissionError, OSError):
                    return folder_path, 0, 0

            processed = 0
            total = total_folders
            last_update = time.time()

            with ThreadPoolExecutor(max_workers=min(8, os.cpu_count() or 4)) as executor:
                futures = {executor.submit(get_local_size, path): path for path in all_paths}

                for future in as_completed(futures):
                    if scanning_flag is not None and not scanning_flag():
                        executor.shutdown(wait=False, cancel_futures=True)
                        return {}, {}

                    path, size, count = future.result()
                    local_sizes[path] = size
                    local_counts[path] = count
                    processed += 1

                    current_time = time.time()
                    if current_time - last_update >= 1:
                        stage_progress = (processed / total) * 100
                        total_progress = 5 + 45 * (stage_progress / 100)  # 45% от общего

                        elapsed = current_time - start_time
                        speed = processed / elapsed if elapsed > 0 else 0
                        remaining = (total - processed) / speed if speed > 0 else 0
                        eta_str = f"{int(remaining)} сек" if remaining < 120 else f"{int(remaining / 60)} мин"

                        if progress_callback:
                            progress_callback(
                                total_progress,
                                "Сбор локальных размеров",
                                stage_progress,
                                f"{processed}/{total} | Скорость: {speed:.0f} папок/сек | Осталось: {eta_str}"
                            )

                        sys.stdout.write(
                            f"\r📊 Сбор размеров: {stage_progress:.1f}% ({processed}/{total}) | Скорость: {speed:.0f} папок/сек | Осталось: {eta_str}   ")
                        sys.stdout.flush()
                        last_update = current_time

            sys.stdout.write("\n")
            sys.stdout.flush()

            self.save_local_sizes(local_sizes, local_counts)
            if progress_callback:
                progress_callback(50, "Сбор локальных размеров", 100, f"Собрано {len(local_sizes)} папок")

        # ========== ЭТАП 3: Рекурсивные размеры (30%) ==========
        if progress_callback:
            progress_callback(50, "Вычисление рекурсивных размеров", 0, "Начинаем вычисление...")

        if scanning_flag is not None and not scanning_flag():
            return {}, {}

        sizes = {}
        counts = {}

        parent_map = {}
        for path in all_paths:
            parent = os.path.dirname(path)
            if parent not in parent_map:
                parent_map[parent] = []
            parent_map[parent].append(path)

        sorted_paths = sorted(all_paths, key=lambda x: x.count(os.sep), reverse=True)

        recalc_processed = 0
        total_recursive = len(sorted_paths)
        last_update = time.time()
        recalc_start = time.time()

        for path in sorted_paths:
            if scanning_flag is not None and not scanning_flag():
                return sizes, counts

            total_size = local_sizes.get(path, 0)
            total_count = local_counts.get(path, 0)

            for sub_path in parent_map.get(path, []):
                total_size += sizes.get(sub_path, 0)
                total_count += counts.get(sub_path, 0)

            sizes[path] = total_size
            counts[path] = total_count

            recalc_processed += 1
            current_time = time.time()
            if current_time - last_update >= 1:
                stage_progress = (recalc_processed / total_recursive) * 100
                total_progress = 50 + 30 * (stage_progress / 100)  # 30% от общего

                elapsed = current_time - recalc_start
                speed = recalc_processed / elapsed if elapsed > 0 else 0
                remaining = (total_recursive - recalc_processed) / speed if speed > 0 else 0
                eta_str = f"{int(remaining)} сек" if remaining < 120 else f"{int(remaining / 60)} мин"

                if progress_callback:
                    progress_callback(
                        total_progress,
                        "Вычисление рекурсивных размеров",
                        stage_progress,
                        f"{recalc_processed}/{total_recursive} | Осталось: {eta_str}"
                    )

                sys.stdout.write(
                    f"\r📊 Вычисление размеров: {stage_progress:.1f}% ({recalc_processed}/{total_recursive}) | Осталось: {eta_str}   ")
                sys.stdout.flush()
                last_update = current_time

        sys.stdout.write("\n")
        sys.stdout.flush()

        if progress_callback:
            progress_callback(80, "Вычисление рекурсивных размеров", 100, f"Вычислено {len(sizes)} папок")

        # ========== ЭТАП 4: Сохранение в кэш (20%) ==========
        if progress_callback:
            progress_callback(80, "Сохранение в кэш", 0, "Начинаем сохранение...")

        # Сохраняем в кэш
        cache_items = []
        for path, size in sizes.items():
            if size > 0:
                cache_items.append((path, size, counts.get(path, 0)))

        if cache_items:
            # Сохраняем с прогрессом
            self._save_cache_batch_with_progress(cache_items, progress_callback)

        if progress_callback:
            progress_callback(100, "Готово", 100, f"Завершено! {len(sizes)} папок")

        elapsed = time.time() - start_time
        debug_print(f"✅ Один проход завершён за {elapsed:.2f} сек ({len(sizes)} папок)")

        return sizes, counts

    def get_cached_size(self, folder_path):
        """Получение размера папки из кэша с использованием быстрого сканирования"""
        key = self.get_folder_key(folder_path)

        with self.lock:
            try:
                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()

                cursor.execute('''
                               SELECT total_size, file_signatures, last_modified, timestamp
                               FROM cache
                               WHERE path = ? OR path_normalized = ?
                               ''', (folder_path, key))

                row = cursor.fetchone()
                conn.close()

                if not row:
                    self.cache_miss_count += 1
                    return None

                total_size, file_signatures_json, last_modified, timestamp = row

                # Проверяем актуальность (не старше 30 дней)
                if time.time() - timestamp > 86400 * 30:
                    self.cache_miss_count += 1
                    return None

                # Быстрая проверка изменения папки
                try:
                    current_mtime = os.path.getmtime(folder_path)
                    if current_mtime > last_modified + 60:
                        self.cache_miss_count += 1
                        return None
                except:
                    pass

                self.cache_hit_count += 1
                return total_size

            except Exception as e:
                debug_print(f"Ошибка чтения кэша: {e}")
                self.cache_miss_count += 1
                return None

    def update_cache_full(self, folder_path):
        """Полное обновление кэша с использованием быстрого метода"""
        key = self.get_folder_key(folder_path)

        # Используем быстрый метод сканирования
        size, file_count = self.scan_folder_full(folder_path)

        if size == 0:
            # Пробуем os.walk если быстрый метод вернул 0
            size, file_count = self.scan_folder_full_os_walk(folder_path)

        if size == 0:
            return 0

        with self.lock:
            try:
                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()

                # Сохраняем с пустыми сигнатурами (для совместимости)
                signatures_json = '{}'

                cursor.execute('''
                    INSERT OR REPLACE INTO cache 
                    (path, total_size, file_count, last_modified, timestamp, 
                     file_signatures, path_normalized)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    folder_path,
                    size,
                    file_count,
                    time.time(),
                    time.time(),
                    signatures_json,
                    key
                ))

                conn.commit()
                conn.close()

                self.full_updates += 1

            except Exception as e:
                debug_print(f"❌ Ошибка обновления кэша: {e}")
                return 0

        return size

    def scan_folder_full_os_walk(self, folder_path):
        """Полное сканирование папки через os.walk (эталон, но медленный)"""
        total_size = 0
        file_count = 0

        system_folders = {
            'Documents and Settings', 'System Volume Information',
            '$Recycle.Bin', 'Config.Msi', 'Windows', 'ProgramData',
            'System32', 'SysWOW64', 'Recovery', 'Boot', 'PerfLogs'
        }

        try:
            for root, dirs, files in os.walk(folder_path, followlinks=False):
                dirs[:] = [d for d in dirs if d not in system_folders]
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                        file_count += 1
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass

        return total_size, file_count

    def get_folder_size_fast(self, folder_path):
        """Метод 4: os.scandir (глубина 5)"""
        try:
            total_size = 0

            def scan_dir(path, depth):
                if depth > 5:
                    return 0
                size = 0
                try:
                    with os.scandir(path) as entries:
                        for entry in entries:
                            if entry.is_file():
                                try:
                                    size += entry.stat().st_size
                                except:
                                    pass
                            elif entry.is_dir() and depth < 5:
                                size += scan_dir(entry.path, depth + 1)
                except:
                    pass
                return size

            total_size = scan_dir(folder_path, 1)

            # Логируем каждые 1000 папок
            if self.full_updates % 1000 == 0:
                debug_print(f"📊 Быстрый метод: {os.path.basename(folder_path)} = {self.format_size(total_size)}")

            return total_size
        except Exception as e:
            debug_print(f"❌ Ошибка в быстром методе: {e}")
            return 0

    def _init_database(self):
        """Инициализация SQLite базы данных"""
        try:
            # Проверяем, существует ли файл и является ли он SQLite
            if os.path.exists(self.cache_file):
                try:
                    with open(self.cache_file, 'rb') as f:
                        header = f.read(16)
                        if not header.startswith(b'SQLite format 3'):
                            debug_print(f"⚠️ Файл {self.cache_file} не является SQLite, удаляем")
                            os.remove(self.cache_file)
                            debug_print("🔄 Создаём новый файл кэша")
                except Exception as e:
                    debug_print(f"⚠️ Ошибка проверки файла: {e}, удаляем")
                    try:
                        os.remove(self.cache_file)
                    except:
                        pass

            conn = sqlite3.connect(self.cache_file, timeout=30)
            cursor = conn.cursor()

            # Таблица для кэша папок (рекурсивные размеры)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS cache
                           (
                               path
                               TEXT
                               PRIMARY
                               KEY,
                               total_size
                               INTEGER
                               DEFAULT
                               0,
                               file_count
                               INTEGER
                               DEFAULT
                               0,
                               last_modified
                               REAL
                               DEFAULT
                               0,
                               timestamp
                               REAL
                               DEFAULT
                               0,
                               file_signatures
                               TEXT
                               DEFAULT
                               '{}',
                               path_normalized
                               TEXT
                           )
                           ''')

            # Таблица для локальных размеров (только файлы в корне папки)
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS local_sizes
                           (
                               path
                               TEXT
                               PRIMARY
                               KEY,
                               local_size
                               INTEGER
                               DEFAULT
                               0,
                               local_count
                               INTEGER
                               DEFAULT
                               0,
                               timestamp
                               REAL
                               DEFAULT
                               0,
                               path_normalized
                               TEXT
                           )
                           ''')

            # Таблица для кэша списка папок
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS folder_list
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY,
                               root_path
                               TEXT,
                               folders
                               TEXT,
                               folder_count
                               INTEGER,
                               timestamp
                               REAL,
                               UNIQUE
                           (
                               root_path
                           )
                               )
                           ''')

            # Создаём индексы для быстрого поиска
            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_path_normalized
                               ON cache(path_normalized)
                           ''')

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_cache_timestamp
                               ON cache(timestamp)
                           ''')

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_local_path_normalized
                               ON local_sizes(path_normalized)
                           ''')

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_local_timestamp
                               ON local_sizes(timestamp)
                           ''')

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_folder_list_root
                               ON folder_list(root_path)
                           ''')

            conn.commit()
            conn.close()
            debug_print("✅ База данных SQLite инициализирована")

        except sqlite3.DatabaseError as e:
            debug_print(f"❌ Ошибка инициализации БД: {e}")
            # Если файл повреждён - удаляем и создаём заново
            if os.path.exists(self.cache_file):
                try:
                    os.remove(self.cache_file)
                    debug_print("🗑️ Повреждённый файл удалён")
                except:
                    pass

            # Пробуем создать заново
            try:
                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()

                cursor.execute('''
                               CREATE TABLE IF NOT EXISTS cache
                               (
                                   path
                                   TEXT
                                   PRIMARY
                                   KEY,
                                   total_size
                                   INTEGER
                                   DEFAULT
                                   0,
                                   file_count
                                   INTEGER
                                   DEFAULT
                                   0,
                                   last_modified
                                   REAL
                                   DEFAULT
                                   0,
                                   timestamp
                                   REAL
                                   DEFAULT
                                   0,
                                   file_signatures
                                   TEXT
                                   DEFAULT
                                   '{}',
                                   path_normalized
                                   TEXT
                               )
                               ''')

                cursor.execute('''
                               CREATE TABLE IF NOT EXISTS local_sizes
                               (
                                   path
                                   TEXT
                                   PRIMARY
                                   KEY,
                                   local_size
                                   INTEGER
                                   DEFAULT
                                   0,
                                   local_count
                                   INTEGER
                                   DEFAULT
                                   0,
                                   timestamp
                                   REAL
                                   DEFAULT
                                   0,
                                   path_normalized
                                   TEXT
                               )
                               ''')

                cursor.execute('''
                               CREATE TABLE IF NOT EXISTS folder_list
                               (
                                   id
                                   INTEGER
                                   PRIMARY
                                   KEY,
                                   root_path
                                   TEXT,
                                   folders
                                   TEXT,
                                   folder_count
                                   INTEGER,
                                   timestamp
                                   REAL,
                                   UNIQUE
                               (
                                   root_path
                               )
                                   )
                               ''')

                cursor.execute('''
                               CREATE INDEX IF NOT EXISTS idx_path_normalized
                                   ON cache(path_normalized)
                               ''')

                cursor.execute('''
                               CREATE INDEX IF NOT EXISTS idx_cache_timestamp
                                   ON cache(timestamp)
                               ''')

                cursor.execute('''
                               CREATE INDEX IF NOT EXISTS idx_local_path_normalized
                                   ON local_sizes(path_normalized)
                               ''')

                cursor.execute('''
                               CREATE INDEX IF NOT EXISTS idx_local_timestamp
                                   ON local_sizes(timestamp)
                               ''')

                cursor.execute('''
                               CREATE INDEX IF NOT EXISTS idx_folder_list_root
                                   ON folder_list(root_path)
                               ''')

                conn.commit()
                conn.close()
                debug_print("✅ База данных SQLite создана заново")

            except Exception as e2:
                debug_print(f"❌ Не удалось создать БД: {e2}")

        except Exception as e:
            debug_print(f"❌ Ошибка инициализации БД: {e}")
            if os.path.exists(self.cache_file):
                try:
                    os.remove(self.cache_file)
                    debug_print("🗑️ Файл удалён, будет создан заново")
                except:
                    pass

    def get_folder_key(self, folder_path):
        """Получение ключа для папки (нормализованный путь)"""
        return folder_path.lower().replace('\\', '/')

    def get_folder_signatures(self, folder_path, max_depth=3):
        """Получение сигнатур всех файлов в папке (рекурсивно)"""
        signatures = {}
        total_size = 0
        file_count = 0
        last_modified = 0

        system_folders = {
            'Documents and Settings', 'System Volume Information',
            '$Recycle.Bin', 'Config.Msi', 'Windows', 'ProgramData',
            'System32', 'SysWOW64', 'Recovery', 'Boot', 'PerfLogs'
        }

        try:
            for root, dirs, files in os.walk(folder_path, followlinks=False):
                dirs[:] = [d for d in dirs if d not in system_folders]

                rel_root = os.path.relpath(root, folder_path)
                if rel_root != '.':
                    depth = rel_root.count(os.sep) + 1
                    if depth > max_depth:
                        dirs[:] = []
                        continue

                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        rel_path = os.path.relpath(file_path, folder_path)
                        stat = os.stat(file_path)

                        signatures[rel_path] = {
                            'size': stat.st_size,
                            'mtime': stat.st_mtime,
                            'ctime': stat.st_ctime
                        }
                        total_size += stat.st_size
                        file_count += 1

                        if stat.st_mtime > last_modified:
                            last_modified = stat.st_mtime

                    except (PermissionError, OSError):
                        continue

        except (PermissionError, OSError):
            pass

        return {
            'signatures': signatures,
            'total_size': total_size,
            'file_count': file_count,
            'last_modified': last_modified,
            'timestamp': time.time()
        }

    def get_folder_size_cached(self, folder_path):
        """Быстрый доступ к кэшу без повторного сканирования"""
        key = self.get_folder_key(folder_path)

        with self.lock:
            try:
                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()

                cursor.execute('''
                               SELECT total_size, timestamp
                               FROM cache
                               WHERE path = ? OR path_normalized = ?
                               ''', (folder_path, key))

                row = cursor.fetchone()
                conn.close()

                if row:
                    total_size, timestamp = row
                    if time.time() - timestamp < 86400 * 30:
                        self.cache_hit_count += 1
                        return total_size

                self.cache_miss_count += 1
                return None

            except Exception as e:
                debug_print(f"Ошибка чтения кэша: {e}")
                self.cache_miss_count += 1
                return None

    def update_cache_partial(self, folder_path):
        """Частичное обновление кэша"""
        key = self.get_folder_key(folder_path)

        with self.lock:
            try:
                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()

                cursor.execute('''
                               SELECT total_size, file_count, file_signatures, last_modified
                               FROM cache
                               WHERE path = ?
                                  OR path_normalized = ?
                               ''', (folder_path, key))

                row = cursor.fetchone()

                if not row:
                    conn.close()
                    return self.update_cache_full(folder_path)

                old_total_size, old_file_count, file_signatures_json, old_last_modified = row
                cached_signatures = json.loads(file_signatures_json) if file_signatures_json else {}

                current = self.get_folder_signatures(folder_path, max_depth=3)
                if not current:
                    conn.close()
                    return 0

                current_signatures = current.get('signatures', {})

                added_files = []
                modified_files = []
                deleted_files = []

                for file_path, sig in current_signatures.items():
                    cached_sig = cached_signatures.get(file_path)
                    if not cached_sig:
                        added_files.append(file_path)
                    elif (cached_sig.get('size') != sig.get('size') or
                          cached_sig.get('mtime') != sig.get('mtime')):
                        modified_files.append(file_path)

                for file_path in cached_signatures.keys():
                    if file_path not in current_signatures:
                        deleted_files.append(file_path)

                if not added_files and not modified_files and not deleted_files:
                    conn.close()
                    return old_total_size

                total_size = old_total_size
                file_count = old_file_count

                for file_path in deleted_files:
                    file_size = cached_signatures.get(file_path, {}).get('size', 0)
                    total_size -= file_size
                    file_count -= 1
                    del cached_signatures[file_path]

                for file_path in added_files:
                    sig = current_signatures[file_path]
                    total_size += sig['size']
                    file_count += 1
                    cached_signatures[file_path] = sig

                for file_path in modified_files:
                    old_size = cached_signatures.get(file_path, {}).get('size', 0)
                    new_size = current_signatures[file_path]['size']
                    diff = new_size - old_size
                    total_size += diff
                    cached_signatures[file_path] = current_signatures[file_path]

                signatures_json = json.dumps(cached_signatures)

                cursor.execute('''
                               UPDATE cache
                               SET total_size      = ?,
                                   file_count      = ?,
                                   last_modified   = ?,
                                   timestamp       = ?,
                                   file_signatures = ?
                               WHERE path = ?
                                  OR path_normalized = ?
                               ''', (
                                   total_size,
                                   file_count,
                                   current['last_modified'],
                                   time.time(),
                                   signatures_json,
                                   folder_path,
                                   key
                               ))

                conn.commit()
                conn.close()

                self.partial_updates += 1
                return total_size

            except Exception as e:
                debug_print(f"Ошибка частичного обновления: {e}")
                return self.update_cache_full(folder_path)

    def update_cache(self, folder_path, size):
        """Обновление кэша для папки (устаревший метод, для совместимости)"""
        return self.update_cache_full(folder_path)

    def get_folder_size_smart(self, folder_path):
        """Умное получение размера папки"""
        cached_size = self.get_cached_size(folder_path)

        if cached_size is not None:
            return cached_size

        return self.update_cache_partial(folder_path)

    def scan_folder_full(self, folder_path):
        """
        Полное сканирование папки (используется только для одиночных обновлений)
        """
        try:
            size = self.get_folder_size_fast(folder_path)
            if size > 0:
                # Убираем debug спам для маленьких папок
                # if size > 1024 * 1024:  # Только для папок > 1 МБ
                #     debug_print(f"  ✅ Быстрый метод: {self.format_size(size)}")
                return size, 0
            return self.scan_folder_full_os_walk(folder_path)
        except Exception:
            return self.scan_folder_full_os_walk(folder_path)

    def get_cached_folder_list(self, root_path):
        """Получение кэшированного списка папок"""
        try:
            conn = sqlite3.connect(self.cache_file, timeout=30)
            cursor = conn.cursor()

            cursor.execute('''
                           SELECT folders, folder_count, timestamp
                           FROM folder_list
                           WHERE root_path = ?
                           ''', (root_path,))

            row = cursor.fetchone()
            conn.close()

            if row:
                folders_json, folder_count, timestamp = row
                # Проверяем актуальность (не старше 7 дней)
                if time.time() - timestamp < 86400 * 7:
                    folders = json.loads(folders_json)
                    return folders
            return None

        except Exception as e:
            debug_print(f"Ошибка чтения кэша списка папок: {e}")
            return None

    def save_folder_list(self, root_path, folders):
        """Сохранение списка папок в кэш"""
        if not folders:
            return

        try:
            folders_json = json.dumps(folders)

            conn = sqlite3.connect(self.cache_file, timeout=30)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT OR REPLACE INTO folder_list 
                (root_path, folders, folder_count, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (root_path, folders_json, len(folders), time.time()))

            conn.commit()
            conn.close()

        except Exception as e:
            debug_print(f"Ошибка сохранения списка папок: {e}")

    def get_cache_stats(self):
        """Получение статистики кэша"""
        try:
            conn = sqlite3.connect(self.cache_file, timeout=30)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM cache")
            total_entries = cursor.fetchone()[0]

            cursor.execute("SELECT SUM(total_size) FROM cache")
            total_size = cursor.fetchone()[0] or 0

            db_size = os.path.getsize(self.cache_file) if os.path.exists(self.cache_file) else 0

            conn.close()

            total_requests = self.cache_hit_count + self.cache_miss_count
            hit_rate = (self.cache_hit_count / total_requests * 100) if total_requests > 0 else 0

            return {
                'total_entries': total_entries,
                'total_size': total_size,
                'cache_size_mb': db_size / (1024 * 1024),
                'hits': self.cache_hit_count,
                'misses': self.cache_miss_count,
                'hit_rate': hit_rate,
                'partial_updates': self.partial_updates,
                'full_updates': self.full_updates
            }

        except Exception as e:
            debug_print(f"Ошибка получения статистики: {e}")
            return {
                'total_entries': 0,
                'total_size': 0,
                'cache_size_mb': 0,
                'hits': 0,
                'misses': 0,
                'hit_rate': 0,
                'partial_updates': 0,
                'full_updates': 0
            }

    def clear_cache(self):
        """Очистка кэша"""
        with self.lock:
            try:
                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM cache")
                cursor.execute("DELETE FROM folder_list")
                conn.commit()
                conn.close()

                conn = sqlite3.connect(self.cache_file, timeout=30)
                cursor = conn.cursor()
                cursor.execute("VACUUM")
                conn.commit()
                conn.close()

                self.cache_hit_count = 0
                self.cache_miss_count = 0
                self.partial_updates = 0
                self.full_updates = 0
                debug_print("🗑️ Кэш полностью очищен")

            except Exception as e:
                debug_print(f"Ошибка очистки кэша: {e}")

    def save_cache(self):
        """Сохранение кэша (для SQLite - ничего не делаем, всё уже сохранено)"""
        debug_print("💾 SQLite кэш автоматически сохранён")

    def format_size(self, size_bytes):
        """Форматирование размера"""
        return format_size(size_bytes)

    def validate_cache(self):
        """Проверка целостности кэша"""
        debug_print("🔍 Проверка целостности кэша...")

        try:
            conn = sqlite3.connect(self.cache_file, timeout=30)
            cursor = conn.cursor()

            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()

            if result[0] != 'ok':
                debug_print(f"⚠️ БД повреждена: {result[0]}")
                conn.close()
                return 0, 0

            cursor.execute("SELECT COUNT(*), SUM(total_size) FROM cache")
            count, total_size = cursor.fetchone()
            conn.close()

            debug_print(f"✅ Проверка завершена: {count} записей, {self.format_size(total_size or 0)}")
            return count or 0, total_size or 0

        except Exception as e:
            debug_print(f"❌ Ошибка проверки кэша: {e}")
            return 0, 0
