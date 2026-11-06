import os, sys, time, traceback
sys.path.insert(0, os.path.abspath('.'))
from tkinter import Tk
from src.gui import ProfessionalDiskAnalyzer

root = Tk()
root.withdraw()
app = ProfessionalDiskAnalyzer(root)
root.update_idletasks()

# заполним топ из SQLite
app._refresh_top_tabs()
root.update_idletasks()

print("top_folders:", len(app.top_folders))
if not app.top_folders:
    print("НЕТ ДАННЫХ — нечего кликать")
    app.on_closing()
    sys.exit(0)

first = app.top_folders[0]
print("first path:", first['path'])
print("isdir:", os.path.isdir(first['path']))

# программно выделяем первую строку и вызываем handler
children = app.top_folders_tree.get_children()
if not children:
    print("НЕТ СТРОК в treeview")
    app.on_closing()
    sys.exit(0)

app.top_folders_tree.selection_set(children[0])
root.update_idletasks()

sel = app.top_folders_tree.selection()
print("selection:", sel)
vals = app.top_folders_tree.item(sel[0], 'values')
print("values:", vals)

try:
    r = app._top_folders_double_click()
    print("handler returned:", r)
except Exception as e:
    print("HANDLER EXCEPTION:", e)
    traceback.print_exc()

# даём time для add_log + os.startfile
for _ in range(20):
    root.update()
    time.sleep(0.05)

app.on_closing()
print("DONE")
