"""Normal-weight tab icons, rendered separately from bold button captions."""
import os
from pathlib import Path
from tkinter import font as tkfont

from PIL import Image, ImageDraw, ImageFont, ImageTk


def install_navigation_icon(button, glyph, colors):
    root = button.winfo_toplevel()
    font = tkfont.Font(root=root, family="Segoe UI Emoji", size=12, weight="normal")
    pixel_size = max(1, round(12 * float(root.tk.call("tk", "scaling"))))
    try:
        icon_font = ImageFont.truetype(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / "seguiemj.ttf"), pixel_size)
    except OSError:
        # Keep non-Windows installations usable when Segoe UI is unavailable.
        icon_font = ImageFont.truetype("DejaVuSans.ttf", pixel_size)
    bounds = icon_font.getbbox(glyph)
    height = font.metrics("linespace")
    width = max(1, bounds[2] - bounds[0]) + 4
    cache = getattr(root, "_navigation_icon_cache", {})
    root._navigation_icon_cache = cache

    def refresh():
        images = []
        for color in (colors["muted"], colors["muted"], colors["accent"], colors["text"]):
            key = (glyph, pixel_size, height, color)
            if key not in cache:
                bitmap = Image.new("RGBA", (width, height))
                ImageDraw.Draw(bitmap).text((-bounds[0], (height - (bounds[3] - bounds[1])) // 2 - bounds[1]),
                                            glyph, font=icon_font, fill=color)
                cache[key] = ImageTk.PhotoImage(bitmap, master=root)
            images.append(cache[key])
        button._navigation_images = images
        button.configure(image=(images[0], "disabled", images[1], "selected", images[2], "active", images[3]),
                         compound="left")

    button._theme_redraw = refresh
    refresh()
