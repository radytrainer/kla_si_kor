"""Phase 15: a complete two-player touchless session in real time.

Scripted hands move smoothly (like real ones) and are fed through the real
camera -> detection -> player tracking -> gesture -> UI -> engine chain.
Nothing is injected past the detector: every pinch must be held, released and
recognised by the real gesture code, and players must stay tracked while
reaching across the camera image.
"""

from __future__ import annotations

import threading
import time
import unittest
import warnings

import config
from app.application import Application, LaunchOptions
from game.cell import Cell
from game.piece import Piece
from game.state import Side
from tests.fake_camera import make_fake_camera
from tests.hand_factory import hand_pointing_at
from ui.screen import ScreenId
from vision.player_tracker import TrackStatus

HOME = {1: (0.25, 0.65), 2: (0.75, 0.65)}  # Where each player's fingertip rests.
MOVE_TIME = 0.4  # Seconds for a smooth reach to a target.
SETTLE_TIME = 0.25  # Hold still before pinching (lets smoothing settle).
PINCH_TIME = config.PINCH_HOLD_TIME + 0.25
RELEASE_TIME = config.ACTION_COOLDOWN + config.GESTURE_RELEASE_TIME + 0.15
TIMEOUT = 8.0


class Director:
    """Thread-safe script of both players' hands, read by the fake detector."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.tips = dict(HOME)
        self.pinched = {1: False, 2: False}

    def set(self, player: int, tip=None, pinched=None) -> None:
        with self._lock:
            if tip is not None:
                self.tips[player] = tip
            if pinched is not None:
                self.pinched[player] = pinched

    def detect(self, image, timestamp_ms: int):
        with self._lock:
            return tuple(hand_pointing_at(*self.tips[p],
                                          pinch_gap=0.1 if self.pinched[p] else None)
                         for p in (1, 2))

    def close(self) -> None:
        pass


class TouchlessSessionTest(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.director = Director()
        self.app = Application(LaunchOptions(start_screen=ScreenId.MENU, sound=False,
                                             input_mode=config.INPUT_MODE_GESTURE),
                               camera=make_fake_camera(),
                               detector_factory=lambda: self.director)
        self.addCleanup(self.app.shutdown)
        self.mapper = self.app._mapper
        self._last = time.monotonic()

    # -- real-time helpers --------------------------------------------------------
    def frame(self) -> None:
        now = time.monotonic()
        self.app.render_frame(now - self._last)
        self._last = now
        time.sleep(1 / 120)  # Let the camera/vision threads run.

    def run_for(self, seconds: float) -> None:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            self.frame()

    def wait_for(self, condition, what: str) -> None:
        end = time.monotonic() + TIMEOUT
        while time.monotonic() < end:
            self.frame()
            if condition():
                return
        self.fail(f"timed out waiting for {what}")

    def move(self, player: int, target) -> None:
        """Glide the fingertip to ``target`` like a real hand."""
        start = self.director.tips[player]
        began = time.monotonic()
        while (t := (time.monotonic() - began) / MOVE_TIME) < 1.0:
            self.director.set(player, (start[0] + (target[0] - start[0]) * t,
                                       start[1] + (target[1] - start[1]) * t))
            self.frame()
        self.director.set(player, target)
        self.run_for(SETTLE_TIME)

    def pinch(self, player: int) -> None:
        self.director.set(player, pinched=True)
        self.run_for(PINCH_TIME)
        self.director.set(player, pinched=False)
        self.run_for(RELEASE_TIME)

    def pinch_at(self, player: int, target) -> None:
        self.move(player, target)
        self.pinch(player)

    def button(self, screen: ScreenId, index: int):
        x, y = self.app._screens[screen]._buttons[index].rect.center
        return x / config.WINDOW_WIDTH, y / config.WINDOW_HEIGHT

    def cell(self, row: int, col: int):
        return self.mapper.cell_center(row, col)

    def tracked(self, player: int) -> bool:
        result = self.app.vision.latest_result()
        return result is not None and result.player(player).status is TrackStatus.TRACKED

    # -- the session ---------------------------------------------------------------
    def test_full_touchless_session(self) -> None:
        board = self.app.engine.state.board
        self.wait_for(lambda: self.tracked(1) and self.tracked(2), "both players tracked")

        # Menu: Player 2 reaches to START GAME (crossing the middle) and pinches.
        self.pinch_at(2, self.button(ScreenId.MENU, 0))
        self.assertIs(self.app.current_screen_id, ScreenId.READY)
        self.assertTrue(self.tracked(1) and self.tracked(2))

        # Ready check: both players pinch, then the 3-2-1 countdown starts the game.
        self.move(2, HOME[2])
        self.pinch(1)
        self.pinch(2)
        self.wait_for(lambda: self.app.current_screen_id is ScreenId.GAME, "countdown")

        # Player 2 (Cows) places a Cow on B1.
        self.pinch_at(2, self.cell(0, 1))
        board = self.app.engine.state.board
        self.assertIs(board.get(Cell(0, 1)), Piece.COW)

        # Player 2 pinches again, but it is the Tigers' turn: refused, nothing changes.
        self.pinch(2)
        self.assertEqual(len(self.app.engine.state.move_history), 1)

        # Player 1 (Tigers) selects A1 and jumps the Cow to C1.
        self.pinch_at(1, self.cell(0, 0))
        self.assertEqual(self.app.engine.state.selected, Cell(0, 0))
        self.pinch_at(1, self.cell(0, 2))
        self.assertEqual(self.app.engine.state.cows_captured, 1)

        # Jump to the end: one Cow short of a Tiger win.
        self.app.engine.state.cows_captured = config.COW_COUNT - 1
        self.pinch_at(2, self.cell(1, 2))  # Cow on C2, right below the Tiger on C1.
        self.pinch_at(1, self.cell(0, 2))  # Select C1...
        self.pinch_at(1, self.cell(2, 2))  # ...and jump C2 to C3: the 12th capture.
        self.assertIs(self.app.engine.state.winner, Side.TIGER)
        self.wait_for(lambda: self.app.current_screen_id is ScreenId.GAME_OVER, "game over")

        # Player 1 pinches PLAY AGAIN: back to the ready check with a fresh game.
        self.run_for(0.2)
        self.pinch_at(1, self.button(ScreenId.GAME_OVER, 0))
        self.assertIs(self.app.current_screen_id, ScreenId.READY)
        history = [record.describe() for record in self.app.engine.state.move_history]
        self.assertEqual(history[:3], ["Cow placed at B1", "Tiger captured Cow at B1 (A1 → C1)",
                                       "Cow placed at C2"])


if __name__ == "__main__":
    unittest.main()
