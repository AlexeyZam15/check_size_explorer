"""
Диагностика размеров/положения виджетов интерфейса.

Запуск:
    python diag_layout.py                # сводка (скрытое окно, reqW/reqH)
    python diag_layout.py --show         # показать окно на 1.5с и снять реальные размеры
    python diag_layout.py --dump out.txt # записать в файл
    python diag_layout.py --depth 4
"""
import os
import sys
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tkinter import Tk

from src.gui import ProfessionalDiskAnalyzer

KEY_WIDGETS = [
    ('root', None),
    ('tree', 'tree'),
    ('log_text', 'log_text'),
    ('cache_tree', 'cache_tree'),
    ('top_folders_tree', 'top_folders_tree'),
    ('top_files_tree', 'top_files_tree'),
    ('drives_frame', 'drives_frame'),
    ('path_entry', 'path_entry'),
    ('progress_bar', 'progress_bar'),
    ('folder_progress_bar', 'folder_progress_bar'),
    ('stage_label', 'stage_label'),
    ('scan_status', 'scan_status'),
    ('path_label', 'path_label'),
    ('back_btn', 'back_btn'),
    ('scan_btn', 'scan_btn'),
    ('cancel_btn', 'cancel_btn'),
    ('control_collapse', 'control_collapse'),
    ('progress_collapse', 'progress_collapse'),
]


def describe(w, label, shown):
    if w is None:
        return f"{label:24s} : <нет>"
    try:
        w.update_idletasks()
        info = (
            f"x={w.winfo_x():4d} y={w.winfo_y():4d} "
            f"w={w.winfo_width():4d} h={w.winfo_height():4d} "
            f"reqW={w.winfo_reqwidth():4d} reqH={w.winfo_reqheight():4d} "
            f"mapped={int(w.winfo_ismapped())} "
            f"manager={w.winfo_manager() or '-':6s} "
            f"class={w.winfo_class()}"
        )
    except Exception as e:
        info = f"<err {e}>"
    return f"{label:24s} : {info}"


def walk(w, depth, max_depth, out):
    if depth > max_depth:
        return
    try:
        children = w.winfo_children()
    except Exception:
        children = []
    for c in children:
        try:
            c.update_idletasks()
            line = (
                f"{'  ' * depth}"
                f"{c.winfo_class():22s} "
                f"name={str(c).split('.')[-1]:20s} "
                f"x={c.winfo_x():4d} y={c.winfo_y():4d} "
                f"w={c.winfo_width():4d} h={c.winfo_height():4d} "
                f"reqW={c.winfo_reqwidth():4d} reqH={c.winfo_reqheight():4d} "
                f"mapped={int(c.winfo_ismapped())} "
                f"mgr={c.winfo_manager() or '-':6s}"
            )
        except Exception as e:
            line = f"{'  ' * depth}<err {e}>"
        out.append(line)
        walk(c, depth + 1, max_depth, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dump', default=None, help='записать отчёт в файл')
    ap.add_argument('--depth', type=int, default=3, help='глубина дерева виджетов')
    ap.add_argument('--show', action='store_true', help='показать окно (реальные размеры)')
    args = ap.parse_args()

    root = Tk()
    if not args.show:
        root.withdraw()
    app = ProfessionalDiskAnalyzer(root)

    if args.show:
        root.update()
        # даём pack/ttk.Notebook устояться
        for _ in range(10):
            root.update()
            time.sleep(0.05)

    root.update_idletasks()

    out = []
    out.append("=" * 100)
    out.append("ОКНО")
    out.append("=" * 100)
    out.append(f"geometry       : {root.winfo_geometry()}")
    out.append(f"min size       : {root.wm_minsize()}")
    out.append(f"max size       : {root.wm_maxsize()}")
    out.append(f"screen         : {root.winfo_screenwidth()}x{root.winfo_screenheight()}")
    out.append(f"state          : {root.state()}")
    out.append(f"shown          : {args.show}")
    out.append("")

    out.append("=" * 100)
    out.append("КЛЮЧЕВЫЕ ВИДЖЕТЫ")
    out.append("=" * 100)
    for label, attr in KEY_WIDGETS:
        if attr is None:
            out.append(describe(root, label, args.show))
        else:
            out.append(describe(getattr(app, attr, None), label, args.show))
    out.append("")

    out.append("=" * 100)
    out.append("MANAGER INFO (pack/grid)")
    out.append("=" * 100)
    for label, attr in KEY_WIDGETS:
        if attr is None:
            continue
        w = getattr(app, attr, None)
        if w is None:
            continue
        try:
            mgr = w.winfo_manager()
            if mgr == 'pack':
                pi = w.pack_info()
                out.append(f"{label:24s} pack : side={pi.get('side')} "
                           f"fill={pi.get('fill')} expand={pi.get('expand')}")
            elif mgr == 'grid':
                gi = w.grid_info()
                out.append(f"{label:24s} grid : row={gi.get('row')} "
                           f"col={gi.get('column')} sticky={gi.get('sticky')}")
            else:
                out.append(f"{label:24s} mgr  : {mgr or '-'}")
        except Exception as e:
            out.append(f"{label:24s} <err {e}>")
    out.append("")

    out.append("=" * 100)
    out.append(f"ДЕРЕВО ВИДЖЕТОВ (глубина {args.depth})")
    out.append("=" * 100)
    walk(root, 1, args.depth, out)

    report = "\n".join(out)
    print(report)

    if args.dump:
        try:
            with open(args.dump, 'w', encoding='utf-8') as f:
                f.write(report + "\n")
            print(f"\n[diag] отчёт записан: {args.dump}")
        except Exception as e:
            print(f"\n[diag] не удалось записать {args.dump}: {e}")

    try:
        app.on_closing()
    except Exception:
        root.destroy()


if __name__ == '__main__':
    main()