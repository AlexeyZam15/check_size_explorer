"""Логика сканирования: start/cancel/complete, scan_folder_optimized."""
import os
import threading
import time
import gc

from tkinter import *
from tkinter import messagebox

from ..utils import debug_print, format_size


class ScanMixin:
    """Сканирование выбранных корней (мультидиск)."""

    def start_scan(self):
        debug_print("start_scan: вызван")
        if self.scanning:
            debug_print("start_scan: уже сканируется — выходим")
            self.add_log("⚠️ Сканирование уже идёт", "warning")
            return

        roots = self._get_scan_roots()
        debug_print(f"start_scan: _get_scan_roots() -> {roots}")
        if not roots:
            self.add_log("❌ Не выбрано ни одного диска/папки", "error")
            messagebox.showerror(
                "Ошибка",
                "Не выбрано ни одного диска или папки.\n\n"
                "Разверните «⚙️ Параметры сканирования», отметьте хотя бы "
                "один диск (или включите «Или сканировать конкретную папку» "
                "и укажите путь), и нажмите «Начать сканирование» снова.")
            return

        for r in roots:
            if not os.path.exists(r):
                self.add_log(f"❌ Путь не существует: {r}", "error")
                messagebox.showerror("Ошибка", f"Путь не существует: {r}")
                return

        self.last_scan_root = ""
        self.last_scan_results = []
        self.last_scan_total_size = 0
        self.last_scan_roots = list(roots)
        try:
            self.settings.set('last_scan_roots', list(roots))
        except Exception:
            pass

        debug_print(f"start_scan: запуск скана корней: {roots}")
        self.clear_results()
        self.error_count = 0
        self.add_log("=" * 70, "info")
        self.add_log("⚡ НАЧАЛО ОПТИМИЗИРОВАННОГО СКАНИРОВАНИЯ", "highlight")
        self.add_log(f"📁 Корни ({len(roots)}): {', '.join(roots)}", "info")
        self.add_log(f"💾 Кэш: {'ВКЛЮЧЕН ⚡' if self.use_cache.get() else 'ВЫКЛЮЧЕН'}",
                     "info")
        self.add_log(f"⚡ Потоков: {self.max_workers}, Батч: {self.batch_size}",
                     "info")
        self.add_log("=" * 70, "info")

        self.scanning = True
        self.scan_start_time = time.time()
        self.scan_btn.config(state=DISABLED)
        self.cancel_btn.config(state=NORMAL)
        self.set_status("Сканирование...", "scanning")

        self.progress_var.set(0)
        self.progress_percent.config(text="0%")
        self.folder_progress_var.set(0)
        self.folder_progress_percent.config(text="0%")
        self.stage_label.config(text="🔄 Подготовка...",
                                foreground=self.colors['stage_prepare'])
        if hasattr(self, 'current_folder_label'):
            try:
                self.current_folder_label.config(text="")
            except Exception:
                pass
        if hasattr(self, 'files_count_label'):
            try:
                self.files_count_label.config(text="📄 0")
            except Exception:
                pass
        self.scan_status.config(text="⏳ Подготовка...")

        thread = threading.Thread(target=self.scan_folder_optimized, args=(roots,))
        thread.daemon = True
        thread.start()
        debug_print("start_scan: поток сканирования запущен")

    def cancel_scan(self):
        if self.scanning:
            self.scanning = False
            debug_print("Сканирование остановлено пользователем")
            self.add_log("⏹️ СКАНИРОВАНИЕ ОСТАНОВЛЕНО", "warning")
            try:
                self.cache.save_cache()
                self.add_log("💾 Кэш сохранён при остановке", "info")
            except Exception as e:
                debug_print(f"Ошибка при сохранении кэша: {e}")

            self.set_status("Остановлено", "error")
            self.scan_btn.config(state=NORMAL)
            self.cancel_btn.config(state=DISABLED)
            self.scan_status.config(text="⏹️ Остановлено")
            self.stage_label.config(text="⏹️ Остановлено",
                                    foreground=self.colors['error'])

        if hasattr(self, '_scan_thread') and self._scan_thread and self._scan_thread.is_alive():
            self._scanning_folder = False

    def scan_complete(self):
        self.scanning = False
        debug_print("Сканирование завершено")
        self.scan_btn.config(state=NORMAL)
        self.cancel_btn.config(state=DISABLED)

        if not self.tree.get_children():
            self.scan_status.config(
                text="Сканирование завершено. Папок не найдено.")

        self.refresh_cache_list()
        gc.collect()

    def scan_folder_optimized(self, roots):
        """Сканирование списка корней (один проход scandir на корень)."""
        if isinstance(roots, str):
            roots = [roots]
        debug_print(f"Начало сканирования в потоке: {roots}")
        try:
            start_time = time.time()
            use_cache = self.use_cache.get()
            n_roots = max(1, len(roots))

            self.root.after(0, lambda: self.stage_label.config(
                text="🚀 Этап 1/3: Сканирование...",
                foreground=self.colors['stage_scan']))
            self.root.after(0, lambda: self.scan_status.config(
                text="⏳ Сканирование..."))
            self.root.after(0, lambda: self.progress_var.set(0))
            self.root.after(0, lambda: self.progress_percent.config(text="0%"))

            self.add_log(
                f"📂 Один проход сканирования по {n_roots} корн(ям)...", "info")

            def is_scanning():
                return self.scanning

            folder_sizes = {}
            folder_counts = {}
            root_of = {}
            stopped = False
            error_msg = None

            for idx_root, root in enumerate(roots):
                if not is_scanning():
                    stopped = True
                    break

                base = (idx_root / n_roots) * 90.0
                span = 90.0 / n_roots

                def _scaled_progress(tp, stage, sp, msg,
                                     _base=base, _span=span, _idx=idx_root):
                    try:
                        local = float(tp) if tp is not None else 0.0
                    except Exception:
                        local = 0.0
                    local = max(0.0, min(100.0, local))
                    total_p = _base + _span * (local / 100.0)
                    label = f"[{_idx + 1}/{n_roots}] {stage}"
                    self._update_scan_progress(total_p, label, sp, msg)

                self.root.after(0, lambda r=root, i=idx_root:
                self.scan_status.config(
                    text=f"⏳ Сканирование {i + 1}/{n_roots}: {r}"))

                result = {'sizes': None, 'counts': None,
                          'error': None, 'stopped': False}

                def scan_thread(_root=root, _cb=_scaled_progress, _res=result):
                    try:
                        sizes, counts = self.cache.scan_all_folders_one_pass(
                            _root, progress_callback=_cb,
                            scanning_flag=is_scanning)
                        if not is_scanning():
                            _res['stopped'] = True
                            return
                        _res['sizes'] = sizes
                        _res['counts'] = counts
                        debug_print(
                            f"✅ scan_all_folders_one_pass({_root}) вернул "
                            f"{len(sizes) if sizes else 0} папок")
                    except Exception as e:
                        _res['error'] = str(e)
                        debug_print(f"❌ Ошибка в scan_thread({_root}): {e}")

                th = threading.Thread(target=scan_thread)
                th.daemon = True
                th.start()

                while th.is_alive():
                    self.root.update_idletasks()
                    time.sleep(0.1)

                if result['error']:
                    error_msg = result['error']
                    break
                if result['stopped'] or not self.scanning:
                    stopped = True
                    break

                part_sizes = result['sizes'] or {}
                part_counts = result['counts'] or {}
                for p, s in part_sizes.items():
                    folder_sizes[p] = s
                    root_of[p] = root
                for p, c in part_counts.items():
                    folder_counts[p] = c

            if error_msg:
                self.add_log(f"❌ Ошибка: {error_msg}", "error")
                self.root.after(0, self.scan_complete)
                return

            if stopped or not self.scanning:
                self.add_log("⏹️ Сканирование остановлено пользователем", "warning")
                try:
                    self.cache.save_cache()
                except Exception:
                    pass
                self.root.after(0, self.scan_complete)
                return

            total = len(folder_sizes)
            debug_print(f"📊 Получено {total} папок (корней: {n_roots})")

            if total == 0:
                self.add_log("⚠️ Папок не найдено", "warning")
                self.root.after(0, self.scan_complete)
                return

            self.add_log(
                f"📊 Просканировано {total} папок за "
                f"{time.time() - start_time:.1f} сек", "success")

            if use_cache and folder_sizes:
                self.root.after(0, lambda: self.stage_label.config(
                    text="💾 Сохранение в кэш...",
                    foreground=self.colors['stage_cache']))
                self.add_log(f"💾 Сохранение {len(folder_sizes)} папок в кэш...",
                             "info")

                cache_items = []
                for folder, size in folder_sizes.items():
                    if size > 0:
                        cache_items.append(
                            (folder, size, folder_counts.get(folder, 0)))
                if cache_items:
                    self.cache.save_cache_batch_with_progress(
                        cache_items, self._update_scan_progress)
                    self.add_log(f"💾 Сохранено {len(cache_items)} папок в кэш",
                                 "success")

            self.root.after(0, lambda: self.stage_label.config(
                text="📊 Формирование результатов...",
                foreground=self.colors['stage_prepare']))
            self.root.after(0, lambda: self.scan_status.config(
                text="⏳ Формирование..."))
            self.root.after(0, lambda: self.progress_var.set(90))
            self.root.after(0, lambda: self.progress_percent.config(text="90%"))

            all_results = []
            for folder, size in folder_sizes.items():
                if size > 0:
                    all_results.append({
                        'name': os.path.basename(folder),
                        'size': size,
                        'size_str': format_size(size),
                        'path': folder,
                        'source': '🔄 Сканирование',
                        'file_count': folder_counts.get(folder, 0),
                        'root': root_of.get(folder, ''),
                    })
            all_results.sort(key=lambda x: x['size'], reverse=True)
            debug_print(f"📊 Сформировано {len(all_results)} результатов")

            root_subfolders = []
            for root in roots:
                if not self.scanning:
                    break
                try:
                    with os.scandir(root) as entries:
                        for entry in entries:
                            if not self.scanning:
                                break
                            if entry.is_dir():
                                folder_name = entry.name
                                if folder_name in self.system_folders:
                                    continue
                                size = folder_sizes.get(entry.path, 0)
                                root_subfolders.append({
                                    'name': folder_name,
                                    'size': size,
                                    'size_str': format_size(size) if size > 0 else "0 Б",
                                    'path': entry.path,
                                    'source': '🔄 Сканирование' if size > 0 else '📂 Пустая',
                                    'file_count': folder_counts.get(entry.path, 0),
                                    'root': root,
                                })
                except Exception as e:
                    debug_print(f"Ошибка получения прямых подпапок {root}: {e}")
            root_subfolders.sort(key=lambda x: x['size'], reverse=True)
            if not root_subfolders:
                root_subfolders = all_results[:500]

            self._last_folder_sizes = folder_sizes
            self._last_folder_counts = folder_counts
            self._last_root_of = root_of
            self.last_scan_root = roots[0] if len(roots) == 1 else ""
            self.last_scan_roots = list(roots)
            self.last_scan_results = all_results
            self.last_scan_root_subfolders = root_subfolders
            self.last_scan_total_size = sum(r['size'] for r in all_results)
            try:
                self.settings.set('last_scan_roots', list(roots))
            except Exception:
                pass

            # Топ папок
            self.root.after(0, lambda: self.stage_label.config(
                text="🔥 Расчёт топа папок...",
                foreground=self.colors['stage_prepare']))
            try:
                self.top_folders = self._compute_top_folders(
                    folder_sizes, folder_counts, root_of,
                    min_depth=self.top_folders_min_depth, limit=1000)
                self.add_log(
                    f"🔥 Топ папок: {len(self.top_folders)} "
                    f"(глубина≥{self.top_folders_min_depth}, без обёрток)",
                    "highlight")
            except Exception as e:
                debug_print(f"Ошибка расчёта топа папок: {e}")
                self.top_folders = []

            self.root.after(0, self._refresh_top_tabs)

            self.root.after(0, lambda: self.progress_var.set(100))
            self.root.after(0, lambda: self.progress_percent.config(text="100%"))
            self.root.after(0, lambda: self.scan_status.config(text="✅ Готово!"))
            self.root.after(0, lambda: self.stage_label.config(
                text="✅ Готово!", foreground=self.colors['success']))

            elapsed_time = time.time() - start_time
            self.add_log("=" * 70, "info")
            self.add_log(f"⏱️ Завершено за {elapsed_time:.1f} сек", "success")
            self.add_log(
                f"📊 Найдено {len(all_results)} папок", "success")
            if elapsed_time > 0:
                self.add_log(
                    f"⚡ Скорость: {len(all_results) / elapsed_time:.1f} "
                    f"папок/сек", "success")
            self.add_log("=" * 70, "info")

            if root_subfolders:
                self.root.after(0, lambda: self._display_folder_items(
                    root_subfolders, "📊 Результаты сканирования"))
            else:
                top_items = all_results[:100] if all_results else []
                if top_items:
                    self.root.after(0, lambda: self._display_folder_items(
                        top_items, "📊 Топ-100 папок"))

            self.root.after(0, self._refresh_top_tabs)
            self.root.after(100, self.scan_complete)

        except Exception as e:
            debug_print(f"Ошибка: {e}")
            import traceback
            self.add_log(f"❌ Ошибка: {e}", "error")
            traceback.print_exc()
            self.root.after(0, self.scan_complete)
        finally:
            gc.collect()

    def _update_scan_progress(self, total_progress, stage, stage_progress, message):
        current_time = time.time()
        min_interval = 0.5
        if not hasattr(self, '_last_progress_update'):
            self._last_progress_update = 0
        if current_time - self._last_progress_update < min_interval:
            if stage == "Сбор списка папок":
                return
            if current_time - self._last_progress_update < 0.3:
                return
        self._last_progress_update = current_time

        self.root.after(0, lambda p=total_progress: self.progress_var.set(p))
        self.root.after(0, lambda p=total_progress:
        self.progress_percent.config(text=f"{p:.0f}%"))
        self.root.after(0, lambda p=stage_progress:
        self.folder_progress_var.set(p))
        self.root.after(0, lambda p=stage_progress:
        self.folder_progress_percent.config(text=f"{p:.0f}%"))
        self.root.after(0, lambda s=stage, m=message:
        self.scan_status.config(text=f"{s}: {m}"))
        self.root.after(0, lambda s=stage: self.stage_label.config(
            text=f"🔄 {s}", foreground=self.colors['stage_scan']))