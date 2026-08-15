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