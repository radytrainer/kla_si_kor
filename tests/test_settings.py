"""Phase 14: settings model, persistence, CLI overrides and live application."""

from __future__ import annotations

import json
import tempfile
import unittest
import warnings
from pathlib import Path

import config
from app.application import Application, LaunchOptions, session_settings
from app.settings import Settings, load_settings, save_settings
from tests.fake_camera import FakeDetector, make_fake_camera
from ui.screen import ScreenId
from ui.settings_screen import OPTIONS, next_value

FRAME = 1 / 60


class SettingsFileTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "settings.json"

    def test_defaults_come_from_config(self) -> None:
        settings = load_settings(self.path)  # No file yet.
        self.assertEqual(settings, Settings())
        self.assertEqual(settings.pinch_thresholds,
                         (config.PINCH_THRESHOLD, config.PINCH_RELEASE_THRESHOLD))

    def test_round_trip(self) -> None:
        settings = Settings(sound=False, volume=0.25, language=config.LANGUAGE_KM,
                            input_mode=config.INPUT_MODE_MOUSE, pinch_sensitivity="HIGH",
                            cursor_smoothing="LOW", fullscreen=True, debug=False, camera_index=1,
                            one_hand=True, computer="HARD", human_side="TIGER")
        save_settings(settings, self.path)
        self.assertEqual(load_settings(self.path), settings)
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_invalid_values_fall_back_individually(self) -> None:
        self.path.write_text(json.dumps({"volume": 7, "language": "fr", "sound": "yes",
                                         "camera_index": 1, "pinch_sensitivity": "HIGH",
                                         "computer": "GOD", "human_side": "DOG"}),
                             encoding="utf-8")
        settings = load_settings(self.path)
        self.assertEqual(settings.volume, Settings().volume)
        self.assertEqual(settings.language, Settings().language)
        self.assertEqual(settings.sound, Settings().sound)
        self.assertEqual((settings.computer, settings.human_side),
                         (Settings().computer, Settings().human_side))
        self.assertEqual((settings.camera_index, settings.pinch_sensitivity), (1, "HIGH"))

    def test_corrupt_file_gives_defaults(self) -> None:
        self.path.write_text("{not json", encoding="utf-8")
        self.assertEqual(load_settings(self.path), Settings())
        self.path.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(load_settings(self.path), Settings())

    def test_presets_keep_release_below_relaxed_hand(self) -> None:
        relaxed_hand = 0.38  # Measured on MediaPipe's sample photo (Phase 8).
        for close, release in config.PINCH_SENSITIVITY_PRESETS.values():
            self.assertLess(close, release)
            self.assertLess(release, relaxed_hand)


class CliOverrideTests(unittest.TestCase):
    def test_only_given_options_override(self) -> None:
        saved = Settings(debug=True, input_mode=config.INPUT_MODE_GESTURE, sound=True)
        session = session_settings(saved, LaunchOptions(input_mode=config.INPUT_MODE_MOUSE,
                                                        sound=False))
        self.assertEqual(session.input_mode, config.INPUT_MODE_MOUSE)
        self.assertFalse(session.sound)
        self.assertTrue(session.debug)  # Not given on the command line: saved value kept.


class NextValueTests(unittest.TestCase):
    def test_cycles_and_wraps(self) -> None:
        self.assertEqual(next_value(("LOW", "NORMAL", "HIGH"), "HIGH"), "LOW")
        self.assertEqual(next_value((True, False), True), False)

    def test_unlisted_number_jumps_to_next_step(self) -> None:
        self.assertEqual(next_value(config.VOLUME_STEPS, 0.7), 0.75)
        self.assertEqual(next_value(config.VOLUME_STEPS, 1.0), 0.0)


class LiveSettingsTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        # These tests save settings; remove them so later tests start from defaults.
        self.addCleanup(config.SETTINGS_FILE.unlink, missing_ok=True)
        self.app = Application(LaunchOptions(start_screen=ScreenId.SETTINGS,
                                             input_mode=config.INPUT_MODE_MOUSE),
                               camera=make_fake_camera(), detector_factory=FakeDetector)
        self.addCleanup(self.app.shutdown)
        self.screen = self.app._screens[ScreenId.SETTINGS]
        self.app.render_frame(FRAME)

    def option(self, field: str):
        return next(option for option in OPTIONS if option.field == field)

    def test_language_switches_immediately_and_is_saved(self) -> None:
        self.screen.cycle(self.option("language"))
        self.assertEqual(self.app._ctx.tr("turn.tiger"), "វេនខ្លា")
        self.assertEqual(load_settings().language, config.LANGUAGE_KM)
        self.app.render_frame(FRAME)  # Khmer labels render.

    def test_pinch_sensitivity_reaches_the_gesture_detector(self) -> None:
        self.screen.cycle(self.option("pinch_sensitivity"))  # NORMAL -> HIGH
        tracker = self.app.vision.gestures._trackers[1]
        self.assertEqual((tracker.tuning.pinch_threshold, tracker.tuning.pinch_release_threshold),
                         config.PINCH_SENSITIVITY_PRESETS["HIGH"])

    def test_input_mode_switch_starts_camera_on_touchless_screens(self) -> None:
        self.assertFalse(self.app.camera.running)  # Mouse mode: camera off on Settings.
        self.screen.cycle(self.option("input_mode"))  # MOUSE -> GESTURE
        self.assertEqual(self.app._ctx.input_mode, config.INPUT_MODE_GESTURE)
        self.assertTrue(self.app.vision.camera._thread is not None)

    def test_one_hand_play_applies_immediately_and_is_saved(self) -> None:
        self.assertFalse(self.app._ctx.one_hand)
        self.screen.cycle(self.option("one_hand"))
        self.assertTrue(self.app._ctx.one_hand)
        self.assertTrue(load_settings().one_hand)

    def test_computer_opponent_settings_reach_the_game(self) -> None:
        self.screen.cycle(self.option("computer"))  # OFF -> EASY
        self.screen.cycle(self.option("human_side"))  # COW -> TIGER
        self.assertEqual((self.app._ctx.computer_level, self.app._ctx.human_side),
                         ("EASY", "TIGER"))
        self.assertTrue(self.app._ctx.vs_computer)
        saved = load_settings()
        self.assertEqual((saved.computer, saved.human_side), ("EASY", "TIGER"))
        self.app.render_frame(FRAME)  # The longer settings grid renders.

    def test_sound_and_volume(self) -> None:
        self.screen.cycle(self.option("volume"))
        self.assertIn(self.app.sounds.volume, config.VOLUME_STEPS)
        self.screen.cycle(self.option("sound"))
        self.assertEqual(self.app.sounds.enabled, self.app.settings.sound)

    def test_debug_toggle_and_every_button_renders(self) -> None:
        before = self.app.settings.debug
        self.screen.on_select(self.screen._buttons[OPTIONS.index(self.option("debug"))]
                              .rect.center)
        self.assertEqual(self.app.settings.debug, not before)
        self.app.render_frame(FRAME)

    def test_command_line_override_is_not_saved(self) -> None:
        # Started with --input mouse; changing the volume must not save input_mode.
        self.screen.cycle(self.option("volume"))
        saved = load_settings()
        self.assertEqual(saved.input_mode, Settings().input_mode)
        self.assertEqual(saved.volume, self.app.settings.volume)

    def test_f11_toggles_fullscreen(self) -> None:
        import pygame

        from unittest import mock

        before = self.app.settings.fullscreen
        with mock.patch("pygame.display.toggle_fullscreen"):  # A driver that can toggle.
            self.app.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11)])
        self.assertEqual(self.app.settings.fullscreen, not before)
        self.app.render_frame(FRAME)

    def test_fullscreen_unsupported_keeps_window_and_does_not_crash(self) -> None:
        import pygame

        # The headless test driver cannot toggle (like some real drivers).
        before = self.app.settings.fullscreen
        for _ in range(5):  # Used to crash pygame on the second attempt.
            self.app.handle_events([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_F11)])
            self.app.render_frame(FRAME)
        self.assertEqual(self.app.settings.fullscreen, before)

    def test_back_returns_to_menu(self) -> None:
        self.screen.on_select(self.screen._buttons[-1].rect.center)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)


if __name__ == "__main__":
    unittest.main()
