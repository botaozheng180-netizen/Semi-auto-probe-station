"""Clipped panel viewports and local, scrollbar-free wheel routing."""
import tkinter as tk
from tkinter import ttk


class ScrollablePanel(ttk.Frame):
    """Content frame genuinely parented to its canvas, with an outer card.

    Callers build their controls in this frame. Geometry placement and string
    conversion expose the outer card to grid, pack, paned windows and canvases.
    Widget operations and child construction still target the inner frame.
    """
    def __init__(self, parent, *, raised=True, style=None, **options):
        self.shell = ttk.Frame(parent, style="Raised.Panel.TFrame" if raised else "Panel.TFrame",
                               padding=18 if raised else 0)
        self.shell.rowconfigure(0, weight=1)
        self.shell.columnconfigure(0, weight=1)
        colors = getattr(parent.winfo_toplevel(), "colors", {})
        self.canvas = tk.Canvas(self.shell, bd=0, highlightthickness=0,
                                background=colors.get("surface", "#111821"),
                                width=1, height=1, yscrollincrement=1, xscrollincrement=1)
        self.canvas.grid(sticky="nsew")
        super().__init__(self.canvas, style="Panel.TFrame", **options)
        self.panel = self
        # Use the content path explicitly: str(self) exposes the outer card.
        self.item = self.canvas.create_window(0, 0, window=self._w, anchor="nw")
        self.pending = None
        self.bind("<Configure>", self.schedule, add="+")
        self.canvas.bind("<Configure>", self.schedule, add="+")
        self.schedule()

    def __str__(self):
        return str(self.shell)

    def grid_configure(self, *args, **kwargs):
        return self.shell.grid_configure(*args, **kwargs)

    grid = grid_configure

    def pack_configure(self, *args, **kwargs):
        return self.shell.pack_configure(*args, **kwargs)

    pack = pack_configure

    def place_configure(self, *args, **kwargs):
        return self.shell.place_configure(*args, **kwargs)

    place = place_configure

    def grid_info(self):
        return self.shell.grid_info()

    def grid_remove(self):
        return self.shell.grid_remove()

    def grid_forget(self):
        return self.shell.grid_forget()

    def pack_forget(self):
        return self.shell.pack_forget()

    def schedule(self, _event=None):
        if self.pending is None:
            self.pending = self.canvas.after_idle(self.sync)

    def sync(self):
        self.pending = None
        if not self.canvas.winfo_exists():
            return
        requested_width = self.winfo_reqwidth()
        requested_height = self.winfo_reqheight()
        # Propagate natural size to the containing layout; actual viewport size
        # can shrink independently when the window has less room.
        if int(self.canvas.cget("width")) != requested_width:
            self.canvas.configure(width=requested_width)
        if int(self.canvas.cget("height")) != requested_height:
            self.canvas.configure(height=requested_height)
        width = max(self.canvas.winfo_width(), requested_width)
        height = max(self.canvas.winfo_height(), requested_height)
        self.canvas.itemconfigure(self.item, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))


def install_panel_scrolling(root, pages, colors):
    viewports = {}

    def collect(widget):
        if isinstance(widget, ScrollablePanel):
            viewports[widget] = widget
        for child in widget.winfo_children():
            collect(child)
    for page in pages:
        collect(page)
    root._panel_viewports = viewports
    tag = f"PanelWheel{id(root)}"

    def route(event):
        widget = event.widget
        # Preserve text scrolling, field editing and camera/GDS wheel gestures.
        if isinstance(widget, (tk.Text, tk.Listbox, ttk.Treeview, ttk.Combobox, ttk.Spinbox)):
            return None
        if isinstance(widget, tk.Canvas) and not widget.find_withtag("all"):
            return None
        if isinstance(widget, tk.Canvas) and not any(widget.type(i) == "window" for i in widget.find_all()):
            return None
        horizontal = bool(getattr(event, "state", 0) & 1)
        delta = getattr(event, "delta", 0)
        pixels = -delta / 120 * 36 if delta else (-36 if getattr(event, "num", 0) == 4 else 36)
        current = widget
        while current is not None:
            viewport = viewports.get(current)
            canvas = viewport.canvas if viewport else current if isinstance(current, tk.Canvas) else None
            if canvas is not None:
                view = canvas.xview if horizontal else canvas.yview
                first, last = view()
                if last-first < 0.999 and ((pixels < 0 and first > 0) or (pixels > 0 and last < 1)):
                    # Moveto gives pixel-resolution movement for small touchpad deltas.
                    bounds = canvas.bbox("all")
                    extent = (bounds[2]-bounds[0]) if horizontal else (bounds[3]-bounds[1])
                    move = canvas.xview_moveto if horizontal else canvas.yview_moveto
                    move(first + pixels / max(1, extent))
                    return "break"
            current = current.master
        return None

    for sequence in ("<MouseWheel>", "<Shift-MouseWheel>", "<Button-4>", "<Button-5>"):
        root.bind_class(tag, sequence, route)

    def tag_widget(widget):
        if isinstance(widget, ttk.Scrollbar):
            command = widget.tk.splitlist(widget.cget("command"))
            try:
                target = root.nametowidget(command[0]) if command else None
            except KeyError:
                target = None
            # Keep data-table scrollbars; hide only existing panel scrollbars.
            if isinstance(target, tk.Canvas) and any(target.type(i) == "window" for i in target.find_all()):
                if widget.winfo_manager() == "grid":
                    widget.grid_remove()
                elif widget.winfo_manager() == "pack":
                    widget.pack_forget()
        if tag not in widget.bindtags():
            widget.bindtags((tag,) + widget.bindtags())
        for child in widget.winfo_children():
            tag_widget(child)
    for page in pages:
        tag_widget(page)
    root.bind("<Map>", lambda event: tag_widget(event.widget), add="+")

