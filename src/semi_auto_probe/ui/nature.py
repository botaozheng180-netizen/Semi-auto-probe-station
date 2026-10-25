"""Nature's UI-only companion. Routes never execute a hardware operation."""
from __future__ import annotations

import json
import time
import tkinter as tk
from collections import deque
from pathlib import Path
from tkinter import ttk
from tkinter import font as tkfont
from .guide_highlight import GuideHighlight
from .nature_walkthrough import build_walkthrough, reveal_control

from PIL import Image, ImageTk, ImageDraw


def keyed_sprite(image, key):
    """Flatten alpha to an exact Windows color key, never blend with magenta.

    Generated atlases contain low, nonzero alpha even in their empty gutters.
    Tk blends those pixels with the canvas, which breaks exact color-key matching.
    Windows color-key windows support binary transparency, so apply the silhouette
    mask after resizing and keep the original RGB of visible character pixels.
    """
    rgba = image.convert("RGBA")
    mask = rgba.getchannel("A").point(lambda alpha: 255 if alpha >= 128 else 0)
    result = Image.new("RGB", rgba.size, key)
    result.paste(rgba.convert("RGB"), (0, 0), mask)
    return result


def circular_portrait(image, transparent):
    """Fit the supplied circular portrait to the complete flat dock button."""
    face = image.convert("RGB").resize((64, 64), Image.Resampling.LANCZOS)
    mask = Image.new("L", (64, 64))
    ImageDraw.Draw(mask).ellipse((0, 0, 63, 63), fill=255)
    result = Image.new("RGB", (72, 72), transparent)
    result.paste(face, (4, 4), mask)
    return result


# Explicit page IDs, completion keys and user-facing instructions are kept together
# so the onboarding workflow can evolve independently of animation playback.
GUIDE = (
    ("autofocus", "AutoFocus", "Adjust Z until the outline is visible.\nThen run AutoFocus."),
    ("plane", "FocusMap", "Set the mapping area and run FocusMap to calibrate the focus plane."),
    ("stitch", "ImgStitch", "Optional: record the die before testing.\nSet the area, then Start."),
    ("layout", "LayoutBond", "Load your layout, match the calibration points, then fit the mapping."),
    ("single", "Main", "Open Instrument in the top bar.\nConfigure and run a single-device test."),
    ("test", "AutoTest", "Review the device list, contact settings and measurement workflow, then run AutoTest."),
)


def workflow_result(app, event):
    """Return (operation, success), only from explicit completion evidence."""
    kind = event[0]
    if kind == "nature_result":
        return event[1], bool(event[2])
    if kind == "af_plane_done":
        if event[1]:  # Cancellation is neither success nor an error bark.
            return None
        return "plane", bool(app.af_plane_model_stored and not app.af_plane_error_active)
    if kind == "imgstitch_done":
        return "stitch", True
    if kind == "imgstitch_error":
        return "stitch", False
    if kind == "autotest_done":
        return ("single" if int(event[1]) == 1 else "test"), int(event[1]) > 0
    if kind in {"autotest_error", "autotest_transport_lost"}:
        return "test", False
    if kind == "mapping_finished":
        if event[1] in {"stopped", "cancelled", "incomplete"} and not event[2]:
            return None
        count = getattr(getattr(app, "mapping_panel", None), "_completed", None)
        return ("single" if count == 1 else "test"), event[1] == "completed" and not event[2]
    return None


class NatureCompanion(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.withdraw()
        self.overrideredirect(True)
        self.transient(app)
        self.dock_key = "#ff00fe"
        self.dock_transparent = app.tk.call("tk", "windowingsystem") == "win32"
        if self.dock_transparent:
            self.wm_attributes("-transparentcolor", self.dock_key)
            self.wm_attributes("-toolwindow", True)
        self.app = app
        self.pose = "sit"
        self.mode = "question"
        self.step = None
        self.stitching_choice = None
        # Each detail resolves its live controls when shown, after page routing.
        self.step_details = build_walkthrough(app)
        self.detail_index = 0
        self.detail_flow_wait = False
        self.detail_flow_seen = False
        self.highlight = GuideHighlight(app)
        self.last_activity = time.monotonic()
        self.jobs = set()
        self.animation_job = None
        self.animating = False
        self.closed = False
        self.minimized = False
        self.drag_origin = None
        self.dragged = False
        self.window_position = None
        self.user_positioned = False
        self.activation_job = None
        self.layout_job = None
        self.repaint_job = None
        self.laying_out = False
        self.prompt_width = 360
        self.prompt_height = 130
        self.results = deque()
        self.assets = Path(__file__).resolve().parents[1] / "assets" / "nature"
        data = json.loads((self.assets / "animations-v5.json").read_text())
        self.moves = {s["name"]: s for s in data["states"]}
        self.transitions = data["transitions"]
        self.photos = {}
        self.atlases = {}
        self.background = app.colors["surface"] if "surface" in app.colors else app.colors["bg"]
        self.configure(bg=self.dock_key if self.dock_transparent else self.background)
        self.canvas = tk.Canvas(self, width=192, height=174,
                                bg=self.dock_key if self.dock_transparent else self.background,
                                bd=0, highlightthickness=0, cursor="hand2", takefocus=True)
        self.canvas.pack()
        self.prompt_canvas = tk.Canvas(self, width=self.prompt_width, height=130, bd=0, highlightthickness=0,
                                       bg=self.dock_key if self.dock_transparent else self.background)
        self.prompt_canvas.pack(fill="x")
        self.body = ttk.Frame(self.prompt_canvas, style="Nature.TFrame")
        # Keep controls as ordinary child windows: embedding them as a Canvas
        # window caused stale clipping when the layered top-level changed size.
        self.body.place(x=12, y=10, width=self.prompt_width-24)
        self.prompt_background = self.prompt_canvas.create_image(0, 0, anchor="nw")
        self.prompt_canvas.tag_lower(self.prompt_background)
        self.body.bind("<Configure>", self.redraw_prompt)
        header = ttk.Frame(self.body, style="Nature.TFrame")
        header.pack(fill="x")
        self.title_label = title = ttk.Label(header, text="Nature - your SAP Companion", cursor="fleur", style="Nature.Title.TLabel")
        title.pack(side="left")
        header.configure(cursor="fleur")
        self.toggle = ttk.Button(header, text="−", width=3, command=self.toggle_visible)
        self.toggle.pack(side="right")
        self.image_item = self.canvas.create_image(96, 87)
        for widget in (header, title, self.canvas):
            widget.bind("<ButtonPress-1>", self.drag_start)
            widget.bind("<B1-Motion>", self.drag_move)
            widget.bind("<ButtonRelease-1>", self.drag_end)
        self.canvas.bind("<Return>", lambda _: self.help())
        self.canvas.bind("<Enter>", self.hover)
        self.message = ttk.Label(self.body, wraplength=280, justify="left", style="Nature.TLabel")
        self.message.pack(fill="x")
        self.choices = ttk.Frame(self.body, style="Nature.TFrame")
        self.choices.pack(fill="x")
        self.dock_window = tk.Toplevel(app, bg=self.dock_key)
        self.dock_window.withdraw()
        self.dock_window.overrideredirect(True)
        self.dock_window.transient(app)
        if self.dock_transparent:
            self.dock_window.wm_attributes("-transparentcolor", self.dock_key)
            self.dock_window.wm_attributes("-toolwindow", True)
        self.dock = tk.Canvas(self.dock_window, width=72, height=72, highlightthickness=0,
                              bd=0, cursor="hand2", takefocus=True)
        self.dock.pack()
        self.dock.bind("<ButtonPress-1>", lambda _: self.draw_dock(True))
        self.dock.bind("<ButtonRelease-1>", self.dock_release)
        self.dock.bind("<Return>", lambda _: self.restore())
        self.dock.bind("<space>", lambda _: self.restore())
        self.dock.bind("<FocusIn>", lambda _: self.draw_dock())
        self.dock.bind("<FocusOut>", lambda _: self.draw_dock())
        self.dock._theme_redraw = self.draw_dock
        self.draw_dock()
        self._theme_redraw = self.refresh_transparency
        self.canvas._theme_redraw = self.refresh_transparency
        self.prompt_canvas._theme_redraw = self.refresh_transparency
        self.refresh_transparency()
        self.bind("<Destroy>", self._destroyed, add="+")
        self.activity_bindings = [(seq, app.bind(seq, self.touch, add="+")) for seq in ("<Motion>", "<ButtonPress>", "<KeyPress>")]
        self.activity_bindings.append(("<Configure>", app.bind("<Configure>", self.keep_in_bounds, add="+")))
        self.activity_bindings.append(("<Unmap>", app.bind("<Unmap>", self.hide_dock, add="+")))
        self.activity_bindings.append(("<Map>", app.bind("<Map>", self.sync_dock, add="+")))
        for seq in ("<FocusIn>", "<Activate>"):
            self.activity_bindings.append((seq, app.bind(seq, self.on_app_activate, add="+")))
        self.bind("<Configure>", self.keep_in_bounds, add="+")
        for seq in ("<Motion>", "<ButtonPress>", "<KeyPress>"):
            self.bind(seq, self.touch, add="+")
        self.draw(self.moves["Welcome"]["frames"][-1])
        self.schedule(800, self.welcome)
        self.schedule(200, self.poll)
        self.schedule(0, self.sync_expanded)

    def refresh_transparency(self):
        background = self.dock_key if self.dock_transparent else self.app.colors["bg"]
        self.configure(bg=background)
        self.canvas.configure(bg=background)
        self.prompt_canvas.configure(bg=background)
        colors = self.app.colors
        base = colors.get("surface", colors["bg"])
        style = ttk.Style(self)
        style.configure("Nature.TFrame", background=base)
        style.configure("Nature.TLabel", background=base, foreground=colors.get("text", "#253348"), font=("Segoe UI", 10))
        style.configure("Nature.Title.TLabel", background=base, foreground=colors.get("muted", "#536278"), font=("Segoe UI", 11))
        button_font = tkfont.Font(root=self, font=style.lookup("TButton", "font") or ("Segoe UI", 10))
        title_font = tkfont.Font(root=self, font=style.lookup("Nature.Title.TLabel", "font"))
        self.prompt_width = max(360, 3*(button_font.measure("Back to Step")+34)+24,
                                title_font.measure("Nature - your SAP Companion")+80)
        self.redraw_prompt()

    def redraw_prompt(self, _event=None):
        if self.closed or self.laying_out or self.layout_job is not None:
            return
        def layout():
            self.jobs.discard(self.layout_job)
            self.layout_job = None
            self.layout_prompt()
        self.layout_job = self.after_idle(layout)
        self.jobs.add(self.layout_job)

    def layout_prompt(self):
        if self.closed or self.laying_out:
            return
        self.laying_out = True
        try:
            width = self.prompt_width
            self.body.place_configure(width=width-24)
            self.body.update_idletasks()
            height = max(60, self.body.winfo_reqheight()+20)
            self.prompt_height = height
            self.body.place_configure(height=height-20)
            key = self.dock_key if self.dock_transparent else self.app.colors["bg"]
            base = self.app.colors.get("surface", self.app.colors["bg"])
            image = Image.new("RGB", (width, height), key)
            ImageDraw.Draw(image).rounded_rectangle((0, 0, width-1, height-1), radius=16, fill=base)
            self.prompt_image = ImageTk.PhotoImage(image, master=self)
            self.prompt_canvas.itemconfigure(self.prompt_background, image=self.prompt_image)
            self.prompt_canvas.configure(width=width, height=height)
            self.sync_expanded()
            if self.repaint_job:
                self.after_cancel(self.repaint_job)
                self.jobs.discard(self.repaint_job)
            self.repaint_job = self.schedule(16, self.repaint_prompt)
        finally:
            self.laying_out = False

    def repaint_prompt(self):
        self.repaint_job = None
        if not self.winfo_ismapped():
            return
        self.prompt_canvas.update_idletasks()
        if self.dock_transparent:
            # Invalidate the layered window AND native child controls after the
            # final geometry settles; no window switching is needed to repaint.
            import ctypes
            from ctypes import wintypes
            redraw = ctypes.windll.user32.RedrawWindow
            redraw.argtypes = (wintypes.HWND, ctypes.c_void_p, wintypes.HANDLE, wintypes.UINT)
            redraw.restype = wintypes.BOOL
            redraw(self.winfo_id(), None, None, 0x0001 | 0x0004 | 0x0080 | 0x0100)

    def schedule(self, ms, callback):
        def run():
            self.jobs.discard(job)
            if not self.closed:
                callback()
        job = self.after(ms, run)
        self.jobs.add(job)
        return job

    def _destroyed(self, event):
        if event.widget is not self:
            return
        self.closed = True
        for job in self.jobs:
            self.after_cancel(job)
        self.jobs.clear()
        self.highlight.destroy()
        self.dock_window.destroy()
        for seq, binding in self.activity_bindings:
            self.app.unbind(seq, binding)

    def touch(self, _event=None):
        self.last_activity = time.monotonic()

    def draw_dock(self, pressed=False):
        colors = self.app.colors
        base = colors.get("bg", "#e0e5ec")
        transparent = self.dock_key if self.dock_transparent else base
        self.dock.configure(bg=transparent)
        self.dock.delete("all")
        with Image.open(self.assets / "nature-portrait.png") as portrait:
            image = circular_portrait(portrait, transparent)
        self.dock_face = ImageTk.PhotoImage(image, master=self.dock)
        self.dock.create_image(36, 36, image=self.dock_face)
        if self.dock.focus_get() is self.dock or pressed:
            self.dock.create_oval(4, 4, 67, 67, outline=colors.get("accent", "#6554d9"), width=2)

    def dock_release(self, event):
        self.draw_dock()
        if (event.x-36)**2 + (event.y-36)**2 <= 32**2:
            self.restore()

    def drag_start(self, event):
        self.touch()
        self.drag_origin = (event.x_root, event.y_root,
                            self.winfo_rootx()-self.app.winfo_rootx(),
                            self.winfo_rooty()-self.app.winfo_rooty())
        self.dragged = False

    def drag_move(self, event):
        if self.drag_origin is None or self.minimized:
            return
        px, py, x, y = self.drag_origin
        dx, dy = event.x_root-px, event.y_root-py
        if not self.dragged and abs(dx)+abs(dy) < 5:
            return
        self.dragged = True
        self.position_at(x+dx, y+dy)
        self.touch()

    def drag_end(self, event):
        clicked = self.drag_origin is not None and not self.dragged
        self.drag_origin = None
        if clicked and event.widget is self.canvas:
            self.help()

    def position_at(self, x, y, *, remember=True):
        width = self.prompt_width
        height = 174+self.prompt_height
        reserved_height = 174+max(240, self.prompt_height)
        x = max(0, min(int(x), max(0, self.app.winfo_width()-width)))
        y = max(0, min(int(y), max(0, self.app.winfo_height()-reserved_height-20)))
        self.window_position = (x, y)
        if remember:
            self.user_positioned = True
        screen_x, screen_y = self.app.winfo_rootx()+x, self.app.winfo_rooty()+y
        geometry = f"{width}x{height}+{screen_x}+{screen_y}"
        if self.geometry() != geometry:
            self.geometry(geometry)

    def sync_expanded(self):
        if self.closed or self.minimized or not self.app.winfo_ismapped():
            return
        if not self.user_positioned or self.window_position is None:
            x = (self.app.winfo_width()-self.prompt_width)//2
            y = self.app.winfo_height()-174-max(240, self.prompt_height)-20
            self.position_at(x, y, remember=False)
        else:
            self.position_at(*self.window_position, remember=False)
        self.deiconify()

    def on_app_activate(self, _event=None):
        """Owned borderless windows can fall behind SAP when it reactivates."""
        if self.closed or self.activation_job is not None:
            return
        def restore_visibility():
            self.activation_job = None
            if not self.app.winfo_ismapped() or self.app.state() in {"withdrawn", "iconic"}:
                return
            # Do not cover a modal dialog while SAP owns an input grab.
            grab = self.app.grab_current()
            if grab is not None and grab.winfo_toplevel() not in (self.app, self, self.dock_window):
                return
            self.sync_dock()
            if not self.minimized:
                self.lift()
        self.activation_job = self.schedule(0, restore_visibility)

    def keep_in_bounds(self, event):
        if event.widget is self.app and self.minimized:
            self.sync_dock()
        if event.widget not in (self.app, self) or self.minimized:
            return
        if self.app.winfo_width() > 1 and self.app.winfo_height() > 1:
            self.sync_expanded()

    def hide_dock(self, event):
        if event.widget is self.app:
            self.highlight.hide()
            self.dock_window.withdraw()
            self.withdraw()

    def sync_dock(self, event=None):
        if event is not None and event.widget is not self.app:
            return
        if not self.minimized:
            self.sync_expanded()
            return
        if self.closed or not self.app.winfo_ismapped():
            return
        x = self.app.winfo_rootx() + max(0, self.app.winfo_width()-86)
        y = self.app.winfo_rooty() + max(0, self.app.winfo_height()-86)
        self.dock_window.geometry(f"72x72+{x}+{y}")
        self.dock_window.deiconify()
        self.dock_window.lift()

    def restore(self):
        if not self.minimized:
            return
        self.minimized = False
        self.dock_window.withdraw()
        self.sync_expanded()
        self.touch()
        if self.mode == "rest":
            self.rest()

    def hardware_busy(self):
        return any(getattr(self.app, flag, False) for flag in (
            "motion_busy", "autofocus_running", "af_plane_running", "imgstitch_running",
            "autotest_running", "mapping_running"))

    def draw(self, frame):
        key = (frame["image"], tuple(frame["rect"]), frame["scale"], frame["lift"])
        if key not in self.photos:
            name = frame["image"]
            if name not in self.atlases:
                with Image.open(self.assets / name) as image:
                    self.atlases[name] = image.convert("RGBA")
            x, y, w, h = frame["rect"]
            sprite = self.atlases[name].crop((x, y, x+w, y+h))
            scale = frame["scale"] * .6
            sprite = sprite.resize((round(w*scale), round(h*scale)), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (192, 174))
            canvas.alpha_composite(sprite, ((192-sprite.width)//2, round(168-frame["lift"]*.6)-sprite.height))
            if self.dock_transparent:
                canvas = keyed_sprite(canvas, self.dock_key)
            self.photos[key] = ImageTk.PhotoImage(canvas, master=self)
        self.canvas.itemconfigure(self.image_item, image=self.photos[key])

    def cancel_animation(self):
        if self.animation_job:
            self.after_cancel(self.animation_job)
            self.jobs.discard(self.animation_job)
        self.animation_job = None
        self.animating = False

    def animate(self, frames, durations, done=lambda: None, index=0):
        if index == 0:
            self.cancel_animation()
        self.animating = True
        self.draw(frames[index])
        def advance():
            self.animation_job = None
            if index+1 < len(frames):
                self.animate(frames, durations, done, index+1)
            else:
                self.animating = False
                done()
        self.animation_job = self.schedule(durations[index], advance)

    def action(self, name, done=lambda: None):
        move = self.moves[name]
        self.animate(move["frames"], [min(t, 400) for t in move["ms"]], done)

    def bridge(self, target, done=lambda: None):
        self.cancel_animation()
        if self.pose == target:
            self.hold(target)
            done()
            return
        if self.pose != "sit" and target != "sit":
            self.bridge("sit", lambda: self.bridge(target, done))
            return
        frames = self.transitions["sitRest" if "rest" in (self.pose, target) else "sitStand"]
        if target == "sit":
            frames = list(reversed(frames))
        def finish():
            self.hold(target)
            done()
        self.animate(frames, [150]*len(frames), finish)

    def hold(self, pose):
        self.pose = pose
        self.draw({"sit": self.moves["Welcome"]["frames"][-1], "stand": self.moves["Guide"]["frames"][0], "rest": self.moves["Waiting"]["frames"][0]}[pose])

    def say(self, message, options=()):
        self.highlight.clear()
        self.detail_flow_wait = False
        self.message.configure(text=message)
        for child in self.choices.winfo_children():
            child.destroy()
        # Three consistent columns; a fourth action occupies a full-width row.
        columns = min(3, max(1, len(options)))
        for column in range(3):
            self.choices.columnconfigure(column, weight=1 if column < columns else 0,
                                         uniform="nature_actions" if column < columns else "")
        for index, (label, command) in enumerate(options):
            if len(options) == 4:
                row, column, span = (0, 0, 3) if index == 0 else (1, index-1, 1)
            else:
                row, column, span = index//columns, index % columns, 1
            ttk.Button(self.choices, text=label, width=0, command=command).grid(
                row=row, column=column, columnspan=span, sticky="ew", padx=2, pady=4)
        self.touch()
        self.redraw_prompt()

    def welcome(self):
        if self.hardware_busy() or self.minimized:
            return
        self.mode = "question"
        self.bridge("sit", lambda: self.action("Welcome", self.ask_new))

    def hover(self, _event):
        if self.mode in {"idle", "rest"} and not self.hardware_busy():
            self.welcome()

    def ask_new(self):
        self.hold("sit")
        self.say("New user?", (("✔ Yes", self.offer_tour), ("❌ No", lambda: self.idle("Good to have you back! Have a nice Test~"))))

    def offer_tour(self):
        self.say("Want me to guide you through?", (("✔ Yes", self.start_tour), ("❌ No", lambda: self.idle("Click me whenever you need help."))))

    def idle(self, text):
        self.mode = "idle"
        self.step = None
        self.say(text)

    def start_tour(self):
        self.step = 0
        self.stitching_choice = None
        self.guide()

    def choose_stitching(self, include):
        self.stitching_choice = include
        if include:
            self.guide()
        else:
            self.mode = "watch"
            self.next_step()

    def guide_options(self):
        options = [("Step Detail", self.step_detail), ("Next Step", self.next_step)]
        if self.step is not None and GUIDE[self.step][0] == "single":
            options.insert(0, ("Open Instrument", self.app._show_instrument))
        options.append(("End Guide", lambda: self.idle("Click me whenever you need help.")))
        return options

    def step_detail(self):
        if self.step is None or self.mode != "watch" or self.animating:
            return
        self.detail_index = 0
        self.show_step_detail()

    def show_step_detail(self):
        if self.step is None:
            return
        self.mode = "detail"
        operation = GUIDE[self.step][0]
        if operation == "layout" and self.detail_index >= 2:
            panel = self.app.gds_stage_mapper_panel
            if not panel.calibration_expanded_var.get():
                panel.calibration_expanded_var.set(True)
                panel._update_calibration_section_visibility()
        if operation == "test" and self.detail_index == 3:
            panel = self.app.autotest_panel
            if not panel.approach_expanded_var.get():
                self.detail_index += 1
        details = self.step_details.get(operation, ())
        options = [("Back to Step", self.guide),
                   ("End Guide", lambda: self.idle("Click me whenever you need help."))]
        if not details:
            self.say("The detailed walkthrough for this step is being prepared. You can return to the step overview for now.", options)
            return
        if self.detail_index >= len(details):
            self.guide()
            return
        detail = details[self.detail_index]
        text, resolve_target = detail[:2]
        self.say(text, [("Next Step", self.advance_detail)] + options)
        try:
            target = resolve_target()
            for widget in target if isinstance(target, (list, tuple)) else [target]:
                reveal_control(widget)
            self.highlight.show(target)
        except (LookupError, StopIteration, KeyError, AttributeError, tk.TclError):
            self.message.configure(text="This control is unavailable in the current view. Return to the step and check its settings.")
            return
        if len(detail) > 2 and detail[2] == "flow_dialog":
            self.detail_flow_wait = True
            self.detail_flow_seen = False
            self.choices.winfo_children()[0].configure(state="disabled")

    def advance_detail(self):
        if self.mode != "detail" or self.detail_flow_wait or self.hardware_busy():
            return
        self.detail_index += 1
        details = self.step_details.get(GUIDE[self.step][0], ())
        if self.detail_index >= len(details):
            self.mode = "watch"
            self.next_step()
        else:
            self.show_step_detail()

    def poll_detail_dialog(self):
        if self.mode != "detail" or not self.detail_flow_wait:
            return
        dialog = getattr(self.app.autotest_panel, "_measurement_dialog", None)
        try:
            opened = dialog is not None and dialog.winfo_exists() and dialog.state() != "withdrawn"
        except tk.TclError:
            opened = False
        if opened:
            self.detail_flow_seen = True
            self.highlight.hide()
        elif self.detail_flow_seen:
            self.detail_flow_wait = False
            self.advance_detail()

    def next_step(self):
        """Browse the next guide stage without executing or completing a task."""
        if self.step is None or self.mode != "watch" or self.animating:
            return
        if self.hardware_busy():
            self.say("Wait for the current operation to finish before moving to the next step.",
                     (("Next Step", self.next_step),))
            return
        self.step += 1
        if self.step >= len(GUIDE):
            self.idle("That’s the end of the guide! Have a nice Test~")
        else:
            self.guide()

    def guide(self):
        if self.step is None:
            return
        if self.hardware_busy():
            self.mode = "watch"
            self.say("I’ll wait for the current operation to finish.", (("Continue guide", self.guide),))
            return
        operation, page, text = GUIDE[self.step]
        if operation == "stitch" and self.stitching_choice is None:
            self.mode = "question"
            self.bridge("sit", lambda: self.say(
                "Record the die before electrical testing?\nStitching is optional.",
                (("Record surface", lambda: self.choose_stitching(True)),
                 ("Skip stitching", lambda: self.choose_stitching(False)))))
            return
        self.mode = "guide"
        self.app.show_page(page)
        self.lift()
        self.say(text)
        def watch():
            self.mode = "watch"
            self.say(text, self.guide_options())
        self.bridge("stand", lambda: self.action("Guide", lambda: self.bridge("sit", watch)))

    def observe(self, event):
        result = workflow_result(self.app, event)
        if result is not None:
            self.results.append(result)

    def feedback(self, operation, success):
        self.mode = "feedback"
        self.say("Well done!" if success else "Something needs checking. Review the operation status before retrying.")
        def finish():
            self.pose = "sit" if success else "stand"
            def seated():
                expected = GUIDE[self.step][0] if self.step is not None else None
                matches = expected == operation or (expected == "test" and operation == "single") or (expected == "single" and operation == "test" and not success)
                if self.step is not None and matches:
                    if not success and operation == "autofocus":
                        self.app.show_page("AutoFocus")
                        self.mode = "watch"
                        self.step_detail()
                        return
                    if success:
                        self.step += 1
                    if self.step < len(GUIDE):
                        self.guide()
                    else:
                        self.idle("You’ve finished the guide! Have a nice Test~")
                elif self.step is not None:
                    self.mode = "watch"
                    self.say(GUIDE[self.step][2], self.guide_options())
                else:
                    self.idle("Well done!" if success else "Please check the operation status. I’m here if you need help.")
            self.bridge("sit", seated)
        self.bridge("stand", lambda: self.action("Success" if success else "Attention", finish))

    def help(self):
        if self.mode in {"thinking", "feedback"}:
            return
        self.mode = "help"
        def prompt():
            self.say("How can I help you?")
            entry = ttk.Entry(self.choices, width=23)
            for column in range(3):
                self.choices.columnconfigure(column, weight=1, uniform="nature_actions")
            entry.grid(row=0, column=0, columnspan=3, sticky="ew", padx=2, pady=(0, 4))
            def send():
                text = entry.get().strip()
                if text and self.app.agent_panel.submit_question(text):
                    self.app.show_page("AI Agent")
                    self.lift()
                    self.mode = "thinking"
                    self.say("Thinking… Your answer will appear in AI Agent.")
                    self.think()
                elif text:
                    self.message.configure(text="The AI Agent is busy. Please wait for its current request.")
            ttk.Button(self.choices, text="Send", width=0, command=send).grid(row=1, column=0, sticky="ew", padx=2, pady=4)
            ttk.Button(self.choices, text="Guide", width=0, command=self.start_tour).grid(row=1, column=1, sticky="ew", padx=2, pady=4)
            ttk.Button(self.choices, text="Close", width=0, command=lambda: self.guide() if self.step is not None else self.idle("Click me whenever you need help.")).grid(row=1, column=2, sticky="ew", padx=2, pady=4)
            entry.bind("<Return>", lambda _: send())
            entry.focus_set()
            self.redraw_prompt()
        self.bridge("sit", prompt)

    def think(self):
        if self.mode == "thinking":
            self.action("Thinking", self.think)

    def rest(self):
        if self.mode == "rest" and not self.minimized:
            m = self.moves["Waiting"]
            self.animate(m["frames"], m["ms"], self.rest)

    def toggle_visible(self):
        if self.minimized:
            self.restore()
            return
        self.minimized = True
        self.highlight.hide()
        self.withdraw()
        # Let one-shot callbacks finish so folding cannot lose a result.
        if self.mode == "rest":
            self.cancel_animation()
        self.draw_dock()
        self.sync_dock()
        self.touch()

    def poll(self):
        self.poll_detail_dialog()
        if not self.minimized and self.app.winfo_ismapped() and not (self.detail_flow_wait and self.detail_flow_seen):
            self.highlight.refresh()
        else:
            self.highlight.hide()
        if self.mode == "thinking" and self.app.agent_panel.phase_var.get() != "Planning":
            self.cancel_animation()
            self.hold("sit")
            self.mode = "help"
            self.say("Your response is in AI Agent.", (("Open answer", lambda: self.app.show_page("AI Agent")), ("Continue", self.guide if self.step is not None else lambda: self.idle("Click me whenever you need help."))))
        if not self.minimized and not self.hardware_busy():
            if self.results and not self.animating and self.mode not in {"thinking", "help", "question"}:
                self.feedback(*self.results.popleft())
            elif self.mode == "idle" and not self.animating and time.monotonic()-self.last_activity >= 10:
                self.mode = "rest"
                self.bridge("rest", self.rest)
        self.schedule(200, self.poll)
