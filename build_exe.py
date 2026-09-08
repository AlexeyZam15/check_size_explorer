"""
Сборка DiskAnalyzer в .exe (оптимизированная)
Запуск: python build_exe.py
"""

import PyInstaller.__main__
import os
import sys
import shutil
import warnings
from pathlib import Path

# ============================================================
# ПОДАВЛЕНИЕ ПРЕДУПРЕЖДЕНИЙ
# ============================================================
warnings.filterwarnings('ignore', category=DeprecationWarning)
warnings.filterwarnings('ignore', category=UserWarning)
os.environ['PYTHONWARNINGS'] = 'ignore'

# ============================================================
# НАСТРОЙКИ
# ============================================================
APP_NAME = "DiskAnalyzer"
APP_ICON = "icon.ico"
OUTPUT_DIR = "dist"
BUILD_DIR = "build"
CLEAN_BEFORE_BUILD = True
USE_UPX = False

EXCLUDED_MODULES = [
    'PyQt5', 'PySide2', 'PySide6', 'PyQt6',
    'matplotlib', 'mpl_toolkits',
    'django', 'flask', 'fastapi',
    'tensorflow', 'keras', 'theano',
    'pandas', 'sklearn', 'scikit-learn',
    'jupyter', 'notebook', 'ipykernel',
    'cryptography', 'openssl',
    'torch', 'torchvision',
    'easyocr',
    'opencv-python', 'cv2',
    'playwright',
    'dxcam',
    'keyboard',
]


def clean_old_build():
    """Удаляет старые папки сборки"""
    if CLEAN_BEFORE_BUILD:
        for folder in [OUTPUT_DIR, BUILD_DIR]:
            if os.path.exists(folder):
                try:
                    shutil.rmtree(folder)
                    print(f"🗑️ Удалена папка: {folder}")
                except Exception as e:
                    print(f"⚠️ Не удалось удалить {folder}: {e}")


def get_version():
    try:
        init_file = Path("src/__init__.py")
        if init_file.exists():
            with open(init_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if '__version__' in line and '=' in line:
                        version = line.split('=')[-1].strip().strip('"\'')
                        return version
        main_file = Path("main.py")
        if main_file.exists():
            with open(main_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if 'v' in line and 'версия' in line.lower():
                        import re
                        match = re.search(r'v(\d+\.\d+)', line)
                        if match:
                            return match.group(1)
    except:
        pass
    return "5.1"


def build_exe():
    """Запускает сборку через PyInstaller"""
    print("=" * 60)
    print(f"🚀 СБОРКА {APP_NAME}")
    print("=" * 60)

    version = get_version()
    print(f"📦 Версия: {version}")
    print(f"📁 Выходная папка: {OUTPUT_DIR}")
    print("📝 DEBUG-лог будет писаться в debug.log (всегда активен)")
    print("=" * 60)

    args = [
        'main.py',
        f'--name={APP_NAME}',
        '--noconsole',
        '--noconfirm',
        f'--distpath={OUTPUT_DIR}',
        f'--workpath={BUILD_DIR}',
    ]

    args.extend([
        '--noupx',
        '--strip',
        '--log-level=ERROR',
    ])

    for module in EXCLUDED_MODULES:
        args.append(f'--exclude-module={module}')

    args.extend([
        '--add-data=src;src',
    ])

    args.extend([
        '--hidden-import=tkinter',
        '--hidden-import=tkinter.ttk',
        '--hidden-import=tkinter.scrolledtext',
        '--hidden-import=sqlite3',
        '--hidden-import=threading',
        '--hidden-import=queue',
        '--hidden-import=time',
        '--hidden-import=json',
        '--hidden-import=traceback',
        '--hidden-import=re',
        '--hidden-import=datetime',
        '--hidden-import=pathlib',
        '--hidden-import=shutil',
        '--hidden-import=gc',
        '--hidden-import=concurrent',
        '--hidden-import=concurrent.futures',
        '--hidden-import=psutil',
        '--hidden-import=src',
        '--hidden-import=src.cache_manager',
        '--hidden-import=src.settings_manager',
        '--hidden-import=src.gui',
        '--hidden-import=src.utils',
    ])

    args.extend([
        '--collect-all=psutil',
    ])

    if os.path.exists(APP_ICON):
        args.append(f'--icon={APP_ICON}')
        print(f"✅ Иконка: {APP_ICON}")
    else:
        print(f"⚠️ Иконка не найдена: {APP_ICON}")

    print("\n⏳ Начинается сборка...")
    print("=" * 60 + "\n")

    try:
        import time
        start_time = time.time()
        PyInstaller.__main__.run(args)
        elapsed = time.time() - start_time
        print(f"\n⏱️ Время сборки: {elapsed:.0f} секунд ({elapsed / 60:.1f} минут)")
        print("\n" + "=" * 60)
        print("✅ СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
        print(f"📁 Готовый .exe: {OUTPUT_DIR}\\{APP_NAME}\\{APP_NAME}.exe")
        print("📝 DEBUG-лог: {OUTPUT_DIR}\\{APP_NAME}\\debug.log (создаётся при запуске)")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ ОШИБКА СБОРКИ: {e}")
        sys.exit(1)


def copy_additional_files():
    """Копирует дополнительные файлы (только иконку)"""
    output_app_dir = Path(OUTPUT_DIR) / APP_NAME

    if os.path.exists(APP_ICON):
        try:
            shutil.copy(APP_ICON, output_app_dir / APP_ICON)
            print(f"✅ Иконка скопирована в {output_app_dir}")
        except Exception as e:
            print(f"⚠️ Не удалось скопировать иконку: {e}")


def show_size_info():
    """Показывает информацию о размере собранного приложения"""
    app_dir = Path(OUTPUT_DIR) / APP_NAME
    exe_path = app_dir / f"{APP_NAME}.exe"

    if exe_path.exists():
        size_mb = exe_path.stat().st_size / (1024 * 1024)
        print(f"\n📊 Размер .exe: {size_mb:.2f} MB")

        if app_dir.exists():
            total_size = 0
            file_count = 0
            for item in app_dir.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size
                    file_count += 1
            total_mb = total_size / (1024 * 1024)
            print(f"📊 Общий размер папки: {total_mb:.2f} MB ({file_count} файлов)")


def create_launcher_bat():
    """Создаёт простой .bat файл для запуска (без DEBUG-режима)"""
    output_app_dir = Path(OUTPUT_DIR) / APP_NAME
    exe_name = f"{APP_NAME}.exe"

    bat_content = f'''@echo off
chcp 65001 > nul
start "" "%~dp0{exe_name}"
'''

    bat_path = output_app_dir / f"Запустить_{APP_NAME}.bat"
    try:
        with open(bat_path, 'w', encoding='utf-8') as f:
            f.write(bat_content)
        print(f"✅ Создан .bat файл: {bat_path}")
    except Exception as e:
        print(f"⚠️ Не удалось создать .bat файл: {e}")


if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
║   🛠️  СБОРЩИК DISK ANALYZER                            ║
║   Оптимизированная версия                               ║
╚══════════════════════════════════════════════════════════╝
""")

    clean_old_build()
    build_exe()
    copy_additional_files()
    show_size_info()
    create_launcher_bat()

    print("\n" + "=" * 60)
    print("🎉 ГОТОВО!")
    print(f"📁 Папка с программой: {OUTPUT_DIR}\\{APP_NAME}\\")
    print(f"▶️  Запуск: {APP_NAME}.exe")
    print(f"📝 DEBUG-лог: debug.log (создаётся автоматически при запуске)")
    print("=" * 60)
    print("\n📌 ВСЕ DEBUG-СООБЩЕНИЯ ПИШУТСЯ В ФАЙЛ:")
    print(f"   {OUTPUT_DIR}\\{APP_NAME}\\debug.log")
    print("   Работает всегда, без флагов и переключений")
    print("=" * 60)
