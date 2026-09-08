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


def debug_print(*args, **kwargs):
    """Вывод отладочной информации в терминал"""
    if DEBUG:
        print("[DEBUG]", *args, **kwargs)
        sys.stdout.flush()


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
            debug_print(f"📁 Создана папка данных: {app_data_path}")
        except Exception as e:
            debug_print(f"❌ Ошибка создания папки данных: {e}")
            # В случае ошибки используем папку с программой
            app_data_path = os.path.dirname(os.path.abspath(__file__))

    debug_print(f"📁 Путь к данным приложения: {app_data_path}")
    return app_data_path
