import os
import json
from .utils import debug_print


class SettingsManager:
    """Управление настройками программы"""

    def __init__(self, settings_file="settings.json"):
        self.settings_file = settings_file
        self.settings = {}
        self.default_settings = {
            'min_folder_size_mb': 100,
            'use_cache': True,
            'last_path': '',
            'batch_size': 50,
            'max_workers': 4,
            'window_geometry': '1200x850',
            'window_state': 'normal',
            'theme': 'dark',
            'log_filter': 'Все',
            'show_hidden': False,
            'sort_by': 'size',
            'sort_reverse': True
        }
        self.load_settings()

    def load_settings(self):
        """Загрузка настроек из файла"""
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Обновляем настройки, сохраняя все ключи
                    self.settings.update(self.default_settings)
                    self.settings.update(loaded)
                debug_print(f"Загружены настройки: {len(self.settings)} параметров")
            else:
                # Создаем настройки по умолчанию
                self.settings = self.default_settings.copy()
                self.save_settings()
                debug_print("Созданы настройки по умолчанию")
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            self.settings = self.default_settings.copy()

    def save_settings(self):
        """Сохранение настроек в файл"""
        try:
            # Создаем резервную копию перед сохранением
            if os.path.exists(self.settings_file):
                backup_file = self.settings_file + '.bak'
                try:
                    import shutil
                    shutil.copy2(self.settings_file, backup_file)
                except:
                    pass

            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            debug_print(f"Сохранены настройки: {len(self.settings)} параметров")
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def get(self, key, default=None):
        """Получение значения настройки"""
        return self.settings.get(key, default)

    def set(self, key, value):
        """Установка значения настройки с мгновенным сохранением"""
        if key in self.settings and self.settings[key] == value:
            return  # Значение не изменилось

        self.settings[key] = value
        self.save_settings()
        debug_print(f"Настройка обновлена: {key} = {value}")

    def update(self, **kwargs):
        """Обновление нескольких настроек"""
        changed = False
        for key, value in kwargs.items():
            if key not in self.settings or self.settings[key] != value:
                self.settings[key] = value
                changed = True

        if changed:
            self.save_settings()
            debug_print(f"Обновлено {len(kwargs)} настроек")

    def reset(self, key=None):
        """Сброс настроек к значениям по умолчанию"""
        if key is None:
            # Сброс всех настроек
            self.settings = self.default_settings.copy()
            self.save_settings()
            debug_print("Все настройки сброшены к значениям по умолчанию")
        elif key in self.default_settings:
            self.settings[key] = self.default_settings[key]
            self.save_settings()
            debug_print(f"Настройка {key} сброшена к значению по умолчанию: {self.default_settings[key]}")

    def get_all(self):
        """Получение всех настроек"""
        return self.settings.copy()

    def export_settings(self, filepath):
        """Экспорт настроек в файл"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            debug_print(f"Настройки экспортированы в {filepath}")
            return True
        except Exception as e:
            print(f"Ошибка экспорта настроек: {e}")
            return False

    def import_settings(self, filepath):
        """Импорт настроек из файла"""
        try:
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    imported = json.load(f)
                    self.settings.update(imported)
                    self.save_settings()
                debug_print(f"Настройки импортированы из {filepath}")
                return True
            else:
                print(f"Файл не найден: {filepath}")
                return False
        except Exception as e:
            print(f"Ошибка импорта настроек: {e}")
            return False

    def __str__(self):
        """Строковое представление настроек"""
        return f"SettingsManager({len(self.settings)} параметров)"

    def __repr__(self):
        """Представление настроек для отладки"""
        return f"SettingsManager(settings={self.settings})"