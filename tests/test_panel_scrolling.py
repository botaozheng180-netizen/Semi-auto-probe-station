import os
from pathlib import Path
import subprocess
import sys
import unittest


class PanelScrollingTests(unittest.TestCase):
    def test_sidebar_width_folding_and_window_resize(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run([sys.executable, "-c", '''
import tkinter as tk
from tkinter import ttk
from semi_auto_probe.ui.panel_scrolling import ScrollablePanel, FoldableSidebar, fit_right_pane
r = tk.Tk()
r.geometry("1200x650")
pane = ttk.PanedWindow(r, orient=tk.HORIZONTAL)
pane.pack(fill="both", expand=True)
viewer = ScrollablePanel(pane, padding=10, fit_width=True)
viewer.rowconfigure(0, weight=1)
left = ScrollablePanel(viewer, raised=False)
left.grid(row=0, column=0, sticky="nsew")
preview = ttk.Label(left, text="Preview")
preview.pack()
canvas = ttk.Frame(viewer, width=600)
canvas.grid(row=0, column=1, sticky="nsew")
sidebar = FoldableSidebar(viewer, left, canvas)
right = ScrollablePanel(pane, padding=12)
ttk.Entry(right, width=30).pack()
pane.add(viewer, weight=1)
pane.add(right, weight=0)
fit_right_pane(pane, right)
r.update()
image = tk.PhotoImage(width=420, height=300)
preview.configure(image=image)
sidebar.schedule()
r.update()
assert left.shell.winfo_width() >= left.winfo_reqwidth()
assert right.canvas.winfo_width() >= right.winfo_reqwidth()
assert right.canvas.winfo_width() - right.winfo_reqwidth() < 5
original = canvas.winfo_width()
sidebar.button.invoke()
r.update()
assert canvas.winfo_width() > original
assert not left.shell.winfo_ismapped()
sidebar.button.invoke()
r.update()
assert left.shell.winfo_ismapped()
assert canvas.winfo_width() == original
right_width = right.canvas.winfo_width()
r.geometry("1400x650")
r.update()
assert abs(right.canvas.winfo_width() - right_width) <= 2
assert canvas.winfo_width() > original
r.destroy()
'''], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_clipping_local_wheel_and_resize(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run([sys.executable, "-c", '''
import tkinter as tk
from tkinter import ttk
from semi_auto_probe.ui.neumorphic_theme import install, LIGHT
from semi_auto_probe.ui.panel_scrolling import ScrollablePanel, install_panel_scrolling
r = tk.Tk()
r.geometry("600x250")
install(r, LIGHT, "light")
page = ttk.Frame(r)
page.pack(fill="both", expand=True)
pane = ttk.PanedWindow(page)
pane.pack(fill="both", expand=True)
panels = []
for n in range(2):
    p = ScrollablePanel(pane)
    pane.add(p, weight=1)
    for i in range(40):
        ttk.Label(p, text=f"Row {i}").pack()
    panels.append(p)
r.update()
install_panel_scrolling(r, [page], LIGHT)
r.update()
a, b = [r._panel_viewports[p] for p in panels]
assert a.canvas.winfo_x() >= 18 and a.canvas.winfo_y() >= 18
assert a.canvas.winfo_height() < panels[0].winfo_height()
r.lift()
r.update()
label = panels[0].winfo_children()[0]
x = label.winfo_rootx() + label.winfo_width() // 2
y = label.winfo_rooty() + label.winfo_height() // 2
assert r.winfo_containing(x, y) == label, "Card shell obscures its content"
assert panels[0].master is a.canvas
label = panels[0].winfo_children()[0]
label.event_generate("<MouseWheel>", delta=-120)
r.update()
assert a.canvas.yview()[0] > 0 and b.canvas.yview()[0] == 0
before = a.canvas.yview()[0]
for i in range(12):
    label.event_generate("<MouseWheel>", delta=-10)
r.update()
assert a.canvas.yview()[0] > before
# Contents must remain clipped at the top and bottom of the card while scrolled.
for y in (a.shell.winfo_rooty() + 10, a.shell.winfo_rooty() + a.shell.winfo_height() - 10):
    hit = r.winfo_containing(a.canvas.winfo_rootx() + 20, y)
    assert hit == a.shell, ("Content covers card border", hit)
for child in panels[0].winfo_children()[5:]:
    child.destroy()
r.geometry("600x600")
r.update()
assert a.canvas.yview() == (0.0, 1.0)
r.destroy()
'''], env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
