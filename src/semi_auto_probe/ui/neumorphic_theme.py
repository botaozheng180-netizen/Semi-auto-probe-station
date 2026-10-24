"""Cached, nine-slice ttk surfaces. Native widget bindings remain intact."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageDraw, ImageFilter, ImageTk

LIGHT = dict(bg="#e0e5ec", surface="#e0e5ec", surface_2="#d8dfe8",
             surface_3="#e0e5ec", input="#e0e5ec", input_focus="#e7ecf3",
             border="#a4afbf", border_focus="#6554d9", text="#253348",
             muted="#536278", accent="#6554d9", accent_hover="#5745c9",
             blue="#235fa3", warning="#8b5900", danger="#b52546")


def surface(master, base, bright, shadow, *, inset=False, focus=None, face=None, size=(64, 40), margin=5, radius=10, blur=2, offset=2):
    """Rasterize once, then let Tk stretch the center without scaling corners."""
    w, h = size
    mask = Image.new("L", size)
    bounds = (margin, margin, w-margin-1, h-margin-1)
    ImageDraw.Draw(mask).rounded_rectangle(bounds, radius, fill=255)
    result = Image.new("RGB", size, base)
    for dx, dy, color in ((-offset, -offset, bright), (offset, offset, shadow)):
        layer = Image.new("L", size)
        ImageDraw.Draw(layer).rounded_rectangle((bounds[0]+dx, bounds[1]+dy, bounds[2]+dx, bounds[3]+dy), radius, fill=255)
        layer = layer.filter(ImageFilter.GaussianBlur(blur))
        if inset:
            from PIL import ImageChops
            layer = ImageChops.multiply(ImageChops.invert(layer), mask)
        result.paste(color, (0, 0), layer)
    if not inset:
        result.paste(face or base, (0, 0), mask)
    if focus:
        ImageDraw.Draw(result).rounded_rectangle((5, 5, w-6, h-6), 10, outline=focus, width=2)
    return ImageTk.PhotoImage(result, master=master)


def install(root, colors, mode):
    style = ttk.Style(root)
    bright, shadow = (("#ffffff", "#b8bcc2") if mode == "light" else ("#2b3b4e", "#05080d"))
    cache = getattr(root, "_neu_cache", {})
    root._neu_cache = cache
    if mode not in cache:
        normal = surface(root, colors["surface"], bright, shadow)
        pressed = surface(root, colors["surface"], bright, shadow, inset=True)
        focus = surface(root, colors["surface"], bright, shadow, focus=colors["border_focus"])
        # Light the whole face without changing geometry or painting a ring.
        highlighted = surface(root, colors["surface"], bright, shadow,
                              face="#eef2f7" if mode == "light" else "#223144")
        keyboard_focus = surface(root, colors["surface"], bright, shadow,
                                 face="#f8faff" if mode == "light" else "#2d4056")
        cache[mode] = (normal, pressed, focus, highlighted, keyboard_focus)
        panel = surface(root, colors["bg"], bright, shadow, face=colors["surface"],
                        size=(80, 80), margin=8, radius=14, blur=4, offset=3)
        cache[mode] += (panel,)
        style.element_create(f"Neu{mode}.panel", "image", panel,
                             border=24, padding=12, width=0, height=0, sticky="nsew")
        # Slice borders control rendering, not geometry. Match clam's
        # three-pixel frame and let the label/padding determine the size.
        style.element_create(f"Neu{mode}.button", "image", normal,
                             ("disabled", normal), ("pressed", pressed),
                             ("focus", keyboard_focus), ("active", highlighted), border=15, padding=3, width=0, height=0, sticky="nsew")
        style.element_create(f"Neu{mode}.field", "image", pressed,
                             ("focus", focus), border=15, padding=3, width=0, height=0, sticky="nsew")
        switches = []
        for selected in (False, True):
            img = Image.new("RGB", (108, 60), colors["surface"])
            draw = ImageDraw.Draw(img)
            draw.rounded_rectangle((3, 5, 105, 55), 25, fill=shadow)
            draw.rounded_rectangle((5, 8, 103, 55), 24, fill=bright)
            draw.rounded_rectangle((6, 9, 102, 51), 22, fill=colors["input"])
            x = 58 if selected else 9
            draw.ellipse((x+2, 13, x+42, 53), fill=shadow)
            draw.ellipse((x, 9, x+40, 49), fill=colors["surface_2"], outline=bright, width=2)
            if selected:
                draw.ellipse((x+15, 24, x+25, 34), fill=colors["accent"])
            switches.append(ImageTk.PhotoImage(img.resize((36, 20), Image.Resampling.LANCZOS), master=root))
        cache[mode] += tuple(switches)
        # All states must have the same dimensions and a positive center after
        # the two 15px slice borders. A 24px-high image hangs Tk's paint loop.
        flat = ImageTk.PhotoImage(Image.new("RGB", (normal.width(), normal.height()), colors["surface"]), master=root)
        cache[mode] += (flat,)
        style.element_create(f"Neu{mode}.tab", "image", flat,
                             ("disabled", flat), ("pressed", pressed),
                             ("focus", keyboard_focus), ("selected", highlighted),
                             ("active", normal),
                             border=15, padding=3, width=0, height=0, sticky="nsew")
        style.element_create(f"Neu{mode}.switch", "image", switches[0],
                             ("selected", switches[1]), width=40, sticky="w")
    # Opt-in outer cards only; nested Panel.TFrame and viewports stay flat.
    style.layout("Raised.Panel.TFrame", [(f"Neu{mode}.panel", {"sticky": "nsew"})])
    style.configure("Raised.Panel.TFrame", background=colors["surface"])
    button_layout = [(f"Neu{mode}.button", {"sticky": "nsew", "children": [
        ("Button.padding", {"sticky": "nsew", "children": [
            ("Button.label", {"sticky": "nsew"})]})]})]
    style.layout("Navigation.TButton", [(f"Neu{mode}.tab", {"sticky": "nsew", "children": [
        ("Button.padding", {"sticky": "nsew", "children": [
            ("Button.label", {"sticky": "nsew"})]})]})])
    style.configure("Navigation.TButton", font=("Segoe UI Emoji", 12),
                    padding=(8, 7), width=-1, anchor="center")
    style.map("Navigation.TButton", foreground=[("disabled", colors["muted"]),
              ("selected", colors["accent"]), ("active", colors["text"]),
              ("!disabled", colors["muted"])])
    for name, color in (("TButton", "text"), ("Accent.TButton", "accent"),
                        ("Danger.TButton", "danger"), ("Instrument.TButton", "blue"),
                        ("Ghost.TButton", "muted"), ("Calibration.TButton", "text")):
        style.layout(name, button_layout)
        style.configure(name, foreground=colors[color])
        style.map(name, foreground=[("disabled", colors["muted"]), ("!disabled", colors[color])])
    style.configure("Calibration.TButton", padding=(6, 5), font=("Segoe UI Symbol", 10, "bold"))
    style.map("Calibration.TButton", foreground=[("selected", colors["warning"]), ("!selected", colors["text"])])
    style.layout("TEntry", [(f"Neu{mode}.field", {"sticky": "nsew", "children": [
        ("Entry.padding", {"sticky": "nsew", "children": [("Entry.textarea", {"sticky": "nsew"})]})]})])
    style.layout("TCheckbutton", [("Checkbutton.padding", {"sticky": "nsew", "children": [
        (f"Neu{mode}.switch", {"side": "left", "sticky": "w"}),
        ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
            ("Checkbutton.label", {"sticky": "nsew"})]})]})])
    style.layout("Horizontal.TProgressbar", [(f"Neu{mode}.field", {"sticky": "nsew", "children": [
        ("Horizontal.Progressbar.pbar", {"side": "left", "sticky": "ns"})]})])
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, fieldbackground=colors["input"], foreground=colors["text"],
                        lightcolor=shadow, darkcolor=bright, borderwidth=2)
    style.configure("Horizontal.TProgressbar", troughcolor=colors["input"],
                    background=colors["accent"], lightcolor=shadow, darkcolor=bright,
                    borderwidth=2, thickness=14)


def recolor_widgets(root, previous, current):
    """Update classic Tk surfaces without touching image/camera pixel data."""
    replacements = {value: current[key] for key, value in previous.items()}
    def visit(widget):
        for option in ("background", "foreground", "insertbackground", "highlightbackground"):
            try:
                old = str(widget.cget(option))
                if old in replacements:
                    widget.configure(**{option: replacements[old]})
            except tk.TclError:
                pass
        if hasattr(widget, "_draw") and hasattr(widget, "switch_width"):
            widget.colors = current
            widget._draw()
        for child in widget.winfo_children():
            visit(child)
    visit(root)
