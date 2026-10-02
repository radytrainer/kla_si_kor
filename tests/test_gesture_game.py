"""Phase 10: gestures drive the game engine."""

from __future__ import annotations

import os
import random
import unittest
import warnings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config  # noqa: E402
from app.application import Application, LaunchOptions  # noqa: E402
from game.cell import Cell  # noqa: E402
from game.piece import Piece  # noqa: E402
from game.state import Side  # noqa: E402
from tests.fake_camera import FakeDetector, make_fake_camera  # noqa: E402
from tests.hand_factory import hand_pointing_at  # noqa: E402
from tests.test_camera import wait_until  # noqa: E402
from ui.screen import ScreenId  # noqa: E402
from vision.coordinate_mapper import BoardCoordinateMapper  # noqa: E402
from vision.gesture_detector import GestureAction, GestureEvent  # noqa: E402

MAPPER = BoardCoordinateMapper()
TIGER, COW = 1, 2
MAX_ACTIONS = 400


def gesture(player: int, action: GestureAction, row: int | None = None,
            col: int | None = None, position=None) -> GestureEvent:
    if row is not None:
        position = MAPPER.cell_center(row, col)
    return GestureEvent(player, action, position, 0.0)


def pinch(player: int, row: int, col: int) -> GestureEvent:
    return gesture(player, GestureAction.SELECT, row, col)


class GestureGameTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                             input_mode=config.INPUT_MODE_GESTURE),
                               camera=make_fake_camera(), detector_factory=FakeDetector)
        self.addCleanup(self.app.shutdown)
        self.game = self.app._screens[ScreenId.GAME]
        self.engine = self.app.engine

    def test_active_player_pinch_places_cow(self) -> None:
        result = self.game.handle_gesture(pinch(COW, 2, 2))
        self.assertTrue(result.valid)
        self.assertIs(self.engine.state.board.get(Cell(2, 2)), Piece.COW)
        self.assertEqual(self.game._toast.text, "Cow placed at C3")
        self.assertEqual(self.game._flash, (Cell(2, 2), config.COLOR_OK))
        self.app.render_frame(1 / 60)  # Flash renders without errors.

    def test_locked_player_pinch_is_rejected_and_named(self) -> None:
        result = self.game.handle_gesture(pinch(TIGER, 1, 1))
        self.assertFalse(result.valid)
        self.assertEqual(self.game._toast.text, "P1: It is not your turn")
        self.assertEqual(self.game._flash, (Cell(1, 1), config.COLOR_ERROR))
        self.assertEqual(self.engine.state.move_history, [])

    def test_pinch_off_the_board(self) -> None:
        result = self.game.handle_gesture(gesture(COW, GestureAction.SELECT,
                                                  position=(0.05, 0.5)))
        self.assertFalse(result.valid)
        self.assertEqual(self.game._toast.text, "P2: Point at a board cell")
        self.assertIsNone(self.game._flash)

    def test_select_cancel_and_capture(self) -> None:
        self.game.handle_gesture(pinch(COW, 0, 1))  # Cow placed at B1.
        self.game.handle_gesture(pinch(TIGER, 0, 0))  # Select Tiger A1.
        self.assertEqual(self.engine.state.selected, Cell(0, 0))
        self.game.handle_gesture(gesture(TIGER, GestureAction.CANCEL))  # ✊
        self.assertIsNone(self.engine.state.selected)
        self.game.handle_gesture(pinch(TIGER, 0, 0))
        result = self.game.handle_gesture(pinch(TIGER, 0, 2))  # Jump B1 -> C1.
        self.assertTrue(result.valid)
        self.assertEqual(self.engine.state.cows_captured, 1)
        self.assertEqual(self.game._toast.text, "Tiger captured Cow at B1 (A1 → C1)")

    def test_open_palm_pauses_without_changing_the_game(self) -> None:
        self.assertIsNone(self.game.handle_gesture(gesture(COW, GestureAction.MENU, 1, 1)))
        self.assertTrue(self.game.paused)
        self.assertEqual(self.engine.state.move_history, [])

    def test_board_pinches_are_ignored_while_paused(self) -> None:
        self.game.pause()
        self.assertIsNone(self.game.handle_gesture(pinch(COW, 2, 2)))
        self.assertEqual(self.engine.state.move_history, [])

    def test_fist_resumes(self) -> None:
        self.game.pause()
        self.game.handle_gesture(gesture(TIGER, GestureAction.CANCEL))
        self.assertFalse(self.game.paused)

    def test_pinch_pause_buttons(self) -> None:
        def pinch_button(index: int) -> None:
            x, y = self.game._pause_buttons[index].rect.center
            self.game.handle_gesture(gesture(COW, GestureAction.SELECT, position=(
                x / config.WINDOW_WIDTH, y / config.WINDOW_HEIGHT)))
        self.game.pause()
        self.app.render_frame(1 / 60)  # Pause overlay renders.
        pinch_button(0)  # RESUME
        self.assertFalse(self.game.paused)
        self.game.pause()
        pinch_button(1)  # MAIN MENU
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_no_pause_after_game_over(self) -> None:
        self.engine.state.cows_captured = config.COW_COUNT - 1
        self.game.handle_gesture(pinch(COW, 0, 1))
        self.game.handle_gesture(pinch(TIGER, 0, 0))
        self.game.handle_gesture(pinch(TIGER, 0, 2))
        self.game.pause()
        self.assertFalse(self.game.paused)

    def test_full_games_played_only_with_gestures(self) -> None:
        for seed in range(3):
            with self.subTest(seed=seed):
                self.app.navigate(ScreenId.GAME)
                rng = random.Random(seed)
                for _ in range(MAX_ACTIONS):
                    if self.engine.state.game_over:
                        break
                    player = self.engine.current_player
                    move = rng.choice(self.engine.get_legal_moves(player))
                    if move.from_cell != move.to_cell:
                        self.game.handle_gesture(pinch(player, *move.from_cell))
                    result = self.game.handle_gesture(pinch(player, *move.to_cell))
                    self.assertTrue(result.valid, result.reason)
                self.assertTrue(self.engine.state.game_over)
                self.assertIn(self.engine.state.winner, (Side.TIGER, Side.COW))
                self.app.render_frame(config.GAME_OVER_DELAY + 0.1)
                self.assertIs(self.app.current_screen_id, ScreenId.GAME_OVER)


class OneHandGameTests(unittest.TestCase):
    """One-hand play: a single hand plays both sides."""

    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                             input_mode=config.INPUT_MODE_GESTURE),
                               camera=make_fake_camera(), detector_factory=FakeDetector)
        self.addCleanup(self.app.shutdown)
        self.app._ctx.one_hand = True
        self.game = self.app._screens[ScreenId.GAME]
        self.engine = self.app.engine

    def test_same_hand_plays_both_sides(self) -> None:
        hand = TIGER  # The hand the tracker happened to give Player 1.
        self.assertTrue(self.game.handle_gesture(pinch(hand, 0, 1)).valid)  # Cow at B1.
        self.game.handle_gesture(pinch(hand, 0, 0))  # Select Tiger A1.
        result = self.game.handle_gesture(pinch(hand, 0, 2))  # Jump B1 -> C1.
        self.assertTrue(result.valid)
        self.assertEqual(self.engine.state.cows_captured, 1)
        self.assertTrue(self.game.handle_gesture(pinch(COW, 2, 2)).valid)  # Either hand works.

    def test_rejection_is_not_prefixed_with_a_player(self) -> None:
        self.game.handle_gesture(gesture(TIGER, GestureAction.SELECT, position=(0.05, 0.5)))
        self.assertEqual(self.game._toast.text, "Point at a board cell")

    def test_full_game_with_one_hand(self) -> None:
        rng = random.Random(0)
        for _ in range(MAX_ACTIONS):
            if self.engine.state.game_over:
                break
            move = rng.choice(self.engine.get_legal_moves(self.engine.current_player))
            if move.from_cell != move.to_cell:
                self.game.handle_gesture(pinch(TIGER, *move.from_cell))
            result = self.game.handle_gesture(pinch(TIGER, *move.to_cell))
            self.assertTrue(result.valid, result.reason)
        self.assertTrue(self.engine.state.game_over)


class VsComputerGameTests(unittest.TestCase):
    """Playing alone against the computer (the person plays Cows by default)."""

    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.MENU,
                                             input_mode=config.INPUT_MODE_GESTURE),
                               camera=make_fake_camera(), detector_factory=FakeDetector)
        self.addCleanup(self.app.shutdown)
        self.app._ctx.computer_level = "NORMAL"
        self.app.navigate(ScreenId.GAME)
        self.game = self.app._screens[ScreenId.GAME]
        self.engine = self.app.engine

    def let_computer_play(self) -> None:
        """Run frames until it is the person's turn again (or the game ends)."""
        for _ in range(20):
            if not self.game.computer_turn:
                return
            self.app.render_frame(max(config.COMPUTER_THINK_TIME, config.COMPUTER_STEP_TIME,
                                      config.CAPTURE_ANIMATION_TIME))
        self.fail("The computer did not finish its turn")

    def test_any_hand_plays_the_persons_side_then_the_computer_answers(self) -> None:
        self.assertEqual(self.game.human_player, COW)
        self.assertTrue(self.game.handle_gesture(pinch(TIGER, 2, 2)).valid)  # Either hand.
        self.assertTrue(self.game.computer_turn)
        self.app.render_frame(config.COMPUTER_THINK_TIME / 2)  # Still thinking.
        self.assertEqual(len(self.engine.state.move_history), 1)
        self.assertEqual(self.game._hint_key(), "hint.computer")
        self.assertEqual(self.game._status_info().computer_player, TIGER)  # Named "Computer".
        self.let_computer_play()
        history = self.engine.state.move_history
        self.assertEqual(len(history), 2)
        self.assertIs(history[1].side, Side.TIGER)
        self.assertEqual(self.engine.current_player, COW)

    def test_pinch_during_the_computers_turn_is_refused(self) -> None:
        self.game.handle_gesture(pinch(COW, 2, 2))
        result = self.game.handle_gesture(pinch(COW, 0, 0))
        self.assertFalse(result.valid)
        self.assertEqual(self.game._toast.text, "It is not your turn")

    def test_computer_waits_while_paused(self) -> None:
        self.game.handle_gesture(pinch(COW, 2, 2))
        self.game.pause()
        for _ in range(5):
            self.app.render_frame(config.COMPUTER_THINK_TIME)
        self.assertEqual(len(self.engine.state.move_history), 1)

    def test_computer_moves_first_when_the_person_plays_tigers(self) -> None:
        self.app._ctx.human_side = "TIGER"
        self.app.navigate(ScreenId.GAME)
        self.assertTrue(self.game.computer_turn)
        self.let_computer_play()
        self.assertEqual(self.engine.state.cows_placed, 1)

    def test_full_game_against_the_computer(self) -> None:
        rng = random.Random(3)
        for _ in range(MAX_ACTIONS):
            if self.engine.state.game_over:
                break
            move = rng.choice(self.engine.get_legal_moves(COW))
            if move.from_cell != move.to_cell:
                self.game.handle_gesture(pinch(TIGER, *move.from_cell))
            self.assertTrue(self.game.handle_gesture(pinch(TIGER, *move.to_cell)).valid)
            self.let_computer_play()
        self.assertTrue(self.engine.state.game_over)
        self.app.render_frame(config.GAME_OVER_DELAY + 0.1)
        self.assertIs(self.app.current_screen_id, ScreenId.GAME_OVER)
        self.app.render_frame(1 / 60)  # "You win!" / "The computer wins" renders.

    def test_mouse_clicks_play_the_persons_side(self) -> None:
        self.app._ctx.input_mode = config.INPUT_MODE_MOUSE
        self.app.navigate(ScreenId.GAME)
        self.game.on_select(self.game._board_renderer.cell_rect(
            self.game._layout.board, Cell(2, 2)).center)
        self.assertIs(self.engine.state.board.get(Cell(2, 2)), Piece.COW)
        self.let_computer_play()
        self.assertEqual(self.engine.current_player, COW)


class OneHandPipelineTests(unittest.TestCase):
    """A single real hand, seen on Player 1's side, places a Cow for Player 2."""

    def test_one_hand_gets_the_active_cursor_and_places_a_cow(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        x, y = MAPPER.cell_center(1, 1)  # B2 lies on the camera's left (Player 1) half.
        self.assertLess(x, 0.5)
        hand = hand_pointing_at(x, y, pinch_gap=0.1)
        app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                        input_mode=config.INPUT_MODE_GESTURE),
                          camera=make_fake_camera(),
                          detector_factory=lambda: FakeDetector(hands=(hand,)))
        self.addCleanup(app.shutdown)
        app._ctx.one_hand = True
        game = app._screens[ScreenId.GAME]

        def cow_placed() -> bool:
            app.render_frame(1 / 60)
            return app.engine.state.board.get(Cell(1, 1)) is Piece.COW
        self.assertTrue(wait_until(cow_placed))
        app.render_frame(1 / 60)
        cursors = list(game._cursors.values())
        self.assertEqual(len(cursors), 1)
        self.assertTrue(cursors[0].active)
        self.assertEqual(cursors[0].player_id, app.engine.current_player)


class EndToEndPinchTests(unittest.TestCase):
    """Scripted hands through the real pipeline: a physical pinch places a Cow."""

    def test_real_pipeline_pinch(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        cow_hand = hand_pointing_at(*MAPPER.cell_center(2, 2), pinch_gap=0.1)  # P2 on C3
        tiger_hand = hand_pointing_at(*MAPPER.cell_center(1, 1), pinch_gap=0.1)  # P1 on B2
        app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                        input_mode=config.INPUT_MODE_GESTURE),
                          camera=make_fake_camera(),
                          detector_factory=lambda: FakeDetector(hands=(tiger_hand, cow_hand)))
        self.addCleanup(app.shutdown)

        def cow_placed() -> bool:
            app.render_frame(1 / 60)
            return app.engine.state.board.get(Cell(2, 2)) is Piece.COW
        self.assertTrue(wait_until(cow_placed))
        for _ in range(60):  # Both keep pinching: nothing more may happen.
            app.render_frame(1 / 60)
        history = app.engine.state.move_history
        # Both pinches fire once, together, during the Cows' turn: the Tiger's is
        # rejected ("not your turn") and the Cow's places a Cow. Holding a pinch
        # never fires again, so the Tiger's held pinch cannot act on its new turn.
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].describe(), "Cow placed at C3")


if __name__ == "__main__":
    unittest.main()
