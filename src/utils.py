import os
import sys
import time
import threading
import queue
import json
import traceback
import re
from pathlib import Path
from datetime import datetime

# Флаг для отладки
DEBUG = True

# ========== Глобальные переменные для лог-файла ==========
_DEBUG_LOG_FILE = None
_LOG_INITIALIZED = False


def _init_debug_log():
    """Инициализирует файл для записи debug-логов"""
    global _DEBUG_LOG_FILE, _LOG_INITIALIZED  # <-- ДОБАВЛЕНО

    if _LOG_INITIALIZED:
        return

    try:
        # Получаем папку для данных приложения
        app_data_path = get_app_data_path("DiskAnalyzer")
        log_file_path = os.path.join(app_data_path, "debug.log")

        # Создаём файл и записываем заголовок
        with open(log_file_path, 'w', encoding='utf-8') as f:
            f.write("=" * 70 + "\n")
            f.write(f"=== DEBUG LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            f.write(f"=== PID: {os.getpid()} ===\n")
            f.write(f"=== NEW SESSION (overwrite mode) ===\n")
            f.write("=" * 70 + "\n")

        _DEBUG_LOG_FILE = log_file_path
        _LOG_INITIALIZED = True

        # Пробуем вывести путь к логу в консоль
        try:
            print(f"📝 Debug log: {log_file_path}")
            if sys.stdout:
                sys.stdout.flush()
        except:
            pass

    except Exception as e:
        # Если не удалось создать лог-файл - используем fallback
        try:
            fallback_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")
            with open(fallback_path, 'w', encoding='utf-8') as f:
                f.write(f"=== FALLBACK LOG - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")
            _DEBUG_LOG_FILE = fallback_path
            _LOG_INITIALIZED = True
        except:
            _DEBUG_LOG_FILE = None
            _LOG_INITIALIZED = True


def debug_print(*args, **kwargs):
    """
    Вывод отладочной информации в терминал И в файл debug.log

    Лог-файл сохраняется в: Documents/DiskAnalyzer/debug.log
    """
    global _LOG_INITIALIZED, _DEBUG_LOG_FILE  # <-- ДОБАВЛЕНО

    if not DEBUG:
        return

    # Инициализируем лог-файл при первом вызове
    if not _LOG_INITIALIZED:
        try:
            _init_debug_log()
        except Exception:
            # Если не удалось инициализировать - просто выводим в консоль
            _LOG_INITIALIZED = True
            _DEBUG_LOG_FILE = None

    # Формируем сообщение
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    message_parts = []
    for arg in args:
        if isinstance(arg, str):
            message_parts.append(arg)
        else:
            try:
                message_parts.append(repr(arg))
            except Exception:
                message_parts.append(str(arg))
    message = " ".join(message_parts)

    full_message = f"[{timestamp}] {message}"

    # ========== 1. Вывод в консоль (если доступна) ==========
    try:
        print("[DEBUG]", full_message)
        if sys.stdout is not None:
            sys.stdout.flush()
    except Exception:
        # Игнорируем ошибки вывода в консоль
        pass

    # ========== 2. Запись в файл ==========
    if _DEBUG_LOG_FILE is not None:
        try:
            with open(_DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(full_message + "\n")
        except Exception:
            # Если не удалось записать в файл - игнорируем
            pass


def debug_print_raw(message):
    """
    Печать сырого сообщения без форматирования (для отладки)
    """
    global _LOG_INITIALIZED, _DEBUG_LOG_FILE  # <-- ДОБАВЛЕНО

    if not DEBUG:
        return

    if not _LOG_INITIALIZED:
        try:
            _init_debug_log()
        except Exception:
            _LOG_INITIALIZED = True
            _DEBUG_LOG_FILE = None

    # В консоль
    try:
        print(message)
        if sys.stdout:
            sys.stdout.flush()
    except:
        pass

    # В файл
    if _DEBUG_LOG_FILE is not None:
        try:
            with open(_DEBUG_LOG_FILE, 'a', encoding='utf-8') as f:
                f.write(message + "\n")
        except:
            pass


def format_size(size_bytes):
    """Форматирование размера"""
    for unit in ['Б', 'КБ', 'МБ', 'ГБ', 'ТБ']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} ПБ"


def get_app_data_path(subfolder="DiskAnalyzer"):
    """
    Возвращает путь к папке для хранения данных приложения в Documents.
    Создаёт папку, если её нет.

    Args:
        subfolder (str): Имя подпапки внутри Documents

    Returns:
        str: Полный путь к папке данных приложения
    """
    # Получаем путь к папке Documents пользователя
    if os.name == 'nt':  # Windows
        # Используем USERPROFILE для Windows
        user_profile = os.environ.get('USERPROFILE', '')
        if user_profile:
            documents = os.path.join(user_profile, 'Documents')
        else:
            # Запасной вариант
            documents = os.path.expanduser('~/Documents')
    else:  # Linux / Mac
        documents = os.path.expanduser('~/Documents')

    # Создаём полный путь к папке данных приложения
    app_data_path = os.path.join(documents, subfolder)

    # Создаём папку, если её нет
    if not os.path.exists(app_data_path):
        try:
            os.makedirs(app_data_path, exist_ok=True)
            # Используем debug_print, но он уже будет использовать get_app_data_path
            # Поэтому пишем напрямую в консоль
            try:
                print(f"📁 Создана папка данных: {app_data_path}")
                if sys.stdout:
                    sys.stdout.flush()
            except:
                pass
        except Exception as e:
            try:
                print(f"❌ Ошибка создания папки данных: {e}")
                if sys.stdout:
                    sys.stdout.flush()
            except:
                pass
            # В случае ошибки используем папку с программой
            app_data_path = os.path.dirname(os.path.abspath(__file__))

    return app_data_path


def get_debug_log_path():
    """Возвращает путь к файлу debug.log"""
    global _LOG_INITIALIZED  # <-- ДОБАВЛЕНО

    if not _LOG_INITIALIZED:
        try:
            _init_debug_log()
        except Exception:
            return None
    return _DEBUG_LOG_FILE
