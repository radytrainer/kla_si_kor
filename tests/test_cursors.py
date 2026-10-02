"""Phase 9: player cursors on the game board (fake camera + scripted hands)."""

from __future__ import annotations

import os
import unittest
import warnings

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config  # noqa: E402
from app.application import Application, LaunchOptions  # noqa: E402
from camera.camera import CameraStatus  # noqa: E402
from game.cell import Cell  # noqa: E402
from tests.fake_camera import FakeDetector, make_fake_camera  # noqa: E402
from tests.hand_factory import hand_pointing_at  # noqa: E402
from tests.test_camera import wait_until  # noqa: E402
from ui.board_renderer import BoardRenderer  # noqa: E402
from ui.screen import ScreenId  # noqa: E402
from vision.coordinate_mapper import BoardCoordinateMapper  # noqa: E402

MAPPER = BoardCoordinateMapper()
P1_TARGET = (1, 1)  # B2, left half of the camera -> Player 1
P2_TARGET = (2, 2)  # C3, right half of the camera -> Player 2


def two_players(p2_pinch: float | None = None):
    return (hand_pointing_at(*MAPPER.cell_center(*P1_TARGET)),
            hand_pointing_at(*MAPPER.cell_center(*P2_TARGET), pinch_gap=p2_pinch))


class CursorTests(unittest.TestCase):
    def make_app(self, hands, input_mode: str = config.INPUT_MODE_GESTURE) -> Application:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        app = Application(LaunchOptions(debug=True, start_screen=ScreenId.MENU,
                                        input_mode=input_mode),
                          camera=make_fake_camera(),
                          detector_factory=lambda: FakeDetector(hands=hands))
        self.addCleanup(app.shutdown)
        return app

    def start_game(self, app: Application):
        app.navigate(ScreenId.GAME)
        game = app._screens[ScreenId.GAME]

        def cursors_ready() -> bool:
            app.render_frame(1 / 60)
            return len(game._cursors) == 2
        self.assertTrue(wait_until(cursors_ready))
        return game

    def test_cursors_map_to_cells_and_screen(self) -> None:
        app = self.make_app(two_players())
        game = self.start_game(app)
        p1, p2 = game._cursors[1], game._cursors[2]
        self.assertEqual((p1.cell, p1.cell_name), (P1_TARGET, "B2"))
        self.assertEqual((p2.cell, p2.cell_name), (P2_TARGET, "C3"))
        board = game._layout.board
        self.assertTrue(BoardRenderer.cell_rect(board, Cell(*P1_TARGET)).collidepoint(p1.position))
        self.assertTrue(BoardRenderer.cell_rect(board, Cell(*P2_TARGET)).collidepoint(p2.position))

    def test_only_player_on_turn_is_active(self) -> None:
        app = self.make_app(two_players())
        game = self.start_game(app)
        self.assertEqual(app.engine.current_player, 2)  # Cows (Player 2) start.
        self.assertTrue(game._cursors[2].active)
        self.assertFalse(game._cursors[1].active)
        self.assertEqual(game._active_cursor_cell(), Cell(*P2_TARGET))  # Board highlight.

    def test_pinch_under_the_cursor_plays_once(self) -> None:
        app = self.make_app(two_players(p2_pinch=0.1))  # Player 2 pinching on C3.
        self.start_game(app)
        for _ in range(60):
            app.render_frame(1 / 60)
        history = [record.describe() for record in app.engine.state.move_history]
        self.assertEqual(history, ["Cow placed at C3"])

    def test_camera_runs_only_on_screens_that_need_it(self) -> None:
        app = self.make_app(two_players())
        self.start_game(app)
        self.assertIs(app.camera.status, CameraStatus.RUNNING)
        app.navigate(ScreenId.MENU)  # Gesture-mode menus are touchless: camera stays on.
        self.assertIs(app.camera.status, CameraStatus.RUNNING)
        app.navigate(ScreenId.SYSTEM_CHECK)  # No gestures there.
        self.assertIs(app.camera.status, CameraStatus.STOPPED)

    def test_tracking_error_is_shown_and_mouse_still_plays(self) -> None:
        from vision.hand_detector import HandDetectorError

        def broken():
            raise HandDetectorError("Hand model not found")

        app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                        input_mode=config.INPUT_MODE_GESTURE),
                          camera=make_fake_camera(), detector_factory=broken)
        self.addCleanup(app.shutdown)
        self.assertTrue(wait_until(lambda: app.vision.status.name == "ERROR"))
        app.render_frame(1 / 60)  # Draws the error message in the camera column.
        game = app._screens[ScreenId.GAME]
        game.on_select(BoardRenderer.cell_rect(game._layout.board, Cell(1, 1)).center)
        self.assertEqual(len(app.engine.state.move_history), 1)  # Mouse fallback works.

    def test_camera_lost_mid_game_keeps_game_playable(self) -> None:
        from unittest import mock

        from camera.camera import Camera
        from tests.fake_camera import FakeCapture

        dies = Camera(capture_factory=lambda: FakeCapture(fail_after=20), mirror=False)
        app = Application(LaunchOptions(debug=True, start_screen=ScreenId.GAME,
                                        input_mode=config.INPUT_MODE_GESTURE),
                          camera=dies, detector_factory=lambda: FakeDetector(hands=()))
        self.addCleanup(app.shutdown)
        with mock.patch.object(config, "CAMERA_MAX_READ_FAILURES", 3):
            def disconnected() -> bool:
                app.render_frame(1 / 60)  # Keeps drawing while the camera dies.
                return app.camera.status is CameraStatus.DISCONNECTED
            self.assertTrue(wait_until(disconnected))
        game = app._screens[ScreenId.GAME]
        game.on_select(BoardRenderer.cell_rect(game._layout.board, Cell(1, 1)).center)
        self.assertEqual(len(app.engine.state.move_history), 1)  # Mouse still plays.

    def test_black_camera_picture_is_explained_in_game(self) -> None:
        from unittest import mock

        app = self.make_app(two_players())
        game = self.start_game(app)
        drawn = []
        original = game.ctx.tr

        def spy(key, **values):
            drawn.append(key)
            return original(key, **values)
        with mock.patch.object(game._player_column, "_tr", side_effect=spy):
            app.render_frame(1 / 60)  # The fake camera's image is bright: no warning.
            self.assertNotIn("camera.too_dark", drawn)
            with mock.patch("camera.camera.Frame.too_dark", new=True):
                app.render_frame(1 / 60)
        self.assertIn("camera.too_dark", drawn)

    def test_mouse_mode_has_no_camera_or_cursors(self) -> None:
        app = self.make_app(two_players(), input_mode=config.INPUT_MODE_MOUSE)
        app.navigate(ScreenId.GAME)
        app.render_frame(1 / 60)
        self.assertIs(app.camera.status, CameraStatus.STOPPED)
        self.assertEqual(app._screens[ScreenId.GAME]._cursors, {})


if __name__ == "__main__":
    unittest.main()
