"""Мультивыбор дисков и вкладка «🔥 Самые большие» (только топ папок)."""
import os
import sqlite3
import threading

from tkinter import *
from tkinter import ttk, messagebox

from ..utils import debug_print, format_size

WRAPPER_SHARE = 0.10


def _norm_path(p):
    try:
        return os.path.normpath(p)
    except Exception:
        return p


class DrivesTopMixin:
    """Чекбоксы дисков, топ папок, вкладка."""

    # ---------- чекбоксы дисков ----------

    def _populate_drive_checkboxes(self):
        if self.drives_frame is None:
            return
        for w in list(self.drives_frame.winfo_children()):
            w.destroy()
        self.selected_drives = {}

        saved = self.settings.get('selected_drives', []) or []
        saved_set = set(saved)

        if os.name == 'nt':
            drives = [f"{d}:\\" for d in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                      if os.path.exists(f"{d}:\\")]
        else:
            drives = [os.path.expanduser('~')]

        if not drives:
            ttk.Label(self.drives_frame, text="(диски не найдены)",
                      font=('Segoe UI', 8),
                      foreground=self.colors['text_muted']).grid(
                row=0, column=0, sticky=W)
            return

        default_on_drive = None
        if not saved_set:
            last_path = (self.settings.get('last_path', '') or '').strip()
            if last_path:
                try:
                    anchor = os.path.splitdrive(os.path.abspath(last_path))[0]
                    if anchor:
                        candidate = anchor + "\\"
                        if candidate in drives:
                            default_on_drive = candidate
                except Exception:
                    pass
            if default_on_drive is None and len(drives) == 1:
                default_on_drive = drives[0]

        PER_ROW = 4
        for idx, drv in enumerate(drives):
            if saved_set:
                default_on = drv in saved_set
            else:
                default_on = (drv == default_on_drive)

            var = BooleanVar(value=default_on)
            self.selected_drives[drv] = var
            cb = ttk.Checkbutton(self.drives_frame, text=drv, variable=var,
                                 style="Modern.TCheckbutton")
            row = idx // PER_ROW
            col = idx % PER_ROW
            cb.grid(row=row, column=col, sticky=W, padx=(0, 16), pady=(0, 2))

        for c in range(PER_ROW):
            self.drives_frame.grid_columnconfigure(c, weight=0)

    def _get_scan_roots(self):
        roots = []
        if getattr(self, 'selected_drives', None):
            for drv, var in self.selected_drives.items():
                try:
                    if var.get():
                        roots.append(drv)
                except Exception:
                    pass
        if (getattr(self, 'selected_custom_path', None)
                and self.selected_custom_path.get()):
            manual = (self.root_path.get() or '').strip()
            if manual and os.path.exists(manual) and manual not in roots:
                roots.append(manual)
        seen = set()
        out = []
        for r in roots:
            if r not in seen:
                seen.add(r)
                out.append(r)
        return out

    # ---------- загрузка из SQLite ----------

    def _load_top_from_sqlite(self):
        try:
            conn = sqlite3.connect(self.cache.cache_file, timeout=30)
            cur = conn.cursor()
            cur.execute("SELECT path, total_size, file_count FROM cache")
            rows = cur.fetchall()
            conn.close()
        except Exception as e:
            debug_print(f"_load_top_from_sqlite: ошибка чтения кэша: {e}")
            return False

        if not rows:
            return False

        known_roots = list(self.last_scan_roots or [])
        if not known_roots:
            saved = self.settings.get('last_scan_roots', []) or []
            if isinstance(saved, list):
                known_roots = [r for r in saved if isinstance(r, str)]
        known_roots = [_norm_path(r) for r in known_roots if r]

        norm_roots = []
        for r in known_roots:
            rr = r if r.endswith(os.sep) else r + os.sep
            norm_roots.append(rr.lower())

        folder_sizes = {}
        folder_counts = {}
        root_of = {}
        canon = {}

        for raw_path, size, count in rows:
            if not raw_path or not isinstance(size, int) or size <= 0:
                continue
            path = _norm_path(raw_path)
            try:
                key = os.path.normcase(path)
            except Exception:
                key = path.lower()
            prev = canon.get(key)
            if prev is not None:
                if size > folder_sizes.get(prev, 0):
                    folder_sizes[prev] = size
                    folder_counts[prev] = count or 0
                continue
            canon[key] = path
            folder_sizes[path] = size
            folder_counts[path] = count or 0

            assigned = None
            path_lower = path.lower()
            for r in norm_roots:
                if path_lower.startswith(r):
                    assigned = r.rstrip('\\/') or r
                    break
            if assigned is None:
                if os.name == 'nt':
                    drv = os.path.splitdrive(path)[0]
                    assigned = (drv + os.sep) if drv else path
                else:
                    assigned = os.sep
            root_of[path] = _norm_path(assigned)

        self._last_folder_sizes = folder_sizes
        self._last_folder_counts = folder_counts
        self._last_root_of = root_of
        debug_print(f"_load_top_from_sqlite: загружено {len(folder_sizes)} папок "
                    f"из SQLite (после дедупа)")
        return True

    # ---------- топ папок ----------

    def _compute_top_folders(self, folder_sizes, folder_counts, root_of,
                             min_depth=3, limit=1000):
        if not folder_sizes:
            return []

        sep = os.sep

        canon = {}
        for raw_p, s in folder_sizes.items():
            p = _norm_path(raw_p)
            try:
                key = os.path.normcase(p)
            except Exception:
                key = p.lower()
            prev = canon.get(key)
            if prev is None:
                canon[key] = (p, s, folder_counts.get(raw_p, 0))
            else:
                pp, ps, pc = prev
                if s > ps:
                    canon[key] = (p, s, folder_counts.get(raw_p, 0))

        child_sum = {}
        for key, (p, s, c) in canon.items():
            i = p.rfind(sep)
            if i > 0:
                parent = _norm_path(p[:i])
                pkey = os.path.normcase(parent)
                if pkey in canon:
                    child_sum[parent] = child_sum.get(parent, 0) + s

        accepted = []
        for key, (p, s, c) in canon.items():
            if s <= 0:
                continue
            root = _norm_path(root_of.get(p) or root_of.get(key) or '')
            if not root:
                continue
            if os.path.normcase(p) == os.path.normcase(root):
                continue
            if p.startswith(root):
                rel = p[len(root):].lstrip('\\/')
            else:
                rel = p
            if not rel or rel.startswith('..'):
                continue
            depth = rel.count(sep) + 1
            if depth < min_depth:
                continue
            own = s - child_sum.get(p, 0)
            if own <= s * WRAPPER_SHARE:
                continue
            accepted.append({
                'path': p,
                'name': os.path.basename(p) or p,
                'size': s,
                'size_str': format_size(s),
                'count': c,
                'depth': depth,
                'root': root,
            })

        accepted.sort(key=lambda x: x['size'], reverse=True)
        return accepted[:limit]

    def _filter_existing(self, folders):
        result = []
        removed = 0
        for e in folders:
            try:
                if os.path.isdir(e['path']):
                    result.append(e)
                else:
                    removed += 1
            except Exception:
                result.append(e)
        if removed:
            debug_print(f"_filter_existing: отброшено {removed} несуществующих папок")
        return result

    # ---------- вкладка ----------

    def create_top_tab(self, parent):
        ctrl = ttk.Frame(parent, style="Modern.TFrame")
        ctrl.pack(fill=X, pady=(0, 6))

        ttk.Label(ctrl, text="Мин. глубина:",
                  font=('Segoe UI', 9),
                  foreground=self.colors['text_secondary']).pack(
            side=LEFT, padx=(0, 6))

        self.top_depth_var = IntVar(value=self.top_folders_min_depth)
        self._top_depth_spin = ttk.Spinbox(
            ctrl, from_=1, to=20, width=4,
            textvariable=self.top_depth_var,
            style="Modern.TSpinbox",
            command=self._on_depth_changed)
        self._top_depth_spin.pack(side=LEFT, padx=(0, 10))
        # ловим ручной ввод (не только стрелки)
        self._top_depth_spin.bind("<FocusOut>", lambda e: self._on_depth_changed())
        self._top_depth_spin.bind("<Return>", lambda e: self._on_depth_changed())

        ttk.Button(ctrl, text="🔄 Пересчитать",
                   command=self._refresh_top_tabs,
                   style="Secondary.TButton").pack(side=LEFT, padx=(0, 6))

        self.top_summary_label = ttk.Label(
            ctrl, text="Пока нет данных — запустите сканирование",
            font=('Segoe UI', 9),
            foreground=self.colors['text_muted'])
        self.top_summary_label.pack(side=RIGHT)

        f_folders = ttk.LabelFrame(
            parent,
            text="📁 Топ папок (глубина ≥ N, без обёрток) — двойной клик открывает в Проводнике",
            style="Card.TLabelframe", padding=(8, 6))
        f_folders.pack(fill=BOTH, expand=True)

        f_folders.grid_rowconfigure(0, weight=1)
        f_folders.grid_columnconfigure(0, weight=1)

        cols = ("#", "📁 Имя", "📦 Размер", "🪜 Глубина", "🔗 Путь", "⚡ Источник")
        self.top_folders_tree = ttk.Treeview(
            f_folders, columns=cols, show="headings",
            style="Table.Treeview")
        for c, txt, w, anch in (
                ("#", "#", 45, CENTER),
                ("📁 Имя", "📁 Имя", 260, W),
                ("📦 Размер", "📦 Размер", 130, E),
                ("🪜 Глубина", "🪜 Глубина", 90, CENTER),
                ("🔗 Путь", "🔗 Путь", 560, W),
                ("⚡ Источник", "⚡ Источник", 120, CENTER),
        ):
            self.top_folders_tree.heading(c, text=txt, anchor=anch)
            self.top_folders_tree.column(c, width=w, anchor=anch, minwidth=50)

        v1 = ttk.Scrollbar(f_folders, orient=VERTICAL,
                           command=self.top_folders_tree.yview,
                           style="Modern.Vertical.TScrollbar")
        self.top_folders_tree.configure(yscrollcommand=v1.set)

        self.top_folders_tree.grid(row=0, column=0, sticky="nsew")
        v1.grid(row=0, column=1, sticky="ns")

        self.top_folders_tree.bind("<Double-1>", self._top_folders_double_click)
        self.top_folders_tree.bind("<Button-3>", self.show_top_context_menu)

    def _on_depth_changed(self):
        """Spinbox изменился — сохраняем в настройки и пересчитываем."""
        try:
            md = int(self.top_depth_var.get())
        except Exception:
            return
        if md < 1:
            md = 1
        if md == self.top_folders_min_depth:
            return
        self.top_folders_min_depth = md
        try:
            self.settings.set('top_folders_min_depth', md)
            debug_print(f"_on_depth_changed: top_folders_min_depth={md}")
        except Exception:
            pass
        try:
            self._refresh_top_tabs()
        except Exception:
            pass

    def _top_folders_double_click(self, event=None):
        sel = self.top_folders_tree.selection()
        if not sel:
            return "break"
        vals = self.top_folders_tree.item(sel[0], 'values')
        if vals and len(vals) >= 5:
            path = _norm_path(vals[4])
            if os.path.isdir(path):
                try:
                    self.open_folder_from_path(path)
                    self.add_log(f"📂 Открыта папка: {path}", "info")
                except Exception as e:
                    debug_print(f"_top_folders_double_click: open EXC: {e}")
            else:
                debug_print(f"_top_folders_double_click: not exist: {path!r}")
                self.add_log(f"⚠️ Папка не существует: {path}", "warning")
                messagebox.showwarning(
                    "Папка не существует",
                    "Этой папки больше нет на диске:\n\n"
                    f"{path}\n\n"
                    "Возможно, её удалили или переименовали после сканирования.\n"
                    "Нажмите «🔄 Пересчитать» — она исчезнет из списка.")
        return "break"

    def _refresh_top_tabs(self):
        try:
            md = int(self.top_depth_var.get())
            if md < 1:
                md = 1
        except Exception:
            md = self.top_folders_min_depth
        self.top_folders_min_depth = md

        if not self._last_folder_sizes:
            loaded = False
            try:
                loaded = self._load_top_from_sqlite()
            except Exception as e:
                debug_print(f"_refresh_top_tabs: ошибка загрузки из SQLite: {e}")
                loaded = False
            if loaded:
                self.add_log(
                    f"💾 Топ папок восстановлен из кэша SQLite "
                    f"({len(self._last_folder_sizes)} папок)", "cache")

        if self._last_folder_sizes:
            try:
                raw_top = self._compute_top_folders(
                    self._last_folder_sizes,
                    self._last_folder_counts,
                    self._last_root_of,
                    min_depth=md, limit=1000)
            except Exception as e:
                debug_print(f"Ошибка пересчёта топа папок: {e}")
                raw_top = []
            self.top_folders = self._filter_existing(raw_top)
        else:
            self.top_folders = []

        self.top_folders_tree.delete(*self.top_folders_tree.get_children())
        for i, e in enumerate(self.top_folders, 1):
            self.top_folders_tree.insert("", END, values=(
                i,
                f"📁 {e['name']}",
                e['size_str'],
                e['depth'],
                e['path'],
                '🔄 Сканирование',
            ))

        summary = f"Папок: {len(self.top_folders)}"
        try:
            self.top_summary_label.config(text=summary)
        except Exception:
            pass

        debug_print(f"_refresh_top_tabs: top_folders={len(self.top_folders)}")

    # ---------- контекст-меню ----------

    def show_top_context_menu(self, event):
        row = self.top_folders_tree.identify_row(event.y)
        if row and row not in self.top_folders_tree.selection():
            self.top_folders_tree.selection_set(row)

        if not self.top_folders_tree.selection():
            return
        menu = Menu(self.root, tearoff=0,
                    bg=self.colors['bg_secondary'],
                    fg=self.colors['text_primary'],
                    activebackground=self.colors['bg_selected'],
                    activeforeground=self.colors['text_light'])

        def _get_sel_path():
            sel = self.top_folders_tree.selection()
            if not sel:
                return None
            vals = self.top_folders_tree.item(sel[0], 'values')
            if vals and len(vals) >= 5:
                return _norm_path(vals[4])
            return None

        def _open_explorer():
            p = _get_sel_path()
            if not p:
                return
            if os.path.isdir(p):
                self.open_folder_from_path(p)
                self.add_log(f"📂 Открыта папка: {p}", "info")
            else:
                self.add_log(f"⚠️ Папка не существует: {p}", "warning")
                messagebox.showwarning(
                    "Папка не существует",
                    f"Этой папки больше нет на диске:\n\n{p}")

        def _navigate():
            p = _get_sel_path()
            if p and os.path.isdir(p):
                self.navigate_to_path(p)

        def _copy_path():
            p = _get_sel_path()
            if p:
                self.root.clipboard_clear()
                self.root.clipboard_append(p)
                self.add_log(f"📋 Скопирован путь: {p}", "success")

        menu.add_command(label="📂 Открыть в Проводнике", command=_open_explorer)
        menu.add_command(label="📁 Перейти в папку (в приложении)", command=_navigate)
        menu.add_separator()
        menu.add_command(label="📋 Копировать путь", command=_copy_path)
        menu.post(event.x_root, event.y_root)

    # ---------- прочее ----------

    def _open_from_tree(self, tree):
        sel = tree.selection()
        if not sel:
            return
        vals = tree.item(sel[0], 'values')
        if vals and len(vals) >= 5:
            p = _norm_path(vals[4])
            if os.path.isdir(p):
                self.open_folder_from_path(p)

    def go_to_scan_root(self):
        if not self.last_scan_root_subfolders:
            self.add_log("⚠️ Нет результатов последнего сканирования",
                         "warning")
            return
        self.current_nav_path = self.last_scan_root or " (мультикорень) "
        try:
            self.path_label.config(
                text=f"📁 Результаты сканирования "
                     f"({len(self.last_scan_roots)} корн.)")
        except Exception:
            pass
        self._display_folder_items(self.last_scan_root_subfolders,
                                   "📊 Результаты сканирования")