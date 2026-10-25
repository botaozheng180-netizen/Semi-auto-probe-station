"""A non-modal outline around a real widget, without changing its command."""
from __future__ import annotations

import tkinter as tk


class GuideHighlight:
    def __init__(self, parent):
        self.parent = parent
        self.target = None
        self.extra_outlines = []
        self.window = tk.Toplevel(parent, bg="#ff00fe")
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.transient(parent)
        self.supported = parent.tk.call("tk", "windowingsystem") == "win32"
        if self.supported:
            self.window.wm_attributes("-transparentcolor", "#ff00fe")
            self.window.wm_attributes("-toolwindow", True)
        self.canvas = tk.Canvas(self.window, bg="#ff00fe", bd=0, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

    def show(self, target):
        self.target = target
        self.refresh()

    def clear(self):
        self.target = None
        self.window.withdraw()
        for outline in self.extra_outlines:
            outline.clear()

    def refresh(self):
        target = self.target
        if target is None:
            return
        targets = list(target) if isinstance(target, (list, tuple)) else [target]
        while len(self.extra_outlines) < len(targets)-1:
            self.extra_outlines.append(GuideHighlight(self.parent))
        for index, outline in enumerate(self.extra_outlines):
            if index+1 < len(targets):
                outline.show(targets[index+1])
            else:
                outline.clear()
        target = targets[0] if targets else None
        if target is None:
            self.window.withdraw()
            return
        try:
            if not self.supported or not target.winfo_exists() or not target.winfo_ismapped():
                self.window.withdraw()
                return
            # The transparent center passes clicks to the underlying control.
            x, y = target.winfo_rootx()-4, target.winfo_rooty()-4
            width, height = target.winfo_width()+8, target.winfo_height()+8
            self.window.geometry(f"{width}x{height}+{x}+{y}")
            self.canvas.delete("all")
            color = self.parent.colors.get("border_focus", "#6554d9")
            r = min(10, height//3)
            points = (r, 2, width-r, 2, width-2, 2, width-2, r,
                      width-2, height-r, width-2, height-2, width-r, height-2,
                      r, height-2, 2, height-2, 2, height-r, 2, r, 2, 2)
            self.canvas.create_polygon(points, smooth=True, fill="", outline=color, width=2)
            self.window.deiconify()
            self.window.lift(target.winfo_toplevel())
        except tk.TclError:
            self.clear()

    def destroy(self):
        self.target = None
        for outline in self.extra_outlines:
            outline.destroy()
        self.window.destroy()

    def hide(self):
        self.window.withdraw()
        for outline in self.extra_outlines:
            outline.hide()
