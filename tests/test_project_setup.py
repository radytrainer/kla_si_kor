"""Phase 1 tests: configuration consistency, diagnostics and entry point."""

from __future__ import annotations

import importlib
import unittest

import config
import main
from app.diagnostics import REQUIRED_PACKAGES, check_dependencies, check_package
from ui.fonts import contains_khmer


class ConfigTests(unittest.TestCase):
    def test_config_is_valid(self) -> None:
        self.assertEqual(config.validate_config(), [])

    def test_four_tigers_on_corners(self) -> None:
        self.assertEqual(len(config.TIGER_START_POSITIONS), 4)
        self.assertEqual(set(config.TIGER_START_POSITIONS),
                         {(0, 0), (0, 3), (3, 0), (3, 3)})

    def test_piece_counts(self) -> None:
        self.assertEqual((config.TIGER_COUNT, config.COW_COUNT), (4, 12))
        self.assertEqual((config.BOARD_ROWS, config.BOARD_COLS), (4, 4))


class DiagnosticsTests(unittest.TestCase):
    def test_every_required_package_reported(self) -> None:
        labels = {status.label for status in check_dependencies()}
        self.assertIn("Python", labels)
        for label, *_ in REQUIRED_PACKAGES:
            self.assertIn(label, labels)

    def test_all_dependencies_functional(self) -> None:
        broken = [status for status in check_dependencies() if not status.ok]
        self.assertEqual(broken, [])

    def test_importable_but_broken_package_detected(self) -> None:
        status = check_package("JSON", "json", "json", "attribute_that_does_not_exist")
        self.assertFalse(status.ok)
        self.assertIn("broken", status.detail)

    def test_missing_package_does_not_raise(self) -> None:
        status = check_package("Nope", "package_that_does_not_exist_123", "nope")
        self.assertFalse(status.ok)


class PackageLayoutTests(unittest.TestCase):
    def test_layers_importable(self) -> None:
        for package in ("app", "camera", "vision", "game", "ui", "audio"):
            with self.subTest(package=package):
                importlib.import_module(package)


class MainTests(unittest.TestCase):
    def test_parse_defaults(self) -> None:
        args = main.parse_args([])
        self.assertFalse(args.check)
        # Not given = use the saved settings (None), not a forced value.
        self.assertIsNone(args.debug)
        self.assertIsNone(args.input)
        self.assertIsNone(args.fullscreen)
        self.assertTrue(main.parse_args(["--debug"]).debug)

    def test_no_debug_flag(self) -> None:
        self.assertFalse(main.parse_args(["--no-debug"]).debug)


class FontTests(unittest.TestCase):
    def test_khmer_detection(self) -> None:
        self.assertTrue(contains_khmer(config.APP_TITLE_KM))
        self.assertFalse(contains_khmer(config.APP_TITLE_EN))


if __name__ == "__main__":
    unittest.main()
