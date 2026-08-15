# main.py
import sys
import os
import traceback

# Добавляем src в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui import ProfessionalDiskAnalyzer
from src.utils import debug_print


def main():
    print("=" * 60)
    print("DISK ANALYZER PRO v5.1 - Частичное обновление кэша")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"OS: {sys.platform}")
    print(f"CPU cores: {os.cpu_count()}")
    print("=" * 60)
    sys.stdout.flush()

    try:
        from tkinter import Tk
        root = Tk()
        root.configure(bg='#0a0e17')

        try:
            root.iconbitmap(default='icon.ico')
        except:
            pass

        app = ProfessionalDiskAnalyzer(root)
        print("Главное окно создано. Запуск основного цикла...")
        sys.stdout.flush()

        # Привязываем закрытие
        root.protocol("WM_DELETE_WINDOW", app.on_closing)

        root.mainloop()

    except KeyboardInterrupt:
        print("\nПрограмма завершена пользователем (Ctrl+C)")
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        traceback.print_exc()
    finally:
        print("Программа завершена")


if __name__ == "__main__":
    main()