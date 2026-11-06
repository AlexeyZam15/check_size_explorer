"""Вкладка «Логи» + add_log/process/display/filter."""
import queue
from datetime import datetime

from tkinter import *
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


class LogsTabMixin:
    """Логи и вкладка логов."""

    def create_logs_tab(self, parent):
        log_control = ttk.Frame(parent, style="Modern.TFrame")
        log_control.pack(fill=X, pady=(0, 10))

        ttk.Label(log_control, text="Фильтр:",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']).pack(side=LEFT, padx=(0, 8))

        self.log_filter = StringVar(value="Все")
        filter_combo = ttk.Combobox(log_control, textvariable=self.log_filter,
                                    values=["Все", "Инфо", "Предупреждение",
                                            "Ошибка", "Успех", "Детали", "Кэш"],
                                    style="Modern.TCombobox", width=15, state="readonly")
        filter_combo.pack(side=LEFT, padx=(0, 15))
        filter_combo.bind('<<ComboboxSelected>>', lambda e: self.apply_log_filter())

        ttk.Button(log_control, text="🧹 Очистить логи",
                   command=self.clear_logs,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 8))
        ttk.Button(log_control, text="💾 Сохранить логи",
                   command=self.save_logs,
                   style="Secondary.TButton").pack(side=LEFT)

        self.log_counter_label = ttk.Label(log_control, text="Записей: 0",
                                           font=('Segoe UI', 9),
                                           foreground=self.colors['text_secondary'])
        self.log_counter_label.pack(side=RIGHT)

        log_frame = ttk.Frame(parent, style="Modern.TFrame")
        log_frame.pack(fill=BOTH, expand=True)

        self.log_text = ScrolledText(log_frame,
                                     bg=self.colors['bg_secondary'],
                                     fg=self.colors['text_primary'],
                                     insertbackground=self.colors['accent'],
                                     font=('Consolas', 10),
                                     relief='flat', borderwidth=1, wrap=WORD,
                                     padx=12, pady=8)
        self.log_text.pack(fill=BOTH, expand=True)

        self.log_text.tag_configure("info", foreground=self.colors['text_secondary'])
        self.log_text.tag_configure("success", foreground=self.colors['success'])
        self.log_text.tag_configure("warning", foreground=self.colors['warning'])
        self.log_text.tag_configure("error", foreground=self.colors['error'])
        self.log_text.tag_configure("highlight", foreground=self.colors['accent'])
        self.log_text.tag_configure("detail", foreground=self.colors['cache_hit'])
        self.log_text.tag_configure("cache", foreground=self.colors['cache_hit'])
        self.log_text.tag_configure("timestamp", foreground=self.colors['text_muted'])

        ttk.Label(log_control, text="💡 Ctrl+C - копировать выделенный текст",
                  font=('Segoe UI', 8),
                  foreground=self.colors['text_muted']).pack(side=RIGHT, padx=(10, 0))

    def add_log(self, message, log_type="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_counter += 1
        self.log_queue.put({
            'timestamp': timestamp,
            'message': message,
            'type': log_type,
            'id': self.log_counter,
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
                "Инфо": "info", "Предупреждение": "warning",
                "Ошибка": "error", "Успех": "success",
                "Детали": "detail", "Кэш": "cache",
            }
            if log_type != type_map.get(current_filter, ""):
                return

        self.log_text.insert(END, f"[{timestamp}] ", "timestamp")
        emojis = {
            "info": "ℹ️", "success": "✅", "warning": "⚠️",
            "error": "❌", "highlight": "🔹", "detail": "📌", "cache": "💾",
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
        except Exception as e:
            self.add_log(f"❌ Ошибка сохранения: {e}", "error")