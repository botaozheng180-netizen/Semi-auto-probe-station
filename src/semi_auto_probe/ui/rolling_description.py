"""A fixed-width subtitle that scrolls continuously while visible."""
import tkinter as tk
from tkinter import font as tkfont


class RollingDescription(tk.Canvas):
    def __init__(self, parent, text, colors, *, width=1):
        self.colors = colors
        self.text = text
        self.text_font = tkfont.Font(root=parent, family="Segoe UI", size=9)
        super().__init__(parent, width=width, height=self.text_font.metrics("linespace") + 2,
                         bd=0, highlightthickness=0, background=colors["bg"])
        self.offset = 0
        self.job = None
        self._theme_redraw = self.refresh
        self.bind("<Configure>", lambda _event: self.refresh())
        self.bind("<Map>", lambda _event: self.refresh())
        self.bind("<Unmap>", lambda _event: self._cancel())
        self.bind("<Destroy>", lambda _event: self._cancel())

    def _cancel(self):
        if self.job is not None:
            self.after_cancel(self.job)
            self.job = None

    def refresh(self):
        self._cancel()
        self.offset = 0
        self.configure(background=self.colors["bg"])
        self._paint()
        if self.winfo_ismapped():
            self.job = self.after(40, self._advance)

    def _paint(self):
        self.delete("subtitle")
        span = self.text_font.measure(self.text) + 32
        for x in (-self.offset, span - self.offset):
            self.create_text(x, 0, text=self.text, anchor="nw", font=self.text_font,
                             fill=self.colors["muted"], tags="subtitle")

    def _advance(self):
        self.job = None
        if not self.winfo_ismapped():
            return
        self.offset = (self.offset + 1) % (self.text_font.measure(self.text) + 32)
        self._paint()
        self.job = self.after(40, self._advance)
