"""Phase 15: command-line entry points and diagnostic screens (coverage gaps)."""

from __future__ import annotations

import io
import unittest
import warnings
from contextlib import redirect_stdout
from unittest import mock

import config
import main
from app.application import Application, LaunchOptions
from app.diagnostics import DependencyStatus
from tests.fake_camera import FakeDetector, make_fake_camera
from tests.hand_factory import make_hand
from tests.test_camera import wait_until
from ui.screen import ScreenId
from ui.system_check import SystemCheckScreen


class MainEntryTests(unittest.TestCase):
    def run_main(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with redirect_stdout(output):
            code = main.main(list(args))
        return code, output.getvalue()

    def test_check_reports_every_component(self) -> None:
        camera_ok = DependencyStatus("Camera", True, "640x480 @ 30 fps")
        with mock.patch("main.check_camera", return_value=camera_ok):
            code, output = self.run_main("--check")
        self.assertEqual(code, 0)
        for name in ("Python", "NumPy", "OpenCV", "MediaPipe", "pygame-ce", "Hand model",
                     "Camera"):
            self.assertIn(name, output)
        self.assertIn("All good.", output)

    def test_check_fails_when_camera_missing(self) -> None:
        missing = DependencyStatus("Camera", False, "Camera not available")
        with mock.patch("main.check_camera", return_value=missing):
            code, output = self.run_main("--check")
        self.assertEqual(code, 1)
        self.assertIn("Problems found", output)

    def test_download_model_failure_is_explained(self) -> None:
        with mock.patch("main.download_hand_model", side_effect=OSError("no internet")):
            code, output = self.run_main("--download-model")
        self.assertEqual(code, 1)
        self.assertIn("Download failed", output)
        self.assertIn(config.HAND_MODEL_FILE.name, output)

    def test_crash_is_logged_and_reraised(self) -> None:
        config.CRASH_LOG_FILE.unlink(missing_ok=True)
        self.addCleanup(config.CRASH_LOG_FILE.unlink, missing_ok=True)
        with mock.patch("app.application.Application.run", side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                self.run_main("--input", "mouse", "--mute")
        log = config.CRASH_LOG_FILE.read_text(encoding="utf-8")
        self.assertIn("RuntimeError: boom", log)
        self.assertIn(config.APP_VERSION, log)

    def test_invalid_config_stops_before_opening_a_window(self) -> None:
        with mock.patch("config.validate_config", return_value=["broken value"]):
            code, output = self.run_main("--input", "mouse")
        self.assertEqual(code, 1)
        self.assertIn("broken value", output)


class DiagnosticScreenTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        hands = (make_hand(x=0.3, pinch_gap=0.1), make_hand(x=0.7, fingers="CCCC"))
        self.app = Application(LaunchOptions(start_screen=ScreenId.MENU, sound=False,
                                             input_mode=config.INPUT_MODE_GESTURE),
                               camera=make_fake_camera(),
                               detector_factory=lambda: FakeDetector(hands=hands))
        self.addCleanup(self.app.shutdown)

    def test_system_check_with_a_missing_dependency(self) -> None:
        screen = SystemCheckScreen(self.app._ctx, [DependencyStatus("OpenCV", False,
                                                                    "not importable")])
        self.assertFalse(screen.all_ok)
        screen.draw(self.app._surface)  # Red row + install hint, no crash.
        screen.on_select(screen._continue.rect.center)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_camera_check_draws_hands_gestures_and_log(self) -> None:
        self.app.navigate(ScreenId.CAMERA_CHECK)
        screen = self.app._screens[ScreenId.CAMERA_CHECK]

        def pinch_logged() -> bool:  # Player 1 is pinching: its SELECT reaches the log.
            self.app.render_frame(1 / 60)
            return len(screen._events) > 0
        self.assertTrue(wait_until(pinch_logged))
        for _ in range(30):  # Keep drawing through the pinch ring / meter states.
            self.app.render_frame(1 / 60)


if __name__ == "__main__":
    unittest.main()
