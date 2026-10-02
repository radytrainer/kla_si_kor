"""Phase 11: the touchless flow (menus, ready check, game over) and calibration."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
import warnings
from pathlib import Path
from unittest import mock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import config  # noqa: E402
from app.application import Application, LaunchOptions  # noqa: E402
from tests.fake_camera import FakeDetector, make_fake_camera  # noqa: E402
from tests.test_camera import wait_until  # noqa: E402
from ui.screen import ScreenId  # noqa: E402
from vision.calibration_store import load_corners, save_corners  # noqa: E402
from vision.coordinate_mapper import rectangle_quad  # noqa: E402
from vision.gesture_detector import GestureAction, GestureEvent  # noqa: E402

FRAME = 1 / 60


def window_to_camera(pos: tuple[int, int]) -> tuple[float, float]:
    return pos[0] / config.WINDOW_WIDTH, pos[1] / config.WINDOW_HEIGHT


class TouchlessTestCase(unittest.TestCase):
    input_mode = config.INPUT_MODE_GESTURE

    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.MENU,
                                             input_mode=self.input_mode),
                               camera=make_fake_camera(), detector_factory=FakeDetector)
        self.addCleanup(self.app.shutdown)
        self.app.render_frame(FRAME)  # Lay out the menu buttons.

    def gesture(self, player: int, action: GestureAction,
                window_pos: tuple[int, int] | None = None,
                camera_pos: tuple[float, float] | None = None) -> None:
        """Queue a gesture as the vision thread would, then run one frame."""
        position = camera_pos or (window_to_camera(window_pos) if window_pos else None)
        self.app.vision._events.put(GestureEvent(player, action, position, 0.0))
        self.app.render_frame(FRAME)

    def button_center(self, screen_id: ScreenId, index: int) -> tuple[int, int]:
        return self.app._screens[screen_id]._buttons[index].rect.center


class TouchlessMenuTests(TouchlessTestCase):
    def test_pinch_on_start_opens_ready_check(self) -> None:
        self.gesture(1, GestureAction.SELECT, self.button_center(ScreenId.MENU, 0))
        self.assertIs(self.app.current_screen_id, ScreenId.READY)

    def test_fist_on_menu_never_quits(self) -> None:
        self.gesture(1, GestureAction.CANCEL)
        self.assertTrue(self.app.running)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_fist_goes_back_from_other_screens(self) -> None:
        self.app.navigate(ScreenId.HOW_TO_PLAY)
        self.gesture(2, GestureAction.CANCEL)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_pinch_from_previous_screen_is_ignored(self) -> None:
        self.app.vision._events.put(GestureEvent(1, GestureAction.SELECT,
                                                 window_to_camera(self.button_center(
                                                     ScreenId.MENU, 0)), 0.0))
        self.app.navigate(ScreenId.HOW_TO_PLAY)  # Stale pinch must not press anything.
        self.app.render_frame(FRAME)
        self.assertIs(self.app.current_screen_id, ScreenId.HOW_TO_PLAY)


class ReadyCheckTests(TouchlessTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app.navigate(ScreenId.READY)
        self.ready = self.app._screens[ScreenId.READY]

    def test_both_players_must_pinch(self) -> None:
        self.gesture(1, GestureAction.SELECT, (100, 100))
        self.gesture(1, GestureAction.SELECT, (100, 100))  # Same player twice: not enough.
        self.assertEqual(self.ready.ready, {1})
        self.assertFalse(self.ready.counting_down)
        self.gesture(2, GestureAction.SELECT, (900, 100))
        self.assertTrue(self.ready.counting_down)

    def test_countdown_then_game(self) -> None:
        self.gesture(1, GestureAction.SELECT, (100, 100))
        self.gesture(2, GestureAction.SELECT, (900, 100))
        self.app.render_frame(config.READY_COUNTDOWN_SECONDS)  # "3, 2, 1" elapsed...
        self.assertIs(self.app.current_screen_id, ScreenId.READY)  # ..."GAME START!" shows
        self.app.render_frame(config.GAME_START_BANNER_TIME)
        self.assertIs(self.app.current_screen_id, ScreenId.GAME)
        self.assertEqual(self.app.engine.state.move_history, [])

    def test_fist_returns_to_menu(self) -> None:
        self.gesture(1, GestureAction.CANCEL)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_ready_state_resets_on_reentry(self) -> None:
        self.gesture(1, GestureAction.SELECT, (100, 100))
        self.app.navigate(ScreenId.MENU)
        self.app.navigate(ScreenId.READY)
        self.assertEqual(self.ready.ready, set())


class OneHandReadyCheckTests(TouchlessTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.app._ctx.one_hand = True
        self.app.navigate(ScreenId.READY)
        self.ready = self.app._screens[ScreenId.READY]

    def test_one_pinch_readies_both_sides(self) -> None:
        self.gesture(2, GestureAction.SELECT, (900, 100))
        self.assertEqual(self.ready.ready, {1, 2})
        self.assertTrue(self.ready.counting_down)
        self.app.render_frame(FRAME)  # One-hand hints render.

    def test_against_the_computer_one_pinch_starts(self) -> None:
        self.app._ctx.one_hand = False
        self.app._ctx.computer_level = "EASY"
        self.gesture(1, GestureAction.SELECT, (100, 100))
        self.assertTrue(self.ready.counting_down)
        self.app.render_frame(FRAME)  # The computer's card renders.


class GameOverTouchlessTests(TouchlessTestCase):
    def test_play_again_by_pinch_goes_to_ready_check(self) -> None:
        self.app.navigate(ScreenId.GAME_OVER)
        self.app.render_frame(FRAME)
        self.gesture(2, GestureAction.SELECT, self.button_center(ScreenId.GAME_OVER, 0))
        self.assertIs(self.app.current_screen_id, ScreenId.READY)


class MouseModeFlowTests(TouchlessTestCase):
    input_mode = config.INPUT_MODE_MOUSE

    def test_start_skips_ready_check_without_camera(self) -> None:
        self.app._screens[ScreenId.MENU].on_select(self.button_center(ScreenId.MENU, 0))
        self.assertIs(self.app.current_screen_id, ScreenId.GAME)

    def test_play_again_skips_ready_check(self) -> None:
        self.app.navigate(ScreenId.GAME_OVER)
        self.app.render_frame(FRAME)
        self.app._screens[ScreenId.GAME_OVER].on_select(
            self.button_center(ScreenId.GAME_OVER, 0))
        self.assertIs(self.app.current_screen_id, ScreenId.GAME)


class CalibrationScreenTests(TouchlessTestCase):
    CORNERS = ((0.25, 0.15), (0.75, 0.2), (0.8, 0.85), (0.2, 0.8))

    def setUp(self) -> None:
        super().setUp()
        self.saved = []
        self.cleared = []
        for name, calls in (("save_corners", self.saved), ("clear_corners", self.cleared)):
            # Never touch the real data/calibration.json.
            patcher = mock.patch(f"ui.calibration_screen.{name}",
                                 side_effect=lambda *args, calls=calls: calls.append(args))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.app.navigate(ScreenId.CALIBRATION)
        self.screen = self.app._screens[ScreenId.CALIBRATION]
        self.mapper = self.app._mapper
        self.app.render_frame(FRAME)

    def pinch_corners(self, corners) -> None:
        for corner in corners:
            self.gesture(1, GestureAction.SELECT, camera_pos=corner)

    def test_four_pinched_corners_calibrate_save_and_show_grid(self) -> None:
        self.pinch_corners(self.CORNERS)
        self.assertEqual(self.mapper.corners, self.CORNERS)
        self.assertEqual(self.saved, [(self.CORNERS,)])
        self.assertTrue(self.screen._saved)  # Stays to show the warped grid for checking.
        self.assertIs(self.app.current_screen_id, ScreenId.CALIBRATION)
        self.assertEqual(self.mapper.cell_at(self.mapper.cell_center(2, 1)), (2, 1))
        self.app.render_frame(FRAME)  # Grid drawing works.

    def test_game_uses_new_calibration_immediately(self) -> None:
        self.pinch_corners(self.CORNERS)
        game = self.app._screens[ScreenId.GAME]
        self.assertIs(game._mapper, self.mapper)

    def test_wrong_order_is_rejected_and_mapper_unchanged(self) -> None:
        before = self.mapper.corners
        tl, tr, br, bl = self.CORNERS
        self.pinch_corners((tl, bl, br, tr))  # Counter-clockwise.
        self.assertEqual(self.mapper.corners, before)
        self.assertEqual(self.saved, [])
        self.assertTrue(self.screen._message_is_error)
        self.assertEqual(self.screen.points, [])  # Start again at top-left.

    def test_too_small_area_is_rejected(self) -> None:
        tiny = ((0.4, 0.4), (0.5, 0.4), (0.5, 0.5), (0.4, 0.5))
        self.pinch_corners(tiny)
        self.assertEqual(self.saved, [])
        self.assertEqual(self.screen._message, self.app._ctx.tr("calibration.too_small"))

    def test_pinch_after_saving_starts_over(self) -> None:
        self.pinch_corners(self.CORNERS)
        self.gesture(1, GestureAction.SELECT, camera_pos=(0.3, 0.3))
        self.assertFalse(self.screen._saved)
        self.assertEqual(self.screen.points, [(0.3, 0.3)])

    def test_reset_restores_default_region(self) -> None:
        self.pinch_corners(self.CORNERS)
        self.screen.on_select(self.screen._buttons[1].rect.center)  # RESET TO DEFAULT
        self.assertEqual(self.mapper.corners, rectangle_quad(*config.BOARD_REGION))
        self.assertEqual(len(self.cleared), 1)

    def test_fist_and_done_return_to_menu(self) -> None:
        self.gesture(1, GestureAction.SELECT, camera_pos=self.CORNERS[0])
        self.gesture(1, GestureAction.CANCEL)
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)
        self.app.navigate(ScreenId.CALIBRATION)
        self.app.render_frame(FRAME)
        self.screen.on_select(self.screen._buttons[2].rect.center)  # DONE
        self.assertIs(self.app.current_screen_id, ScreenId.MENU)

    def test_mouse_clicks_on_preview_add_corners(self) -> None:
        def preview_shown() -> bool:  # The camera needs a moment for its first frame.
            self.app.render_frame(FRAME)
            return self.screen._view.last_image_rect is not None
        self.assertTrue(wait_until(preview_shown))
        image = self.screen._view.last_image_rect
        self.screen.on_select((image.left + image.width // 4, image.top + image.height // 5))
        (x, y), = self.screen.points
        self.assertAlmostEqual(x, 0.25, delta=0.01)
        self.assertAlmostEqual(y, 0.2, delta=0.01)

    def test_camera_check_reachable_and_returns(self) -> None:
        self.screen.on_select(self.screen._buttons[0].rect.center)
        self.assertIs(self.app.current_screen_id, ScreenId.CAMERA_CHECK)
        self.gesture(1, GestureAction.CANCEL)
        self.assertIs(self.app.current_screen_id, ScreenId.CALIBRATION)


class CalibrationStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "calibration.json"

    def test_round_trip(self) -> None:
        corners = ((0.25, 0.15), (0.75, 0.2), (0.8, 0.85), (0.2, 0.8))
        save_corners(corners, self.path)
        self.assertEqual(load_corners(self.path), corners)

    def test_missing_malformed_or_degenerate_files_fall_back(self) -> None:
        self.assertIsNone(load_corners(self.path))  # Missing.
        self.path.write_text("not json", encoding="utf-8")
        self.assertIsNone(load_corners(self.path))
        tl, tr, br, bl = rectangle_quad(0.2, 0.1, 0.8, 0.9)
        self.path.write_text(json.dumps({"corners": [tl, bl, br, tr]}), encoding="utf-8")
        self.assertIsNone(load_corners(self.path))  # Wrong order.
        self.path.write_text(json.dumps({"corners": [[0, 0], [1, 0]]}), encoding="utf-8")
        self.assertIsNone(load_corners(self.path))  # Too few points.


if __name__ == "__main__":
    unittest.main()
