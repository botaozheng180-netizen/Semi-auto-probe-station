"""Resolve Nature's detailed guide against the live controls on each page."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .panel_scrolling import ScrollablePanel


def descendants(root):
    for child in root.winfo_children():
        yield child
        yield from descendants(child)


def find_control(root, *, text=None, variable=None, index=0):
    matches = []
    for widget in descendants(root):
        if text is not None and not isinstance(widget, (ttk.Button, tk.Button, ttk.Combobox)):
            continue
        try:
            if text is not None and str(widget.cget("text")) != text:
                continue
            if variable is not None and str(widget.cget("textvariable")) != str(variable):
                continue
            matches.append(widget)
        except tk.TclError:
            continue
    if len(matches) <= index:
        raise LookupError(f"Guide control is unavailable: {text or variable}")
    return matches[index]


def reveal_control(widget):
    """Scroll the containing sidebar to the actual highlighted control."""
    widget.update_idletasks()
    parent = widget.master
    while parent is not None:
        if isinstance(parent, ScrollablePanel):
            canvas = parent.canvas
            bounds = canvas.bbox("all")
            if bounds:
                top = widget.winfo_rooty()-canvas.winfo_rooty()
                bottom = top+widget.winfo_height()
                if top < 4 or bottom > canvas.winfo_height()-4:
                    canvas.yview_moveto((canvas.canvasy(0)+top-12)/max(1, bounds[3]-bounds[1]))
                    widget.update_idletasks()
        parent = parent.master


def build_walkthrough(app):
    def button(page, text, index=0):
        return lambda: find_control(app.pages[page], text=text, index=index)

    def field(variable):
        return lambda: find_control(app.pages["ImgStitch"], variable=getattr(app, variable))

    def stage_pick(name):
        gds = app.gds_stage_mapper_panel.gds_point_buttons[name]
        row = int(gds.grid_info()["row"])
        return gds.master.grid_slaves(row=row, column=6)[0]

    layout = [("Load the die layout with Load GDS.", button("LayoutBond", "Load GDS")),
              ("Choose the calibration mark cell in Top cell.", lambda: app.gds_stage_mapper_panel.top_cell_combo)]
    for name in ("P1", "P2", "P3", "P4"):
        key = name
        layout.extend([
            (f"{name}: click GDS Pick, then double-click the matching mark in the layout.",
             lambda key=key: app.gds_stage_mapper_panel.gds_point_buttons[key]),
            (f"{name}: align the same mark in the microscope, then click Stage Pick.",
             lambda key=key: stage_pick(key)),
        ])
    layout.append(("Click Fit / Update Mapping to calibrate the layout.", button("LayoutBond", "Fit / Update Mapping")))
    return {
        "autofocus": [
            ("Adjust Z− / Z+ until the device outline is visible.",
             lambda: [button("AutoFocus", "Z-")(), button("AutoFocus", "Z+")()]),
            ("Click Start Auto to refine the focus.", button("AutoFocus", "Start Auto")),
        ],
        "plane": [
            ("Click Generate Mesh to prepare the focus points.", button("FocusMap", "Generate Mesh")),
            ("Click Start FocusMap to calibrate the focus plane.", button("FocusMap", "Start FocusMap")),
        ],
        "stitch": [
            ("Set Rows and Cols to choose the stitching area.",
             lambda: [field("imgstitch_rows_var")(), field("imgstitch_cols_var")()]),
            ("Enable FocusMap plane Z to use the calibrated plane.",
             lambda: next(w for w in descendants(app.pages["ImgStitch"])
                          if w.winfo_class() == "Canvas" and getattr(w, "variable", None) is app.imgstitch_focusmap_plane_var)),
            ("Click Start to record the die surface.", button("ImgStitch", "Start")),
        ],
        "layout": layout,
        "test": [
            ("Click Origin Pick, then select the first device in the layout.", lambda: find_control(app.autotest_panel.frame, text="Pick", index=0)),
            ("Click vi Pick to set the column direction and spacing.", lambda: find_control(app.autotest_panel.frame, text="Pick", index=1)),
            ("Click vj Pick to set the row direction and spacing.", lambda: find_control(app.autotest_panel.frame, text="Pick", index=2)),
            ("Click Collapse to hide the wobble settings.", lambda: app.autotest_panel.approach_toggle_button),
            ("Click Config Measure Flow. Configure the workflow, then close that window.",
             lambda: app.autotest_panel.measurement_button, "flow_dialog"),
            ("Review the region and workflow, then click Run AutoTest.", lambda: app.autotest_panel.run_button),
        ],
    }
