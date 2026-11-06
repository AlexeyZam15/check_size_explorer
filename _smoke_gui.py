import os
import sys
import traceback

sys.path.insert(0, os.path.abspath('.'))
from tkinter import Tk
from src.gui import ProfessionalDiskAnalyzer

MARKERS = []
try:
    root = Tk()
    root.withdraw()
    app = ProfessionalDiskAnalyzer(root)
    checks = [
        ('tree', hasattr(app, 'tree')),
        ('log_text', hasattr(app, 'log_text')),
        ('cache_tree', hasattr(app, 'cache_tree')),
        ('top_folders_tree', hasattr(app, 'top_folders_tree')),
        ('drives_frame', hasattr(app, 'drives_frame')),
        ('selected_drives', isinstance(getattr(app, 'selected_drives', None), dict)),
        ('selected_custom_path', hasattr(app, 'selected_custom_path')),
        ('compute_top_folders', callable(getattr(app, '_compute_top_folders', None))),
        ('populate_drive_checkboxes', callable(getattr(app, '_populate_drive_checkboxes', None))),
        ('get_scan_roots', callable(getattr(app, '_get_scan_roots', None))),
        ('refresh_top_tabs', callable(getattr(app, '_refresh_top_tabs', None))),
        ('go_to_scan_root', callable(getattr(app, 'go_to_scan_root', None))),
        ('load_top_from_sqlite', callable(getattr(app, '_load_top_from_sqlite', None))),
        ('top_folders_click', callable(getattr(app, '_top_folders_click', None))),
    ]
    for name, ok in checks:
        MARKERS.append(f"{'OK ' if ok else 'FAIL'} {name}")
        if not ok:
            print('\n'.join(MARKERS));
            raise SystemExit('SMOKE-FAIL: ' + name)

    app._refresh_top_tabs()
    MARKERS.append('OK _refresh_top_tabs()')
    roots = app._get_scan_roots()
    MARKERS.append(f'OK _get_scan_roots() -> {len(roots)} roots: {roots}')

    fake_sizes = {
        'C:\\Games': 10_000,
        'C:\\Games\\Steam': 9_950,
        'C:\\Games\\Steam\\common': 9_900,
        'C:\\Games\\Steam\\common\\Game': 9_500,
        'C:\\Games\\Steam\\common\\Game\\data': 9_000,
        'C:\\Users\\x\\Downloads': 5_000,
        'C:\\games': 10_000,  # дубликат по регистру
        'C:/Games': 10_000,  # дубликат по слэшу
    }
    fake_counts = {k: 1 for k in fake_sizes}
    fake_roots = {k: 'C:\\' for k in fake_sizes}
    top = app._compute_top_folders(fake_sizes, fake_counts, fake_roots,
                                   min_depth=3, limit=10)
    MARKERS.append(f'OK _compute_top_folders() -> {len(top)} entries; '
                   f'top={[t["path"] for t in top[:3]]}')
    if not top:
        print('\n'.join(MARKERS));
        raise SystemExit('SMOKE-FAIL: top empty')

    paths_lower = [os.path.normcase(os.path.normpath(t['path'])) for t in top]
    if len(paths_lower) != len(set(paths_lower)):
        print('\n'.join(MARKERS))
        raise SystemExit('SMOKE-FAIL: duplicates in top_folders')

    app.on_closing()
    MARKERS.append('OK on_closing()')
except SystemExit:
    raise
except Exception as e:
    print('\n'.join(MARKERS))
    traceback.print_exc()
    raise SystemExit('SMOKE-FAIL: ' + str(e))

print('\n'.join(MARKERS))
print('SMOKE-OK')