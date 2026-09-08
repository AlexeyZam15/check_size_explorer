import os
import time
import json
import threading
import sqlite3
from .utils import debug_print, format_size, get_app_data_path


class SmartCacheManager:
    """Умный менеджер кэша с SQLite хранилищем"""

    def __init__(self, cache_file=None):
        """
        Инициализация менеджера кэша

        Args:
            cache_file (str): Путь к файлу кэша. Если None — используется путь в Documents.
        """
        # Если путь не указан — используем папку Documents
        if cache_file is None:
            app_data_dir = get_app_data_path("DiskAnalyzer")
            cache_file = os.path.join(app_data_dir, "folder_cache.db")

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
        debug_print(f"📁 Файл кэша: {self.cache_file}")

    def save_cache_batch_with_progress(self, items, progress_callback):
        """
        Сохранение в кэш с обновлением прогресса (80-95%)
        СУПЕР-ОПТИМИЗИРОВАННАЯ ВЕРСИЯ
        """
        if not items:
            return

        total = len(items)
        # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
        batch_size = 100000  # Было 10000
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite для больших объёмов ==========
            cursor.execute("PRAGMA synchronous = OFF")
            # ========== ИЗМЕНЕНИЕ: WAL вместо MEMORY для больших объёмов ==========
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            # ========== ИЗМЕНЕНИЕ: Увеличен кэш до 2 ГБ ==========
            cursor.execute("PRAGMA cache_size = -2000000")  # Было 2000000

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

                # ========== ИЗМЕНЕНИЕ: Обновляем прогресс реже ==========
                if progress_callback and (processed % 200000 == 0 or processed >= total):
                    progress_callback(
                        total_progress,
                        "Сохранение в кэш",
                        stage_progress,
                        f"{processed}/{total} ({stage_progress:.0f}%)"
                    )

                if processed % 100000 == 0 or processed >= total:
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
        Сохранение в кэш с обновлением прогресса (СУПЕР-ОПТИМИЗИРОВАННО)
        """
        if not items:
            return

        total = len(items)
        # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
        batch_size = 100000  # Было 100000 (уже было, оставляем)
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            cursor.execute("PRAGMA cache_size = -2000000")  # 2 ГБ кэша

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
                total_progress = 80 + 15 * (stage_progress / 100)

                # ========== ИЗМЕНЕНИЕ: Обновляем прогресс реже ==========
                if progress_callback and (processed % 200000 == 0 or processed >= total):
                    progress_callback(
                        total_progress,
                        "Сохранение в кэш",
                        stage_progress,
                        f"{processed}/{total} ({stage_progress:.0f}%)"
                    )

                if processed % 100000 == 0 or processed >= total:
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

    def save_cache_batch(self, items):
        """
        ПАКЕТНОЕ сохранение множества папок в кэш (СУПЕР-ОПТИМИЗИРОВАННО)
        items: список кортежей (path, total_size, file_count)
        """
        if not items:
            return

        debug_print(f"💾 Пакетное сохранение {len(items)} папок в кэш...")
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            cursor.execute("PRAGMA cache_size = -2000000")  # 2 ГБ кэша

            cursor.execute("BEGIN TRANSACTION")

            # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
            batch_size = 100000  # Было 50000
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
                if processed % 200000 == 0 or processed >= total:
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
        Сохранение локальных размеров в кэш (СУПЕР-ОПТИМИЗИРОВАННО)
        """
        if not local_sizes:
            return

        debug_print(f"💾 Сохранение {len(local_sizes)} локальных размеров в кэш...")
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            cursor.execute("PRAGMA cache_size = -2000000")  # 2 ГБ кэша

            cursor.execute("BEGIN TRANSACTION")

            # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
            batch_size = 100000  # Было 50000
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
                if processed % 200000 == 0 or processed >= total:
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

    # ===== ОСТАЛЬНЫЕ МЕТОДЫ ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ (кроме _init_database) =====

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

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_folder_list_timestamp
                               ON folder_list(timestamp)
                           ''')

            # ========== ИЗМЕНЕНИЕ: Добавлен составной индекс для быстрых запросов ==========
            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_cache_path_timestamp
                               ON cache(path_normalized, timestamp)
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

                # ... (остальной код создания таблиц такой же, как выше)

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

    def save_cache_batch_with_progress(self, items, progress_callback):
        """
        Сохранение в кэш с обновлением прогресса (80-95%)
        СУПЕР-ОПТИМИЗИРОВАННАЯ ВЕРСИЯ
        """
        if not items:
            return

        total = len(items)
        # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
        batch_size = 100000  # Было 10000
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite для больших объёмов ==========
            cursor.execute("PRAGMA synchronous = OFF")
            # ========== ИЗМЕНЕНИЕ: WAL вместо MEMORY для больших объёмов ==========
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            # ========== ИЗМЕНЕНИЕ: Увеличен кэш до 2 ГБ ==========
            cursor.execute("PRAGMA cache_size = -2000000")  # Было 2000000

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

                # ========== ИЗМЕНЕНИЕ: Обновляем прогресс реже ==========
                if progress_callback and (processed % 200000 == 0 or processed >= total):
                    progress_callback(
                        total_progress,
                        "Сохранение в кэш",
                        stage_progress,
                        f"{processed}/{total} ({stage_progress:.0f}%)"
                    )

                if processed % 100000 == 0 or processed >= total:
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
        Сохранение в кэш с обновлением прогресса (СУПЕР-ОПТИМИЗИРОВАННО)
        """
        if not items:
            return

        total = len(items)
        # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
        batch_size = 100000  # Было 100000 (уже было, оставляем)
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            cursor.execute("PRAGMA cache_size = -2000000")  # 2 ГБ кэша

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
                total_progress = 80 + 15 * (stage_progress / 100)

                # ========== ИЗМЕНЕНИЕ: Обновляем прогресс реже ==========
                if progress_callback and (processed % 200000 == 0 or processed >= total):
                    progress_callback(
                        total_progress,
                        "Сохранение в кэш",
                        stage_progress,
                        f"{processed}/{total} ({stage_progress:.0f}%)"
                    )

                if processed % 100000 == 0 or processed >= total:
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

    def save_cache_batch(self, items):
        """
        ПАКЕТНОЕ сохранение множества папок в кэш (СУПЕР-ОПТИМИЗИРОВАННО)
        items: список кортежей (path, total_size, file_count)
        """
        if not items:
            return

        debug_print(f"💾 Пакетное сохранение {len(items)} папок в кэш...")
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            cursor.execute("PRAGMA cache_size = -2000000")  # 2 ГБ кэша

            cursor.execute("BEGIN TRANSACTION")

            # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
            batch_size = 100000  # Было 50000
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
                if processed % 200000 == 0 or processed >= total:
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
        Сохранение локальных размеров в кэш (СУПЕР-ОПТИМИЗИРОВАННО)
        """
        if not local_sizes:
            return

        debug_print(f"💾 Сохранение {len(local_sizes)} локальных размеров в кэш...")
        start_time = time.time()

        try:
            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ИЗМЕНЕНИЕ: Оптимизация SQLite ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = WAL")  # Было MEMORY
            cursor.execute("PRAGMA cache_size = -2000000")  # 2 ГБ кэша

            cursor.execute("BEGIN TRANSACTION")

            # ========== ИЗМЕНЕНИЕ: Увеличен batch_size ==========
            batch_size = 100000  # Было 50000
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
                if processed % 200000 == 0 or processed >= total:
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
        ОДИН ПРОХОД scandir по всему дереву папок (СУПЕР-ОПТИМИЗИРОВАННЫЙ)
        С исправлением падения скорости на больших объёмах
        """
        import sys
        import time
        import gc
        import os
        from collections import deque

        try:
            import psutil
            PSUTIL_AVAILABLE = True
        except ImportError:
            PSUTIL_AVAILABLE = False

        debug_print(f"📂 Один проход scandir: {root_path}")
        start_time = time.time()

        def get_resource_usage():
            usage = {}
            try:
                process = psutil.Process(os.getpid())
                mem_info = process.memory_info()
                usage['rss_mb'] = mem_info.rss / (1024 * 1024)
                usage['vms_mb'] = mem_info.vms / (1024 * 1024)
                usage['cpu_percent'] = process.cpu_percent(interval=0.1)
                usage['num_threads'] = process.num_threads()
                mem = psutil.virtual_memory()
                usage['system_memory_total_mb'] = mem.total / (1024 * 1024)
                usage['system_memory_used_mb'] = mem.used / (1024 * 1024)
                usage['system_memory_percent'] = mem.percent
                disk_io = psutil.disk_io_counters()
                if disk_io:
                    usage['disk_read_mb'] = disk_io.read_bytes / (1024 * 1024)
                    usage['disk_write_mb'] = disk_io.write_bytes / (1024 * 1024)
                usage['gc_count'] = gc.get_count()
            except Exception as e:
                usage['error'] = str(e)
            return usage

        def log_resource_usage(prefix="", folder_count=0):
            if not PSUTIL_AVAILABLE:
                return
            try:
                usage = get_resource_usage()
                debug_print(f"📊 {prefix} РЕСУРСЫ на {folder_count} папок:")
                debug_print(f"  💾 Память процесса: {usage.get('rss_mb', 0):.1f} МБ (RSS)")
                debug_print(f"  💻 Системная память: {usage.get('system_memory_percent', 0):.1f}%")
                debug_print(f"  🗑️ GC: {usage.get('gc_count', (0, 0, 0))}")
            except Exception as e:
                debug_print(f"  ❌ Ошибка мониторинга: {e}")

        system_folders = (
            'Documents and Settings', 'System Volume Information',
            '$Recycle.Bin', 'Config.Msi', 'Windows', 'ProgramData',
            'System32', 'SysWOW64', 'Recovery', 'Boot', 'PerfLogs'
        )

        if PSUTIL_AVAILABLE:
            log_resource_usage("НАЧАЛЬНОЕ", 0)

        # ========== ЭТАП 1: Сбор списка папок ==========
        if progress_callback:
            progress_callback(0, "Сбор списка папок", 0, "Начинаем сбор...")

        if scanning_flag is not None and not scanning_flag():
            return {}, {}

        stack = deque([(root_path, 0)])
        all_paths = []  # список кортежей (глубина, путь)
        all_paths_simple = []  # простой список для быстрого доступа

        error_cache = set()
        last_update = time.time()
        folder_count = 0
        error_count = 0
        max_depth = 0

        system_folders_set = set(system_folders)
        is_scanning_func = scanning_flag
        progress_cb = progress_callback

        UI_UPDATE_INTERVAL = 1.0
        GC_INTERVAL = 50000

        debug_print("📂 Сбор списка папок...")

        while stack:
            if is_scanning_func is not None and not is_scanning_func():
                return {}, {}

            path, depth = stack.pop()

            if not os.path.exists(path):
                continue

            all_paths.append((depth, path))
            all_paths_simple.append(path)
            if depth > max_depth:
                max_depth = depth
            folder_count += 1

            current_time = time.time()

            if folder_count % GC_INTERVAL == 0:
                gc.collect(0)
                elapsed_total = current_time - start_time
                speed = folder_count / elapsed_total if elapsed_total > 0 else 0
                debug_print(f"📊 Статистика на {folder_count} папок:")
                debug_print(f"  ⏱️ Всего времени: {elapsed_total:.1f} сек")
                debug_print(f"  🚀 Скорость: {speed:.1f} папок/сек")
                debug_print(f"  ❌ Ошибок доступа: {error_count}")
                if PSUTIL_AVAILABLE:
                    gc_count = gc.get_count()
                    debug_print(f"  🗑️ GC: {gc_count}")

            if current_time - last_update >= UI_UPDATE_INTERVAL:
                if progress_cb:
                    progress_pct = min(5, (folder_count / 1000) * 5)
                    progress_cb(
                        progress_pct,
                        "Сбор списка папок",
                        min(100, progress_pct * 20),
                        f"Найдено {folder_count} папок"
                    )
                last_update = current_time

            try:
                with os.scandir(path) as entries:
                    for entry in entries:
                        if is_scanning_func is not None and not is_scanning_func():
                            return {}, {}
                        try:
                            if entry.is_dir():
                                name = entry.name
                                if name not in system_folders_set:
                                    stack.append((entry.path, depth + 1))
                        except OSError:
                            pass
            except (PermissionError, OSError):
                if path not in error_cache:
                    error_cache.add(path)
                    error_count += 1
                    if error_count % 50 == 0:
                        debug_print(f"  ⚠️ Ошибка доступа #{error_count}: {os.path.basename(path)}")
                continue

        sys.stdout.write(f"\r📊 Сбор списка папок... {folder_count} ✅\n")
        sys.stdout.flush()

        if progress_cb:
            progress_cb(5, "Сбор списка папок", 100, f"Собрано {folder_count} папок")

        total_folders = len(all_paths)
        debug_print(f"  Всего папок: {total_folders}")

        debug_times = {}
        debug_times['stage1_end'] = time.time()
        debug_print(f"  ⏱️ Этап 1 (сбор списка): {debug_times['stage1_end'] - start_time:.2f} сек")

        gc.collect(0)

        # ========== ЭТАП 2: Локальные размеры ==========
        if progress_cb:
            progress_cb(5, "Сбор локальных размеров", 0, "Начинаем сбор...")

        if is_scanning_func is not None and not is_scanning_func():
            return {}, {}

        local_sizes = {}
        local_counts = {}

        cached_local = self.get_cached_local_sizes(root_path)

        if cached_local is not None and len(cached_local) == total_folders:
            for path, (size, count) in cached_local.items():
                local_sizes[path] = size
                local_counts[path] = count
            debug_print(f"📂 Загружено {len(local_sizes)} локальных размеров из кэша")
            if progress_cb:
                progress_cb(50, "Сбор локальных размеров", 100, f"Загружено {len(local_sizes)} (кэш)")
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            num_workers = min(32, os.cpu_count() * 4 or 4)
            debug_print(f"⚡ Используем {num_workers} потоков")

            def get_local_size_optimized(folder_path):
                if is_scanning_func is not None and not is_scanning_func():
                    return folder_path, 0, 0
                try:
                    size = 0
                    count = 0
                    with os.scandir(folder_path) as entries:
                        for entry in entries:
                            if entry.is_file(follow_symlinks=False):
                                try:
                                    stat_info = entry.stat(follow_symlinks=False)
                                    size += stat_info.st_size
                                    count += 1
                                except (OSError, PermissionError):
                                    pass
                    return folder_path, size, count
                except (PermissionError, OSError):
                    return folder_path, 0, 0

            processed = 0
            total = total_folders
            last_update = time.time()
            stage2_start = time.time()

            debug_print(f"⚡ Запуск {num_workers} потоков для {total} папок...")

            with ThreadPoolExecutor(max_workers=num_workers) as executor:
                futures = {
                    executor.submit(get_local_size_optimized, path): path
                    for path in all_paths_simple
                }

                for future in as_completed(futures):
                    if is_scanning_func is not None and not is_scanning_func():
                        executor.shutdown(wait=False, cancel_futures=True)
                        if local_sizes:
                            self.save_local_sizes(local_sizes, local_counts)
                        return {}, {}

                    path, size, count = future.result()
                    local_sizes[path] = size
                    local_counts[path] = count
                    processed += 1

                    if processed % 50000 == 0:
                        gc.collect(0)

                    current_time = time.time()
                    if current_time - last_update >= UI_UPDATE_INTERVAL:
                        stage_progress = (processed / total) * 100
                        total_progress = 5 + 45 * (stage_progress / 100)

                        if progress_cb:
                            elapsed = current_time - stage2_start
                            speed = processed / elapsed if elapsed > 0 else 0
                            progress_cb(
                                total_progress,
                                "Сбор локальных размеров",
                                stage_progress,
                                f"{processed}/{total} | {speed:.0f} папок/сек"
                            )

                        sys.stdout.write(f"\r📊 Сбор размеров: {stage_progress:.1f}% ({processed}/{total})")
                        sys.stdout.flush()
                        last_update = current_time

            sys.stdout.write("\n")
            sys.stdout.flush()

            self.save_local_sizes(local_sizes, local_counts)
            if progress_cb:
                progress_cb(50, "Сбор локальных размеров", 100, f"Собрано {len(local_sizes)} папок")

        debug_times['stage2_end'] = time.time()
        debug_print(f"  ⏱️ Этап 2 (локальные размеры): {debug_times['stage2_end'] - debug_times['stage1_end']:.2f} сек")

        # ========== ОСВОБОЖДАЕМ ПАМЯТЬ ==========
        all_paths_simple = None
        gc.collect(0)

        # ========== ЭТАП 3: Рекурсивные размеры (ОБРАТНЫЙ ПРОХОД) ==========
        if progress_cb:
            progress_cb(50, "Вычисление рекурсивных размеров", 0, "Начинаем вычисление...")

        if is_scanning_func is not None and not is_scanning_func():
            return {}, {}

        debug_print("🔄 Сортировка папок по глубине...")
        sort_start = time.time()

        # ========== ИСПРАВЛЕНИЕ: Сортируем по глубине (убывание) ==========
        sorted_paths = sorted(all_paths, key=lambda x: x[0], reverse=True)

        debug_print(f"  ⏱️ Сортировка: {time.time() - sort_start:.2f} сек")

        # ========== ИСПРАВЛЕНИЕ: Инициализация размеров ==========
        sizes = {}
        counts = {}

        # ========== ИСПРАВЛЕНИЕ: Копируем локальные размеры ==========
        for depth, path in all_paths:
            sizes[path] = local_sizes.get(path, 0)
            counts[path] = local_counts.get(path, 0)

        # ========== ИСПРАВЛЕНИЕ: Обратный проход ==========
        debug_print("🔄 Обратный проход для рекурсивных размеров...")
        recalc_start = time.time()

        processed = 0
        total_recursive = len(sorted_paths)
        last_update = time.time()

        for depth, path in sorted_paths:
            if is_scanning_func is not None and not is_scanning_func():
                return sizes, counts

            # ========== ИСПРАВЛЕНИЕ: Для корневых папок пропускаем ==========
            if depth == 0:
                processed += 1
                continue

            parent = os.path.dirname(path)

            # ========== ИСПРАВЛЕНИЕ: Добавляем размер текущей папки к родителю ==========
            if parent in sizes:
                sizes[parent] = sizes.get(parent, 0) + sizes.get(path, 0)
                counts[parent] = counts.get(parent, 0) + counts.get(path, 0)

            processed += 1

            if processed % 50000 == 0:
                gc.collect(0)

            current_time = time.time()
            if current_time - last_update >= UI_UPDATE_INTERVAL:
                stage_progress = (processed / total_recursive) * 100
                total_progress = 50 + 30 * (stage_progress / 100)

                if progress_cb:
                    elapsed = current_time - recalc_start
                    speed = processed / elapsed if elapsed > 0 else 0
                    remaining = (total_recursive - processed) / speed if speed > 0 else 0
                    eta_str = f"{int(remaining)} сек" if remaining < 120 else f"{int(remaining / 60)} мин"
                    progress_cb(
                        total_progress,
                        "Вычисление рекурсивных размеров",
                        stage_progress,
                        f"{processed}/{total_recursive} | Осталось: {eta_str}"
                    )

                sys.stdout.write(f"\r📊 Вычисление размеров: {stage_progress:.1f}% ({processed}/{total_recursive})")
                sys.stdout.flush()
                last_update = current_time

        sys.stdout.write("\n")
        sys.stdout.flush()

        if progress_cb:
            progress_cb(80, "Вычисление рекурсивных размеров", 100, f"Вычислено {len(sizes)} папок")

        debug_times['stage3_end'] = time.time()
        debug_print(
            f"  ⏱️ Этап 3 (рекурсивные размеры): {debug_times['stage3_end'] - debug_times['stage2_end']:.2f} сек")

        gc.collect(0)

        # ========== ЭТАП 4: Сохранение в кэш ==========
        if progress_cb:
            progress_cb(80, "Сохранение в кэш", 0, "Начинаем сохранение...")

        cache_items = []
        for path, size in sizes.items():
            if size > 0:
                cache_items.append((path, size, counts.get(path, 0)))

        if cache_items:
            self._save_cache_batch_with_progress(cache_items, progress_cb)

        if progress_cb:
            progress_cb(100, "Готово", 100, f"Завершено! {len(sizes)} папок")

        elapsed = time.time() - start_time

        if PSUTIL_AVAILABLE:
            log_resource_usage("ИТОГОВОЕ", len(sizes))

        debug_print(f"\n📊 ИТОГОВАЯ СТАТИСТИКА СКАНИРОВАНИЯ:")
        debug_print(f"  📁 Папок обработано: {len(sizes)}")
        debug_print(f"  ⏱️ Общее время: {elapsed:.2f} сек")
        if elapsed > 0:
            debug_print(f"  🚀 Средняя скорость: {len(sizes) / elapsed:.1f} папок/сек")
        debug_print(f"  ⏱️ Этап 1 (сбор списка): {debug_times.get('stage1_end', 0) - start_time:.2f} сек")
        debug_print(
            f"  ⏱️ Этап 2 (локальные размеры): {debug_times.get('stage2_end', 0) - debug_times.get('stage1_end', 0):.2f} сек")
        debug_print(
            f"  ⏱️ Этап 3 (рекурсивные размеры): {debug_times.get('stage3_end', 0) - debug_times.get('stage2_end', 0):.2f} сек")
        debug_print(f"  ⏱️ Максимальная глубина: {max_depth}")

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

            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_folder_list_timestamp
                               ON folder_list(timestamp)
                           ''')

            # ========== ИЗМЕНЕНИЕ: Добавлен составной индекс для быстрых запросов ==========
            cursor.execute('''
                           CREATE INDEX IF NOT EXISTS idx_cache_path_timestamp
                               ON cache(path_normalized, timestamp)
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

                # ... (остальной код создания таблиц такой же, как выше)

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
        """Получение кэшированного списка папок (оптимизировано)"""
        try:
            # ========== ОПТИМИЗАЦИЯ: Используем параметры для ускорения ==========
            conn = sqlite3.connect(self.cache_file, timeout=30)
            conn.row_factory = sqlite3.Row  # Ускоряет доступ к колонкам
            cursor = conn.cursor()

            cursor.execute('''
                           SELECT folders, folder_count, timestamp
                           FROM folder_list
                           WHERE root_path = ?
                           ''', (root_path,))

            row = cursor.fetchone()
            conn.close()

            if row:
                folders_json = row['folders']
                folder_count = row['folder_count']
                timestamp = row['timestamp']
                # Проверяем актуальность (не старше 7 дней)
                if time.time() - timestamp < 86400 * 7:
                    # ========== ОПТИМИЗАЦИЯ: Используем быстрый парсер ==========
                    import json
                    folders = json.loads(folders_json)
                    # Проверяем, что количество совпадает
                    if len(folders) == folder_count:
                        return folders
                    else:
                        debug_print(f"⚠️ Количество папок в кэше не совпадает: {len(folders)} vs {folder_count}")
                        return None
            return None

        except Exception as e:
            debug_print(f"Ошибка чтения кэша списка папок: {e}")
            return None

    def save_folder_list(self, root_path, folders):
        """Сохранение списка папок в кэш (оптимизировано)"""
        if not folders:
            debug_print("⚠️ Список папок пуст, сохранение пропущено")
            return

        try:
            import json
            import time

            # ========== ОПТИМИЗАЦИЯ: Используем сжатый JSON ==========
            folders_json = json.dumps(folders, separators=(',', ':'))

            conn = sqlite3.connect(self.cache_file, timeout=60)
            cursor = conn.cursor()

            # ========== ОПТИМИЗАЦИЯ: Включаем быстрый режим ==========
            cursor.execute("PRAGMA synchronous = OFF")
            cursor.execute("PRAGMA journal_mode = MEMORY")

            cursor.execute('''
                INSERT OR REPLACE INTO folder_list 
                (root_path, folders, folder_count, timestamp)
                VALUES (?, ?, ?, ?)
            ''', (root_path, folders_json, len(folders), time.time()))

            conn.commit()
            conn.close()

            # ========== ОПТИМИЗАЦИЯ: Логируем только при больших сохранениях ==========
            if len(folders) > 10000:
                debug_print(f"💾 Сохранено {len(folders)} папок в кэш списка для {root_path}")

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
