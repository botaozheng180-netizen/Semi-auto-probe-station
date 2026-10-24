"""Shared neumorphic switch for toolbar and panel controls."""
from __future__ import annotations

import tkinter as tk
from collections.abc import Callable


class ToggleSwitch(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        variable: tk.BooleanVar,
        colors: dict[str, str],
        *,
        command: Callable[[], None] | None = None,
        background: str | None = None,
        width: int = 44,
        height: int = 24,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=background or colors["surface"],
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            takefocus=True,
        )
        self.variable = variable
        self.colors = colors
        self.command = command
        self.switch_width = width
        self.switch_height = height
        self.variable.trace_add("write", lambda *_args: self._draw())
        self.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.bind("<Return>", self._toggle)
        self.bind("<FocusIn>", lambda _event: self._draw())
        self.bind("<FocusOut>", lambda _event: self._draw())
        self._draw()

    def _toggle(self, _event: tk.Event | None = None) -> str:
        self.variable.set(not bool(self.variable.get()))
        if self.command is not None:
            self.command()
        return "break"

    def _draw(self) -> None:
        self.delete("all")
        enabled = bool(self.variable.get())
        width = self.switch_width
        height = self.switch_height
        key = (enabled, tuple(self.colors.items()), width, height)
        if getattr(self, "_image_key", None) != key:
            from PIL import Image, ImageDraw, ImageTk
            light = self.colors["bg"] == "#e0e5ec"
            bright, shadow = ("#ffffff", "#b8bcc2") if light else ("#35485e", "#05080d")
            scale = 3
            image = Image.new("RGB", (width*scale, height*scale), self.colors["surface"])
            draw = ImageDraw.Draw(image)
            draw.rounded_rectangle((1*scale, 1*scale, (width-1)*scale, (height-1)*scale),
                radius=height*scale//2, fill=shadow)
            draw.rounded_rectangle((2*scale, 3*scale, (width-2)*scale, (height-1)*scale),
                radius=height*scale//2, fill=bright)
            draw.rounded_rectangle((2*scale, 3*scale, (width-2)*scale, (height-3)*scale),
                radius=height*scale//2, fill=self.colors["input"])
            x = width-height+3 if enabled else 3
            draw.ellipse(((x+1)*scale, 4*scale, (x+height-4)*scale, (height-2)*scale), fill=shadow)
            draw.ellipse((x*scale, 3*scale, (x+height-6)*scale, (height-3)*scale),
                fill=self.colors["surface_2"], outline=bright, width=scale)
            if enabled:
                cx = (x+(height-6)/2)*scale
                cy = height*scale/2
                draw.ellipse((cx-2*scale, cy-2*scale, cx+2*scale, cy+2*scale), fill=self.colors["accent"])
            self._switch_image = ImageTk.PhotoImage(image.resize((width, height), Image.Resampling.LANCZOS), master=self)
            self._image_key = key
        self.create_image(0, 0, anchor="nw", image=self._switch_image)
        if self.focus_get() == self:
            self.create_rectangle(1, 1, width-1, height-1, outline=self.colors["border_focus"])
