import tempfile
import os
import threading
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from semi_auto_probe.app import ProbeApp


class ThemeSwitchingTests(unittest.TestCase):
    def test_custom_panels_follow_light_startup_and_theme_changes(self):
        from matplotlib.colors import to_hex
        from semi_auto_probe.focusmap_3d import CanvasFocusMap3DView

        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp)
                Path("ui-theme.json").write_text('{"mode":"light"}')
                with patch.object(ProbeApp, "start_camera"), patch.object(ProbeApp, "connect_and_test_serial"):
                    app = ProbeApp(startup_progress=lambda *_: None)
                try:
                    self.assertEqual(app.theme_mode, "light")
                    fallback = CanvasFocusMap3DView(app, app.colors)
                    fallback.render([], None)
                    app.agent_panel._append_chat("User", "Keep **this message** and `code`.")
                    conversation = app.agent_panel.chat_text.get("1.0", "end")
                    app._draw_af_plane_mesh()
                    app._draw_focusmap_3d()
                    app._render_imgstitch_preview()
                    app._render_imgstitch_scatter()
                    app.autotest_panel._draw_z_wobble_curve()
                    for mode in ("light", "dark", "light"):
                        app.theme_mode = mode
                        app._configure_theme()
                        for canvas in (app.focusmap_mesh_canvas, app.imgstitch_mosaic_canvas,
                                       app.imgstitch_scatter_canvas, app.autotest_panel.z_wobble_curve_canvas,
                                       fallback.widget):
                            self.assertEqual(canvas.cget("background"), app.colors["surface_2"])
                        self.assertEqual(to_hex(app.focusmap_3d_view.figure.get_facecolor()), app.colors["surface_2"])
                        self.assertEqual(to_hex(app.focusmap_3d_view.axes.get_facecolor()), app.colors["surface_2"])
                        curve = app.autotest_panel.z_wobble_curve_canvas
                        self.assertEqual(curve.itemcget(curve.find_all()[0], "fill"), app.colors["surface_2"])
                        chat = app.agent_panel.chat_text
                        self.assertEqual(chat.tag_cget("agent_bubble", "background"), app.colors["surface"])
                        self.assertEqual(chat.tag_cget("user_bubble", "background"), app.colors["surface_3"])
                        self.assertEqual(chat.tag_cget("md_code", "background"), app.colors["surface_2"])
                        self.assertEqual(chat.tag_cget("md_bold", "foreground"), app.colors["text"])
                        self.assertEqual(chat.get("1.0", "end"), conversation)
                finally:
                    app.destroy()
            finally:
                os.chdir(previous)

    def test_readonly_positions_and_cached_af_plot_follow_palette(self):
        # Exercise the real theme/plot methods without hardware startup.
        root = ProbeApp.__new__(ProbeApp)
        tk.Tk.__init__(root)
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                root.config_path = Path(tmp) / "config.json"
                root.theme_mode = "dark"
                root._configure_theme()
                root.focus_lock = threading.Lock()
                root.autofocus_z_score_samples = []
                root.autofocus_fine_range = None
                positions = [tk.Entry(root, state="readonly", readonlybackground=root.colors["surface_2"])
                             for _ in range(3)]
                plots = [tk.Canvas(root, bg=root.colors["surface_2"]) for _ in range(2)]
                for compact, plot in enumerate(plots):
                    root._draw_af_z_score_plot(plot, compact=bool(compact))
                for mode in ("light", "dark", "light", "dark"):
                    root.theme_mode = mode
                    root._configure_theme()
                    for entry in positions:
                        self.assertEqual(entry.cget("readonlybackground"), root.colors["surface_2"])
                        self.assertEqual(entry.cget("state"), "readonly")
                    for plot in plots:
                        self.assertEqual(plot.cget("background"), root.colors["surface_2"])
                        self.assertEqual(plot.itemcget(plot.find_all()[0], "fill"), root.colors["surface_2"])
                        texts = [item for item in plot.find_all() if plot.type(item) == "text"]
                        self.assertTrue(texts)
                        self.assertTrue(all(plot.itemcget(item, "fill") == root.colors["muted"] for item in texts))
        finally:
            tk.Tk.destroy(root)
