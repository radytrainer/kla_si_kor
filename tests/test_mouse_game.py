"""Phase 4 end-to-end tests: the full game played with (synthetic) mouse clicks.

These drive the real Application exactly as a user would: pygame mouse events at
the pixel centre of board cells. Runs headless (SDL dummy video driver).
"""

from __future__ import annotations

import os
import random
import unittest
import warnings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402

import config  # noqa: E402
from app.application import Application, LaunchOptions  # noqa: E402
from game.cell import Cell  # noqa: E402
from game.piece import Piece  # noqa: E402
from game.state import Phase, Side  # noqa: E402
from ui.board_renderer import BoardRenderer  # noqa: E402
from tests.fake_camera import FakeDetector, make_fake_camera  # noqa: E402
from ui.screen import ScreenId  # noqa: E402

MAX_ACTIONS = 400


class MouseGameTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                             input_mode=config.INPUT_MODE_MOUSE),
                               camera=make_fake_camera(),
                               detector_factory=FakeDetector)
        self.game = self.app._screens[ScreenId.GAME]
        self.engine = self.app.engine

    def tearDown(self) -> None:
        self.app.shutdown()

    # -- helpers -------------------------------------------------------------
    def click_pos(self, pos: tuple[int, int], button: int = 1) -> None:
        self.app.handle_events([
            pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)),
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button),
        ])

    def click(self, row: int, col: int, button: int = 1) -> None:
        center = BoardRenderer.cell_rect(self.game._layout.board, Cell(row, col)).center
        self.click_pos(center, button)

    def frame(self, dt: float = 1 / 60) -> None:
        self.app.render_frame(dt)

    # -- tests -----------------------------------------------------------------
    def test_start_game_resets_engine(self) -> None:
        self.click(1, 1)
        self.app.navigate(ScreenId.MENU)
        self.app.navigate(ScreenId.GAME)
        self.assertEqual(self.engine.state.board.to_strings(), ["T..T", "....", "....", "T..T"])

    def test_place_select_move_capture_by_clicks(self) -> None:
        self.click(0, 1)  # Cow placed at B1.
        self.assertIs(self.engine.state.board.get(Cell(0, 1)), Piece.COW)
        self.assertIs(self.engine.state.current_side, Side.TIGER)
        self.click(0, 0)  # Select Tiger A1.
        self.assertEqual(self.engine.state.selected, Cell(0, 0))
        self.frame()  # Selection + legal targets must render.
        self.click(0, 2)  # Jump over B1 to C1.
        self.assertEqual(self.engine.state.cows_captured, 1)
        self.assertIs(self.engine.state.board.get(Cell(0, 2)), Piece.TIGER)
        self.assertEqual(self.game._toast.text, "Tiger captured Cow at B1 (A1 → C1)")
        self.frame()

    def test_rejected_click_shows_reason(self) -> None:
        self.click(0, 0)  # Cows' turn: clicking a Tiger cell = placing on occupied.
        self.assertEqual(self.game._toast.text, "Cows can only be placed on an empty cell")
        self.assertEqual(self.game._toast.color, config.COLOR_ERROR)

    def test_right_click_cancels_selection(self) -> None:
        self.click(1, 1)  # Cow placed.
        self.click(0, 0)  # Tiger selected.
        self.click(2, 2, button=3)
        self.assertIsNone(self.engine.state.selected)

    def test_click_outside_board_is_ignored(self) -> None:
        self.click_pos((5, 5))
        self.assertEqual(self.engine.state.move_history, [])

    def test_random_full_games_by_mouse_reach_game_over_and_replay(self) -> None:
        for seed in range(3):
            with self.subTest(seed=seed):
                self.app.navigate(ScreenId.GAME)
                rng = random.Random(seed)
                for _ in range(MAX_ACTIONS):
                    if self.engine.state.game_over:
                        break
                    moves = self.engine.get_legal_moves(self.engine.current_player)
                    move = rng.choice(moves)
                    if move.from_cell != move.to_cell:
                        self.click(*move.from_cell)
                    self.click(*move.to_cell)
                    self.frame()
                self.assertTrue(self.engine.state.game_over)
                self.assertIs(self.engine.state.phase, Phase.GAME_OVER)
                # The final board stays visible, then the results screen appears.
                self.assertIs(self.app.current_screen_id, ScreenId.GAME)
                self.frame(config.GAME_OVER_DELAY + 0.1)
                self.assertIs(self.app.current_screen_id, ScreenId.GAME_OVER)
                self.frame()
                self.click_play_again()
                self.assertIs(self.app.current_screen_id, ScreenId.GAME)
                self.assertEqual(self.engine.state.move_history, [])

    def click_play_again(self) -> None:
        screen = self.app._screens[ScreenId.GAME_OVER]
        self.click_pos(screen._buttons[0].rect.center)

    def test_game_over_main_menu_button(self) -> None:
        self.engine.state.cows_captured = config.COW_COUNT - 1
        self.click(0, 1)
        self.click(0, 0)
        self.click(0, 2)  # 12th capture -> Tigers win.
        self.assertIs(self.engine.state.winner, Side.TIGER)
        self.frame(config.GAME_OVER_DELAY + 0.1)
        self.frame()
        screen = self.app._screens[ScreenId.GAME_OVER]
        self.click_pos(screen._buttons[1].rect.center)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_clicks_ignored_after_game_over(self) -> None:
        self.engine.state.cows_captured = config.COW_COUNT - 1
        self.click(0, 1)
        self.click(0, 0)
        self.click(0, 2)
        history = list(self.engine.state.move_history)
        self.click(2, 2)
        self.assertEqual(self.engine.state.move_history, history)


if __name__ == "__main__":
    unittest.main()
