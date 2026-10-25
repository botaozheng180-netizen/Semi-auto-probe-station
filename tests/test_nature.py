import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from semi_auto_probe.ui.nature import GUIDE, NatureCompanion, workflow_result, circular_portrait, keyed_sprite
from PIL import Image
from semi_auto_probe.ui.agent_panel import AgentPanel


class NatureResultTests(unittest.TestCase):
    def test_partial_alpha_gutters_become_exact_transparent_key(self):
        image = Image.new("RGBA", (4, 1))
        image.putdata([(90, 60, 40, 5), (90, 60, 40, 40), (200, 100, 50, 253), (255, 255, 255, 254)])
        rendered = keyed_sprite(image, "#ff00fe")
        self.assertEqual([rendered.getpixel((x, 0)) for x in range(4)], [(255, 0, 254), (255, 0, 254), (200, 100, 50), (255, 255, 255)])

    def test_flat_portrait_fills_circle_without_square_corners(self):
        image = circular_portrait(Image.new("RGB", (460, 460), "white"), "#ff00fe")
        for point in ((0, 0), (71, 0), (0, 71), (71, 71), (4, 4)):
            self.assertEqual(image.getpixel(point), (255, 0, 254))
        for point in ((36, 4), (36, 36), (4, 36), (67, 36)):
            self.assertEqual(image.getpixel(point), (255, 255, 255))

    def test_question_submission_is_conversation_only_and_busy_safe(self):
        from unittest.mock import Mock
        panel = SimpleNamespace(active_run_id="", phase_var=Mock(), planning_thread=None,
                                permission_mode_var=Mock(), input_text=Mock(), generate_plan=Mock(),
                                MODE_CHAT=AgentPanel.MODE_CHAT)
        panel.phase_var.get.return_value = "Idle"
        self.assertTrue(AgentPanel.submit_question(panel, "How do I focus?"))
        panel.permission_mode_var.set.assert_called_once_with(AgentPanel.MODE_CHAT)
        panel.generate_plan.assert_called_once()
        panel.active_run_id = "active-operation"
        self.assertFalse(AgentPanel.submit_question(panel, "Another question"))
        panel.generate_plan.assert_called_once()

    def test_only_explicit_success_advances(self):
        app = SimpleNamespace(af_plane_model_stored=True, af_plane_error_active=False)
        self.assertIsNone(workflow_result(app, ("autofocus_done",)))
        self.assertIsNone(workflow_result(app, ("autofocus_status", "Done")))
        self.assertIsNone(workflow_result(app, ("af_plane_done", True)))
        self.assertEqual(workflow_result(app, ("af_plane_done", False)), ("plane", True))
        app.af_plane_error_active = True
        self.assertEqual(workflow_result(app, ("af_plane_done", False)), ("plane", False))
        self.assertIsNone(workflow_result(app, ("mapping_finished", "cancelled", None, None)))
        self.assertEqual(workflow_result(app, ("mapping_finished", "completed", "write failed", None)), ("test", False))
        self.assertEqual(workflow_result(app, ("autotest_done", 1)), ("single", True))
        self.assertEqual(workflow_result(app, ("autotest_done", 5)), ("test", True))


class NatureUITests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.colors = {"bg": "#ffffff"}
        self.pages = []
        self.root.show_page = self.pages.append
        from unittest.mock import Mock
        self.root._show_instrument = Mock()
        self.root.agent_panel = SimpleNamespace(phase_var=tk.StringVar(self.root, value="Idle"))
        self.pet = NatureCompanion(self.root)

    def tearDown(self):
        self.root.update_idletasks()
        self.pet.destroy()
        self.assertFalse(self.pet.jobs)
        self.root.destroy()

    def instant(self, frames, durations, done=lambda: None, index=0):
        self.pet.draw(frames[-1])
        done()

    def test_all_packaged_frames_render(self):
        for move in self.pet.moves.values():
            self.assertEqual(len(move["frames"]), 8)
            for frame in move["frames"]:
                self.pet.draw(frame)

        for frames in self.pet.transitions.values():
            for frame in frames:
                self.pet.draw(frame)

    def test_short_autofocus_and_stitch_overviews_fit_two_lines(self):
        from tkinter import font, ttk
        text_font = font.Font(root=self.root, font=ttk.Style(self.root).lookup("Nature.TLabel", "font"))
        for operation, _, text in GUIDE:
            if operation in {"autofocus", "stitch", "single"}:
                self.assertLessEqual(len(text.splitlines()), 2)
                for line in text.splitlines():
                    self.assertLessEqual(text_font.measure(line), 280)

    def test_guide_routes_only_matching_results_and_retries(self):
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            self.assertEqual(self.pages, ["AutoFocus"])
            self.assertEqual(self.pet.pose, "sit")
            self.pet.feedback("stitch", True)
            self.assertEqual(self.pet.step, 0)
            self.pet.feedback("autofocus", False)
            self.assertEqual(self.pet.step, 0)
            for key, _, _ in GUIDE:
                self.pet.feedback(key, True)
            self.assertIsNone(self.pet.step)
            self.assertEqual(self.pet.mode, "idle")
            self.assertEqual(self.pet.pose, "sit")

    def test_idle_gate_and_click_wakes_to_help(self):
        self.pet.last_activity = -100
        self.pet.mode = "question"
        with patch.object(self.pet, "bridge") as bridge:
            self.pet.poll()
            bridge.assert_not_called()
            self.pet.mode = "idle"
            self.root.motion_busy = True
            self.pet.poll()
            bridge.assert_not_called()
            self.root.motion_busy = False
            self.pet.poll()
            bridge.assert_called_once()
        self.pet.pose = "rest"
        with patch.object(self.pet, "animate", self.instant):
            self.pet.help()
        self.assertEqual(self.pet.pose, "sit")
        self.assertEqual(self.pet.mode, "help")

    def test_next_step_browses_guide_and_finishes_without_operation(self):
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            button = self.pet.choices.winfo_children()[1]
            self.assertEqual(button.cget("text"), "Next Step")
            button.invoke()
            self.assertEqual(self.pet.step, 1)
            self.assertEqual(self.pages[-1], "FocusMap")
            self.root.motion_busy = True
            self.pet.next_step()
            self.assertEqual(self.pet.step, 1)
            self.root.motion_busy = False
            for _ in range(len(GUIDE)-1):
                if self.pet.mode == "question":
                    self.pet.choose_stitching(False)
                    continue
                self.pet.next_step()
            self.assertIsNone(self.pet.step)
            self.assertEqual(self.pet.mode, "idle")
            self.assertEqual(self.pet.pose, "sit")

    def test_optional_stitching_can_skip_without_opening_capture_page(self):
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            self.pet.next_step()
            self.pet.next_step()
            self.assertEqual(self.pet.mode, "question")
            self.assertNotIn("ImgStitch", self.pages)
            self.pet.choices.winfo_children()[1].invoke()
            self.assertEqual(self.pages[-1], "LayoutBond")
            self.pet.next_step()
            self.assertEqual(GUIDE[self.pet.step][0], "single")
            self.assertIn("Instrument in the top bar", self.pet.message.cget("text"))
            self.pet.choices.winfo_children()[0].invoke()
            self.root._show_instrument.assert_called_once()

    def test_detail_scaffold_preserves_stage_and_can_return_to_overview(self):
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            buttons = self.pet.choices.winfo_children()
            self.assertEqual([b.cget("text") for b in buttons], ["Step Detail", "Next Step", "End Guide"])
            buttons[0].invoke()
            self.assertEqual(self.pet.mode, "detail")
            self.assertEqual(self.pet.step, 0)
            self.assertIsNone(self.pet.highlight.target)
            self.pet.choices.winfo_children()[1].invoke()
            self.assertEqual(self.pet.mode, "watch")
            self.assertEqual(self.pet.step, 0)

    def test_detail_targets_highlight_without_invoking_controls_and_cleans_up(self):
        from tkinter import ttk
        from unittest.mock import Mock
        command = Mock()
        target = ttk.Button(self.root, text="Target", command=command)
        self.pet.step_details["autofocus"] = [("First instruction", lambda: target),
                                                ("Second instruction", lambda: self.pet.toggle)]
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            self.pet.step_detail()
            self.assertIs(self.pet.highlight.target, target)
            command.assert_not_called()
            self.pet.choices.winfo_children()[0].invoke()
            self.assertIs(self.pet.highlight.target, self.pet.toggle)
            self.pet.choices.winfo_children()[-1].invoke()
            self.assertIsNone(self.pet.highlight.target)
            self.assertIsNone(self.pet.step)

    def test_autofocus_failure_resets_detail_to_coarse_adjustment(self):
        self.pet.step_details["autofocus"] = [
            ("Adjust Z", lambda: [self.pet.toggle, self.pet.canvas]),
            ("Start Auto", lambda: self.pet.toggle)]
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            self.pet.step_detail()
            self.pet.advance_detail()
            self.assertEqual(self.pet.detail_index, 1)
            self.pet.feedback("autofocus", False)
            self.assertEqual(self.pet.step, 0)
            self.assertEqual(self.pet.detail_index, 0)
            self.assertEqual(self.pet.mode, "detail")
            self.assertEqual(self.pet.highlight.target, [self.pet.toggle, self.pet.canvas])

    def test_flow_dialog_must_open_and_close_before_run_highlight(self):
        from unittest.mock import Mock
        dialog = Mock()
        dialog.winfo_exists.return_value = True
        dialog.state.return_value = "normal"
        self.root.autotest_panel = SimpleNamespace(_measurement_dialog=None)
        self.pet.step = len(GUIDE)-1
        self.pet.step_details["test"] = [("Configure flow", lambda: self.pet.toggle, "flow_dialog"),
                                         ("Run AutoTest", lambda: self.pet.canvas)]
        self.pet.show_step_detail()
        self.assertTrue(self.pet.detail_flow_wait)
        self.pet.advance_detail()
        self.assertEqual(self.pet.detail_index, 0)
        self.pet.poll_detail_dialog()
        self.assertEqual(self.pet.detail_index, 0)
        self.root.autotest_panel._measurement_dialog = dialog
        self.pet.poll_detail_dialog()
        self.assertTrue(self.pet.detail_flow_seen)
        dialog.winfo_exists.return_value = False
        self.pet.poll_detail_dialog()
        self.assertEqual(self.pet.detail_index, 1)
        self.assertIs(self.pet.highlight.target, self.pet.canvas)

    def test_optional_stitching_can_be_selected_before_layout(self):
        with patch.object(self.pet, "animate", self.instant):
            self.pet.start_tour()
            self.pet.next_step()
            self.pet.next_step()
            self.pet.choices.winfo_children()[0].invoke()
            self.assertEqual(self.pages[-1], "ImgStitch")
            self.assertEqual(self.pet.mode, "watch")
            self.assertIn("Optional:", self.pet.message.cget("text"))
            self.pet.feedback("stitch", True)
            self.assertEqual(self.pages[-1], "LayoutBond")

    def test_minimize_preserves_one_shot_completion(self):
        self.pet.action("Welcome")
        job = self.pet.animation_job
        self.pet.toggle_visible()
        self.assertIn(job, self.pet.jobs)
        self.assertTrue(self.pet.animating)

    def test_fold_is_bottom_right_circle_and_restores_conversation(self):
        self.pet.say("Keep this question", (("Yes", lambda: None),))
        self.pet.window_position = (100, 80)
        self.pet.toggle_visible()
        self.assertEqual(self.pet.state(), "withdrawn")
        with patch.object(self.root, "winfo_ismapped", return_value=True), \
             patch.object(self.root, "winfo_rootx", return_value=100), \
             patch.object(self.root, "winfo_rooty", return_value=200), \
             patch.object(self.root, "winfo_width", return_value=900), \
             patch.object(self.root, "winfo_height", return_value=700), \
             patch.object(self.pet.dock_window, "geometry") as geometry, \
             patch.object(self.pet.dock_window, "deiconify"), \
             patch.object(self.pet.dock_window, "lift"):
            self.pet.sync_dock()
            geometry.assert_called_once_with("72x72+914+814")
        with patch.object(self.pet, "sync_expanded") as sync:
            self.pet.restore()
            sync.assert_called_once()
        self.assertEqual(self.pet.window_position, (100, 80))
        self.assertEqual(self.pet.dock_window.state(), "withdrawn")
        self.assertEqual(self.pet.message.cget("text"), "Keep this question")
        self.assertEqual(len(self.pet.choices.winfo_children()), 1)

    def test_expanded_pet_has_transparent_area_above_prompt_and_fold(self):
        self.assertIsInstance(self.pet, tk.Toplevel)
        self.assertTrue(self.pet.overrideredirect())
        self.assertEqual(self.pet.pack_slaves(), [self.pet.canvas, self.pet.prompt_canvas])
        self.assertIs(self.pet.message.master, self.pet.body)
        self.assertEqual(self.pet.title_label.cget("text"), "Nature - your SAP Companion")
        self.pet.redraw_prompt()
        self.root.update_idletasks()
        from PIL import ImageTk
        panel = ImageTk.getimage(self.pet.prompt_image)
        self.assertEqual(panel.getpixel((0, 0))[:3], (255, 0, 254))
        self.assertIs(self.pet.toggle.master.master, self.pet.body)
        if self.pet.dock_transparent:
            self.assertEqual(self.pet.wm_attributes("-transparentcolor"), self.pet.dock_key)
            self.assertEqual(self.pet.canvas.cget("background"), self.pet.dock_key)
        self.pet.refresh_transparency()
        self.pet.hide_dock(SimpleNamespace(widget=self.root))
        self.assertEqual(self.pet.state(), "withdrawn")

    def test_drag_does_not_trigger_help_and_position_is_clamped(self):
        press = SimpleNamespace(x_root=100, y_root=100, widget=self.pet.canvas)
        move = SimpleNamespace(x_root=140, y_root=150, widget=self.pet.canvas)
        with patch.object(self.pet, "position_at") as position, patch.object(self.pet, "help") as help_call:
            self.pet.drag_start(press)
            self.pet.drag_move(move)
            self.pet.drag_end(move)
            position.assert_called_once()
            help_call.assert_not_called()
            self.pet.drag_start(press)
            self.pet.drag_end(press)
            help_call.assert_called_once()
        with patch.object(self.root, "winfo_width", return_value=900), patch.object(self.root, "winfo_height", return_value=700):
            self.pet.position_at(-100, -100)
            self.assertEqual(self.pet.window_position, (0, 0))
            self.pet.position_at(10000, 10000)
            x, y = self.pet.window_position
            self.assertLess(x, 900)
            self.assertLess(y, 700)

    def test_default_is_bottom_center_and_drag_overrides_default(self):
        with patch.object(self.root, "winfo_ismapped", return_value=True), \
             patch.object(self.root, "winfo_width", return_value=1000), \
             patch.object(self.root, "winfo_height", return_value=800), \
             patch.object(self.pet, "winfo_reqwidth", return_value=330), \
             patch.object(self.pet, "winfo_reqheight", return_value=300), \
             patch.object(self.pet, "deiconify"):
            self.pet.sync_expanded()
            self.assertEqual(self.pet.window_position, ((1000-self.pet.prompt_width)//2, 366))
            self.assertFalse(self.pet.user_positioned)
            self.pet.position_at(100, 150)
            self.pet.sync_expanded()
            self.assertEqual(self.pet.window_position, (100, 150))

    def test_reactivation_restores_expanded_or_folded_window(self):
        callbacks = []
        def schedule(ms, callback):
            callbacks.append(callback)
            return "activation"
        with patch.object(self.pet, "schedule", schedule), \
             patch.object(self.root, "winfo_ismapped", return_value=True), \
             patch.object(self.root, "state", return_value="normal"), \
             patch.object(self.pet, "sync_dock") as sync, \
             patch.object(self.pet, "lift") as lift:
            self.pet.on_app_activate()
            self.pet.on_app_activate()
            self.assertEqual(len(callbacks), 1)
            callbacks.pop()()
            sync.assert_called_once()
            lift.assert_called_once()
            sync.reset_mock()
            lift.reset_mock()
            self.pet.minimized = True
            self.pet.on_app_activate()
            callbacks.pop()()
            sync.assert_called_once()
            lift.assert_not_called()

    def test_companion_title_is_only_one_point_larger_than_prompt(self):
        from tkinter import ttk, font
        style = ttk.Style(self.root)
        title = font.Font(root=self.root, font=style.lookup("Nature.Title.TLabel", "font"))
        prompt = font.Font(root=self.root, font=style.lookup("Nature.TLabel", "font"))
        self.assertEqual(title.actual("size"), prompt.actual("size")+1)

    def test_prompt_relayouts_short_long_four_buttons_and_help_at_fixed_width(self):
        from PIL import ImageTk
        width = self.pet.prompt_width
        variants = [
            (GUIDE[0][2], ["Step Detail", "Next Step", "End Guide"]),
            (GUIDE[4][2], ["Open Instrument", "Step Detail", "Next Step", "End Guide"]),
            ("P1: click GDS Pick, then double-click the matching mark in the layout.",
             ["Next Step", "Back to Step", "End Guide"]),
            ("Ready.", ["Next Step", "End Guide"]),
        ]
        for text, labels in variants*3:
            self.pet.say(text, [(label, lambda: None) for label in labels])
            self.root.update_idletasks()
            self.assertIsNone(self.pet.layout_job)
            self.assertEqual(self.pet.prompt_width, width)
            self.assertEqual(ImageTk.getimage(self.pet.prompt_image).width, width)
            self.assertEqual(self.pet.prompt_height, self.pet.body.winfo_reqheight()+20)
            for button in self.pet.choices.winfo_children():
                self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth())
                self.assertLessEqual(button.winfo_x()+button.winfo_width(), width-24)
        with patch.object(self.pet, "animate", self.instant):
            self.pet.help()
        self.root.update_idletasks()
        self.assertEqual(self.pet.prompt_width, width)
        self.assertEqual(ImageTk.getimage(self.pet.prompt_image).height, self.pet.prompt_height)

    def test_prompt_height_changes_keep_character_anchor_and_fit_app(self):
        with patch.object(self.root, "winfo_ismapped", return_value=True), \
             patch.object(self.root, "winfo_width", return_value=1000), \
             patch.object(self.root, "winfo_height", return_value=700), \
             patch.object(self.pet, "deiconify"):
            anchor = None
            for text, count in (("Ready.", 2), (GUIDE[4][2], 4), ("Ready again.", 3)):
                self.pet.say(text, [("Next Step", lambda: None)]*count)
                self.root.update_idletasks()
                if anchor is None:
                    anchor = self.pet.window_position
                self.assertEqual(self.pet.window_position, anchor)
                self.assertLessEqual(anchor[1]+174+self.pet.prompt_height, 680)


if __name__ == "__main__":
    unittest.main()
