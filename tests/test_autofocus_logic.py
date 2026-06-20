from __future__ import annotations

import queue
import threading
import unittest
from unittest import mock

from semi_auto_probe.app import ProbeApp
from semi_auto_probe.config import (
    AUTOFOCUS_PEAK_MODEL_LORENTZIAN,
    AUTOFOCUS_PEAK_MODEL_PARABOLIC,
    AUTOFOCUS_PEAK_MODEL_PSEUDO_VOIGT,
    ProbeConfig,
)


class DummyVar:
    def __init__(self, value: str = "") -> None:
        self.value = value

    def get(self) -> str:
        return self.value

    def set(self, value: str) -> None:
        self.value = value


class AutoFocusLogicTests(unittest.TestCase):
    def test_coarse_wobble_uses_initial_step(self) -> None:
        self.assertEqual(
            ProbeApp._coarse_wobble_offsets(initial_step=50, search_range=120),
            [50, -50, 100, -100, 120, -120],
        )

    def test_fine_scan_is_single_direction_min_step(self) -> None:
        self.assertEqual(
            ProbeApp._fine_scan_positions(start_z=90, end_z=106, step=5),
            [90, 95, 100, 105, 106],
        )

    def test_fine_scan_bounds_stay_near_coarse_peak_center(self) -> None:
        self.assertEqual(
            ProbeApp._fine_scan_bounds(
                best_z=1000,
                initial_step=50,
                min_step=2,
                lower_bound=800,
                upper_bound=1200,
            ),
            (950, 1050),
        )

    def test_fine_scan_bounds_keep_minimum_min_step_window(self) -> None:
        self.assertEqual(
            ProbeApp._fine_scan_bounds(
                best_z=1000,
                initial_step=10,
                min_step=3,
                lower_bound=990,
                upper_bound=1008,
            ),
            (990, 1008),
        )

    def test_fine_scan_bounds_cover_at_least_eight_min_steps_each_side(self) -> None:
        self.assertEqual(
            ProbeApp._fine_scan_bounds(
                best_z=1000,
                initial_step=10,
                min_step=3,
                lower_bound=900,
                upper_bound=1100,
            ),
            (976, 1024),
        )

    def test_gaussian_fit_returns_peak_center(self) -> None:
        scores = {
            90: 20.0,
            95: 73.0,
            100: 100.0,
            105: 73.0,
            110: 20.0,
        }

        self.assertAlmostEqual(ProbeApp._fit_gaussian_focus_peak(scores), 100.0, delta=0.25)

    def test_gaussian_fit_model_exposes_mu_and_sigma(self) -> None:
        model = ProbeApp._fit_gaussian_focus_model(
            {
                90: 20.0,
                95: 73.0,
                100: 100.0,
                105: 73.0,
                110: 20.0,
            }
        )

        self.assertIsNotNone(model)
        assert model is not None
        self.assertAlmostEqual(model["mu"], 100.0, delta=0.25)
        self.assertEqual(model["baseline"], 0.0)
        self.assertGreater(model["sigma"], 0.0)
        self.assertGreater(ProbeApp._gaussian_score_at(model["mu"], model), 90.0)

    def test_gaussian_fit_falls_back_for_flat_scores(self) -> None:
        self.assertEqual(ProbeApp._fit_gaussian_focus_peak({1: 10.0, 2: 10.0, 3: 10.0}), 1.0)

    def test_lorentzian_fit_returns_peak_center_with_zero_baseline(self) -> None:
        scores = {
            80: 20.0,
            90: 50.0,
            100: 100.0,
            110: 50.0,
            120: 20.0,
        }

        model = ProbeApp._fit_focus_peak_model(scores, AUTOFOCUS_PEAK_MODEL_LORENTZIAN)

        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model["baseline"], 0.0)
        self.assertAlmostEqual(float(model["mu"]), 100.0, delta=1.0)

    def test_parabolic_fit_returns_peak_center_with_zero_baseline(self) -> None:
        scores = {
            80: 0.0,
            90: 75.0,
            100: 100.0,
            110: 75.0,
            120: 0.0,
        }

        model = ProbeApp._fit_focus_peak_model(scores, AUTOFOCUS_PEAK_MODEL_PARABOLIC)

        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model["baseline"], 0.0)
        self.assertAlmostEqual(float(model["mu"]), 100.0, delta=1.0)

    def test_pseudo_voigt_fit_returns_peak_center_with_zero_baseline(self) -> None:
        scores = {
            80: 25.0,
            90: 68.0,
            100: 100.0,
            110: 68.0,
            120: 25.0,
        }

        model = ProbeApp._fit_focus_peak_model(scores, AUTOFOCUS_PEAK_MODEL_PSEUDO_VOIGT)

        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model["baseline"], 0.0)
        self.assertAlmostEqual(float(model["mu"]), 100.0, delta=1.0)

    def test_threshold_auto_adjustment_retries_once_after_fitted_peak_below_threshold(self) -> None:
        app = ProbeApp.__new__(ProbeApp)
        app.probe_config = ProbeConfig()
        app.config_path = None
        app.result_queue = queue.Queue()
        app.focus_lock = threading.Lock()
        app.autofocus_z_score_samples = []
        app.autofocus_fine_range = None
        calls = []

        def fake_run(metric: str, initial_step: int, min_step: int, search_range: int, source: str, status_event: str):
            calls.append((metric, initial_step, min_step, search_range, source, status_event))
            if len(calls) == 1:
                return {
                    "result_z": -9,
                    "fine_best_z": -10,
                    "best_score": 400.0,
                    "usable": False,
                    "threshold_passed": False,
                    "edge_limited": False,
                    "peak_fit_available": True,
                    "stopped": False,
                }
            return {
                "result_z": -9,
                "fine_best_z": -10,
                "best_score": 390.0,
                "usable": True,
                "threshold_passed": True,
                "edge_limited": False,
                "peak_fit_available": True,
                "stopped": False,
            }

        app._run_autofocus_sequence = fake_run

        result = ProbeApp._run_autofocus_sequence_with_threshold_auto_adjustment(
            app,
            "Laplacian",
            initial_step=30,
            min_step=5,
            search_range=300,
            source="autofocus",
            status_event="autofocus_status",
        )

        self.assertEqual(len(calls), 2)
        self.assertTrue(result["usable"])
        self.assertTrue(result["auto_threshold_adjusted"])
        self.assertAlmostEqual(app.probe_config.focus_threshold_yellow["Laplacian"], 160.0)
        self.assertAlmostEqual(app.probe_config.focus_threshold_green["Laplacian"], 320.0)
        self.assertEqual(app.probe_config.focus_threshold_yellow["Tenengrad"], 20000.0)

    def test_threshold_auto_adjustment_resets_z_score_plot_before_retry(self) -> None:
        app = ProbeApp.__new__(ProbeApp)
        app.probe_config = ProbeConfig()
        app.config_path = None
        app.result_queue = queue.Queue()
        app.focus_lock = threading.Lock()
        app.autofocus_z_score_samples = [{"z": 1, "score": 100.0, "stage": "fine"}]
        app.autofocus_fine_range = (0, 2)
        calls = []

        def fake_run(metric: str, initial_step: int, min_step: int, search_range: int, source: str, status_event: str):
            calls.append(
                (
                    list(app.autofocus_z_score_samples),
                    app.autofocus_fine_range,
                )
            )
            return {
                "result_z": -9,
                "fine_best_z": -10,
                "best_score": 400.0,
                "usable": len(calls) > 1,
                "threshold_passed": len(calls) > 1,
                "edge_limited": False,
                "peak_fit_available": True,
                "stopped": False,
            }

        app._run_autofocus_sequence = fake_run

        ProbeApp._run_autofocus_sequence_with_threshold_auto_adjustment(
            app,
            "Laplacian",
            initial_step=30,
            min_step=5,
            search_range=300,
            source="autofocus",
            status_event="autofocus_status",
        )

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0], ([{"z": 1, "score": 100.0, "stage": "fine"}], (0, 2)))
        self.assertEqual(calls[1], ([], None))
        self.assertTrue(any(event[0] == "autofocus_z_score_reset" for event in list(app.result_queue.queue)))

    def test_threshold_auto_adjustment_does_not_retry_without_fitted_peak(self) -> None:
        app = ProbeApp.__new__(ProbeApp)
        app.probe_config = ProbeConfig()
        app.config_path = None
        app.result_queue = queue.Queue()
        app.focus_lock = threading.Lock()
        app.autofocus_z_score_samples = []
        app.autofocus_fine_range = None
        calls = []

        def fake_run(metric: str, initial_step: int, min_step: int, search_range: int, source: str, status_event: str):
            calls.append(metric)
            return {
                "result_z": 0,
                "fine_best_z": 0,
                "best_score": 400.0,
                "usable": False,
                "threshold_passed": False,
                "edge_limited": False,
                "peak_fit_available": False,
                "stopped": False,
            }

        app._run_autofocus_sequence = fake_run

        result = ProbeApp._run_autofocus_sequence_with_threshold_auto_adjustment(
            app,
            "Laplacian",
            initial_step=30,
            min_step=5,
            search_range=300,
            source="autofocus",
            status_event="autofocus_status",
        )

        self.assertEqual(len(calls), 1)
        self.assertFalse(result["usable"])
        self.assertEqual(app.probe_config.focus_threshold_yellow["Laplacian"], 1000.0)

    def test_threshold_auto_adjustment_returns_failed_retry_result(self) -> None:
        app = ProbeApp.__new__(ProbeApp)
        app.probe_config = ProbeConfig()
        app.config_path = None
        app.result_queue = queue.Queue()
        app.focus_lock = threading.Lock()
        app.autofocus_z_score_samples = []
        app.autofocus_fine_range = None
        calls = []

        def fake_run(metric: str, initial_step: int, min_step: int, search_range: int, source: str, status_event: str):
            calls.append(metric)
            return {
                "result_z": 0,
                "fine_best_z": search_range,
                "best_score": 400.0,
                "usable": False,
                "threshold_passed": len(calls) > 1,
                "edge_limited": len(calls) > 1,
                "peak_fit_available": True,
                "stopped": False,
            }

        app._run_autofocus_sequence = fake_run

        result = ProbeApp._run_autofocus_sequence_with_threshold_auto_adjustment(
            app,
            "Laplacian",
            initial_step=30,
            min_step=5,
            search_range=300,
            source="autofocus",
            status_event="autofocus_status",
        )

        self.assertEqual(len(calls), 2)
        self.assertFalse(result["usable"])
        self.assertTrue(result["threshold_passed"])
        self.assertTrue(result["edge_limited"])
        self.assertTrue(result["auto_threshold_adjusted"])

    def test_threshold_adjustment_event_updates_settings_vars(self) -> None:
        app = ProbeApp.__new__(ProbeApp)
        app.focus_threshold_yellow_vars = {
            "Laplacian": DummyVar("1000"),
            "Tenengrad": DummyVar("20000"),
            "Brenner": DummyVar("1000"),
        }
        app.focus_threshold_green_vars = {
            "Laplacian": DummyVar("2000"),
            "Tenengrad": DummyVar("40000"),
            "Brenner": DummyVar("2000"),
        }
        app.config_status_var = DummyVar("")
        app._draw_focus_history = lambda: None
        app._draw_autofocus_z_score = lambda: None

        ProbeApp._handle_worker_event(app, ("autofocus_thresholds_adjusted", "Laplacian", 160.0, 320.0, 400.0))

        self.assertEqual(app.focus_threshold_yellow_vars["Laplacian"].get(), "160")
        self.assertEqual(app.focus_threshold_green_vars["Laplacian"].get(), "320")
        self.assertIn("peak 400.00", app.config_status_var.get())

    def test_start_autofocus_uses_visible_threshold_fields_after_auto_adjustment(self) -> None:
        app = ProbeApp.__new__(ProbeApp)
        app.autofocus_running = False
        app.serial_client = object()
        app.probe_config = ProbeConfig()
        app.probe_config.focus_threshold_yellow["Laplacian"] = 145.425
        app.probe_config.focus_threshold_green["Laplacian"] = 290.849
        app.focus_metric_var = DummyVar("Laplacian")
        app.autofocus_step_var = DummyVar("30")
        app.autofocus_min_step_var = DummyVar("5")
        app.autofocus_max_moves_var = DummyVar("300")
        app.autofocus_settle_ms_var = DummyVar("100")
        app.autofocus_sample_count_var = DummyVar("5")
        app.autofocus_peak_model_var = DummyVar("Gaussian")
        app.focus_threshold_yellow_vars = {
            "Laplacian": DummyVar("1000"),
            "Tenengrad": DummyVar("20000"),
            "Brenner": DummyVar("1000"),
        }
        app.focus_threshold_green_vars = {
            "Laplacian": DummyVar("2000"),
            "Tenengrad": DummyVar("40000"),
            "Brenner": DummyVar("2000"),
        }
        app.realtime_enabled = False
        app.home_signal_enabled = False
        app.focus_lock = threading.Lock()
        app.autofocus_samples = []
        app.autofocus_z_score_samples = []
        app.autofocus_fine_range = None
        app.autofocus_history_rows = []
        app.focus_history = []
        app.autofocus_stop_event = threading.Event()
        app.status_var = DummyVar("")
        app.autofocus_status_var = DummyVar("")
        app._draw_autofocus_z_score = lambda: None
        app._draw_focus_history = lambda: None
        app._set_agent_status = lambda _message: None

        with mock.patch("semi_auto_probe.app.threading.Thread") as thread:
            thread.return_value.start.return_value = None
            ProbeApp.start_autofocus(app)

        self.assertEqual(app.probe_config.focus_threshold_yellow["Laplacian"], 1000.0)
        self.assertEqual(app.probe_config.focus_threshold_green["Laplacian"], 2000.0)
        self.assertEqual(app.autofocus_status_var.get(), "Running")
        thread.assert_called_once()


if __name__ == "__main__":
    unittest.main()
