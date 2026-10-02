"""Phase 2 tests: cell naming, translations, layout, hit-testing and navigation.

Runs headless (SDL dummy video driver), so no window opens.
"""

from __future__ import annotations

import os
import unittest
import warnings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
# The dummy driver has no GPU renderer for pygame.SCALED; harmless in tests.
warnings.filterwarnings("ignore", message="no fast renderer available")

import pygame  # noqa: E402

import config  # noqa: E402
from game.cell import Cell  # noqa: E402
from ui.board_renderer import BoardRenderer  # noqa: E402
from ui.layout import GameLayout  # noqa: E402
from ui.text import STRINGS, Translator  # noqa: E402


class CellTests(unittest.TestCase):
    def test_names(self) -> None:
        self.assertEqual(Cell(0, 0).name, "A1")
        self.assertEqual(Cell(1, 1).name, "B2")
        self.assertEqual(Cell(3, 2).name, "C4")

    def test_offset(self) -> None:
        self.assertEqual(Cell(1, 1).offset(-1, 2), Cell(0, 3))


class TranslatorTests(unittest.TestCase):
    def test_english_and_khmer(self) -> None:
        self.assertEqual(Translator(config.LANGUAGE_EN)("turn.tiger"), "TIGER TURN")
        self.assertEqual(Translator(config.LANGUAGE_KM)("turn.tiger"), "វេនខ្លា")
        self.assertEqual(Translator(config.LANGUAGE_KM)("turn.cow"), "វេនគោ")

    def test_missing_khmer_falls_back_to_english(self) -> None:
        from unittest import mock

        khmer_without_rules = {k: v for k, v in STRINGS[config.LANGUAGE_KM].items()
                               if k != "howto.rules"}
        with mock.patch.dict(STRINGS, {config.LANGUAGE_KM: khmer_without_rules}):
            self.assertEqual(Translator(config.LANGUAGE_KM)("howto.rules"), "Rules")

    def test_formatting(self) -> None:
        self.assertEqual(Translator()("player.label", number=2), "Player 2")

    def test_every_english_string_is_translated(self) -> None:
        missing = set(STRINGS[config.LANGUAGE_EN]) - set(STRINGS[config.LANGUAGE_KM])
        self.assertEqual(missing, set())

    def test_khmer_only_keys_are_rejection_reasons(self) -> None:
        # English rejection reasons come from the engine's own (more specific) text.
        extra = set(STRINGS[config.LANGUAGE_KM]) - set(STRINGS[config.LANGUAGE_EN])
        self.assertTrue(all(key.startswith("reason.") for key in extra), extra)

    def test_format_placeholders_match(self) -> None:
        import string

        def fields(text: str) -> set[str]:
            return {name for _, name, _, _ in string.Formatter().parse(text) if name}
        for key, english in STRINGS[config.LANGUAGE_EN].items():
            with self.subTest(key=key):
                self.assertEqual(fields(STRINGS[config.LANGUAGE_KM][key]), fields(english))


class LayoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.layout = GameLayout.for_size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

    def test_regions_do_not_overlap(self) -> None:
        layout = self.layout
        regions = (layout.header, layout.board, layout.camera_column, layout.side_panel)
        for index, first in enumerate(regions):
            for second in regions[index + 1:]:
                self.assertFalse(first.colliderect(second), (first, second))

    def test_camera_column_fits_a_preview(self) -> None:
        self.assertGreaterEqual(self.layout.camera_column.width, 160)

    def test_board_fits_window_and_is_square(self) -> None:
        window = pygame.Rect(0, 0, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.assertTrue(window.contains(self.layout.board))
        self.assertEqual(self.layout.board.width, self.layout.board.height)

    def test_cells_are_large_for_finger_targeting(self) -> None:
        self.assertGreaterEqual(BoardRenderer.cell_size(self.layout.board), 120)


class HitTestTests(unittest.TestCase):
    def setUp(self) -> None:
        self.board = GameLayout.for_size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT).board

    def test_every_cell_center_maps_back_to_itself(self) -> None:
        for row in range(config.BOARD_ROWS):
            for col in range(config.BOARD_COLS):
                cell = Cell(row, col)
                center = BoardRenderer.cell_rect(self.board, cell).center
                self.assertEqual(BoardRenderer.cell_at(self.board, center), cell)

    def test_outside_grid_is_none(self) -> None:
        self.assertIsNone(BoardRenderer.cell_at(self.board, (0, 0)))
        frame_point = (self.board.left + 2, self.board.centery)  # On the label frame.
        self.assertIsNone(BoardRenderer.cell_at(self.board, frame_point))


class ApplicationTests(unittest.TestCase):
    """Drives the real Application with synthetic mouse events."""

    def setUp(self) -> None:
        # unittest resets warning filters per test, so silence it here.
        warnings.filterwarnings("ignore", message="no fast renderer available")
        from app.application import Application, LaunchOptions
        from ui.screen import ScreenId

        from tests.fake_camera import FakeDetector, make_fake_camera

        self.ScreenId = ScreenId
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.MENU),
                               camera=make_fake_camera(),
                               detector_factory=FakeDetector)

    def tearDown(self) -> None:
        self.app.shutdown()

    def click(self, pos: tuple[int, int]) -> None:
        self.app.handle_events([
            pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)),
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1),
        ])

    def menu_button_centers(self) -> list[tuple[int, int]]:
        self.app.render_frame(0)  # Buttons are laid out on first draw.
        menu = self.app._screens[self.ScreenId.MENU]
        return [button.rect.center for button in menu._buttons]

    def test_every_menu_button_navigates(self) -> None:
        # Gesture mode (default): START GAME opens the two-player ready check.
        expected = [self.ScreenId.READY, self.ScreenId.HOW_TO_PLAY, self.ScreenId.CALIBRATION,
                    self.ScreenId.SETTINGS]
        for index, target in enumerate(expected):
            with self.subTest(target=target):
                self.app.navigate(self.ScreenId.MENU)
                self.click(self.menu_button_centers()[index])
                self.assertIs(self.app.current_screen_id, target)
                self.app.render_frame(0)  # Each screen must draw without errors.

    def test_exit_button_stops_app(self) -> None:
        self.click(self.menu_button_centers()[-1])
        self.assertFalse(self.app.running)

    def test_escape_pauses_game_and_returns_from_other_screens(self) -> None:
        escape = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE)
        self.app.navigate(self.ScreenId.GAME)
        self.app.handle_events([escape])  # In a game ESC pauses instead of quitting it.
        self.assertIs(self.app.current_screen_id, self.ScreenId.GAME)
        self.assertTrue(self.app._screens[self.ScreenId.GAME].paused)
        self.app.navigate(self.ScreenId.HOW_TO_PLAY)
        self.app.handle_events([escape])
        self.assertIs(self.app.current_screen_id, self.ScreenId.MENU)


if __name__ == "__main__":
    unittest.main()
