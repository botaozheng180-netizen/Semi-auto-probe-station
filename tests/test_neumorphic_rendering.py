"""Exercise actual painting: withdrawn widgets do not catch Tk paint hangs."""
import os
from pathlib import Path
import subprocess
import sys
import unittest


class NeumorphicRenderingTests(unittest.TestCase):
    def test_navigation_states_paint_without_hanging(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
        result = subprocess.run(
            [sys.executable, "-c", '''
import tkinter as tk
from tkinter import ttk
from semi_auto_probe.ui.neumorphic_theme import install, LIGHT
root = tk.Tk()
root.geometry("400x100+0+0")
try:
    for mode in ("dark", "light", "dark"):
        install(root, LIGHT, mode)
        button = ttk.Button(root, text="MainView", style="Navigation.TButton")
        button.pack()
        for state in ("!selected", "selected", "active", "pressed", "focus", "disabled"):
            button.state([state])
            root.update()
            button.state(["!" + state.lstrip("!")])
        button.destroy()
        panel = ttk.Frame(root, style="Raised.Panel.TFrame", padding=10)
        panel.pack(fill="both", expand=True)
        inner = ttk.Frame(panel, style="Panel.TFrame")
        inner.pack(fill="both", expand=True)
        view = tk.Canvas(inner, width=80, height=30, highlightthickness=1)
        view.pack(fill="both", expand=True)
        for geometry in ("400x200", "640x360", "300x160"):
            root.geometry(geometry)
            root.update()
            assert inner.cget("style") == "Panel.TFrame"
            assert int(view.cget("highlightthickness")) == 1
            assert inner.winfo_x() >= 8 and inner.winfo_y() >= 8
        panel.destroy()
finally:
    root.destroy()
print("paint completed")
'''], env=env, capture_output=True, text=True, timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("paint completed", result.stdout)
