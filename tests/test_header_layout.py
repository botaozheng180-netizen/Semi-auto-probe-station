import os
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from tkinter import font as tkfont, ttk
from unittest.mock import patch

from semi_auto_probe.app import ProbeApp
from semi_auto_probe.ui.neumorphic_theme import LIGHT
from semi_auto_probe.ui.rolling_description import RollingDescription


class HeaderLayoutTests(unittest.TestCase):
    def test_rolling_description_keeps_fixed_width_and_scrolls(self):
        root = tk.Tk()
        try:
            root.geometry("140x80")
            subtitle = RollingDescription(root, "A description longer than its available width", LIGHT, width=130)
            subtitle.pack(anchor="w")
            root.update()
            self.assertIsNotNone(subtitle.job)
            subtitle._cancel()
            subtitle._advance()
            self.assertEqual(subtitle.offset, 1)
            root.geometry("900x80")
            root.update()
            self.assertEqual(subtitle.winfo_width(), 130)
            self.assertIsNotNone(subtitle.job)
        finally:
            root.destroy()

    def test_title_toolbar_and_tabs_fit_at_normal_window_widths(self):
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                with patch.object(ProbeApp, "start_camera"), patch.object(ProbeApp, "connect_and_test_serial"), \
                     patch.object(ProbeApp, "_maximize_default_window", lambda app: None):
                    app = ProbeApp()
                try:
                    for width in (1600, 1800):
                        app.geometry(f"{width}x900")
                        app.update()
                        title = app.app_title_label
                        self.assertEqual(app.rolling_description.winfo_width(), title.winfo_reqwidth())
                        self.assertIsNotNone(app.rolling_description.job)
                        stop = app.emergency_stop_button
                        theme = app.theme_button
                        stop_right = stop.winfo_rootx() + stop.winfo_width()
                        theme_right = theme.winfo_rootx() + theme.winfo_width()
                        self.assertLessEqual(abs(stop_right - theme_right), 2)
                        self.assertLessEqual(stop_right, app.winfo_rootx() + app.winfo_width() - 16)
                        tab_font = tkfont.Font(root=app, font=ttk.Style(app).lookup("Navigation.TButton", "font"))
                        self.assertEqual(tab_font.actual("size"), 12)
                        self.assertEqual(tab_font.actual("weight"), "bold")
                        for button in app.tab_buttons.values():
                            self.assertTrue(button.cget("image"))
                            self.assertEqual(str(button.cget("compound")), "left")
                            self.assertFalse(any(ord(c) > 127 for c in button.cget("text")))
                finally:
                    app.destroy()
            finally:
                os.chdir(previous)
