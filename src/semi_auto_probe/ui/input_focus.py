"""Finish single-line editing without suppressing existing Enter actions."""
import tkinter as tk
from tkinter import ttk


def install_input_focus(root):
    inputs = (tk.Entry, tk.Spinbox, ttk.Entry, ttk.Spinbox, ttk.Combobox)
    tag = f"FinishInput{id(root)}"

    def outside_click(event):
        focused = root.focus_get()
        if isinstance(focused, inputs) and not isinstance(event.widget, inputs):
            # Move focus before the click action; another input still receives
            # its normal click/focus behavior when switching between fields.
            root.focus_set()

    def enter(event):
        if isinstance(event.widget, inputs):
            widget = event.widget
            # Let widget-specific commit/move callbacks run first, even if
            # they return "break". Multiline editors retain their Enter key.
            root.after_idle(lambda: root.focus_set() if root.focus_get() is widget else None)

    root.bind_class(tag, "<Button-1>", outside_click)
    root.bind_class(tag, "<Return>", enter)
    root.bind_class(tag, "<KP_Enter>", enter)

    def attach(widget):
        if tag not in widget.bindtags():
            widget.bindtags((tag,) + widget.bindtags())
        for child in widget.winfo_children():
            attach(child)
    attach(root)
    root.bind("<Map>", lambda event: attach(event.widget), add="+")
