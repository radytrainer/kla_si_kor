"""Phase 13: easing, board animations, sound effects and their wiring into the game."""

from __future__ import annotations

import tempfile
import unittest
import warnings
import wave
from pathlib import Path
from unittest import mock

import numpy as np
import pygame

import config
from app.application import Application, LaunchOptions
from audio.sound_manager import GENERATED_SOUNDS, SoundEffect, SoundManager, synthesize
from game.cell import Cell
from game.piece import Piece
from game.state import MoveKind, MoveRecord, Side
from tests.fake_camera import FakeDetector, make_fake_camera
from ui.animations import (BoardAnimator, CaptureAnimation, MoveAnimation, PlaceAnimation,
                           animation_for)
from ui.board_renderer import BoardRenderer
from ui.confetti import Confetti
from ui.easing import ease_in_out_cubic, ease_out_back, ease_out_cubic
from ui.screen import ScreenId
from ui.widgets import Button

FRAME = 1 / 60


class EasingTests(unittest.TestCase):
    def test_endpoints(self) -> None:
        for curve in (ease_in_out_cubic, ease_out_cubic, ease_out_back):
            with self.subTest(curve=curve.__name__):
                self.assertAlmostEqual(curve(0.0), 0.0)
                self.assertAlmostEqual(curve(1.0), 1.0)
                self.assertAlmostEqual(curve(2.0), 1.0)  # Clamped.

    def test_back_overshoots(self) -> None:
        self.assertGreater(max(ease_out_back(t / 100) for t in range(101)), 1.0)


class AnimationTests(unittest.TestCase):
    def test_place_grows_and_hides_real_piece(self) -> None:
        animation = PlaceAnimation(Cell(1, 2))
        self.assertEqual(animation.hidden_cells(), {Cell(1, 2)})
        first = animation.frames()[0].scale
        animation.update(config.PLACE_ANIMATION_TIME / 2)
        self.assertGreater(animation.frames()[0].scale, first)
        animation.update(config.PLACE_ANIMATION_TIME)
        self.assertTrue(animation.finished)
        self.assertAlmostEqual(animation.frames()[0].scale, 1.0)

    def test_move_slides_between_cells(self) -> None:
        animation = MoveAnimation(Cell(0, 0), Cell(0, 1), Piece.TIGER)
        animation.update(config.MOVE_ANIMATION_TIME / 2)
        frame = animation.frames()[0]
        self.assertAlmostEqual(frame.col, 0.5, delta=0.01)
        self.assertEqual(animation.hidden_cells(), {Cell(0, 1)})

    def test_capture_jumps_and_cow_fades(self) -> None:
        animation = CaptureAnimation(Cell(0, 0), Cell(0, 2), captured=Cell(0, 1))
        self.assertEqual(animation.hidden_cells(), {Cell(0, 2), Cell(0, 1)})
        animation.update(config.CAPTURE_ANIMATION_TIME / 2)
        cow, tiger = animation.frames()
        self.assertEqual((cow.piece, tiger.piece), (Piece.COW, Piece.TIGER))
        self.assertAlmostEqual(tiger.lift, config.CAPTURE_JUMP_HEIGHT, delta=0.01)
        self.assertLess(cow.alpha, 255)
        animation.update(config.CAPTURE_ANIMATION_TIME)
        (tiger,) = animation.frames()  # The Cow is gone by the landing.
        self.assertAlmostEqual(tiger.col, 2.0)
        self.assertAlmostEqual(tiger.lift, 0.0)  # Landed (sin(pi) is ~1e-16, not exactly 0).

    def test_animation_for_records(self) -> None:
        place = MoveRecord(1, Side.COW, MoveKind.PLACE, to_cell=Cell(1, 1))
        capture = MoveRecord(2, Side.TIGER, MoveKind.CAPTURE, Cell(0, 0), Cell(0, 2), Cell(0, 1))
        self.assertIsInstance(animation_for(place, Piece.COW), PlaceAnimation)
        self.assertIsInstance(animation_for(capture, Piece.TIGER), CaptureAnimation)
        self.assertIsNone(animation_for(MoveRecord(3, Side.COW, MoveKind.PASS), Piece.COW))

    def test_animator(self) -> None:
        animator = BoardAnimator()
        animator.start(PlaceAnimation(Cell(0, 1)))
        self.assertTrue(animator.busy)
        animator.start(MoveAnimation(Cell(0, 0), Cell(1, 0), Piece.TIGER))  # Replaces.
        self.assertEqual(animator.hidden_cells(), {Cell(1, 0)})
        self.assertFalse(animator.update(FRAME))
        self.assertTrue(animator.update(config.MOVE_ANIMATION_TIME))
        self.assertFalse(animator.busy)
        disabled = BoardAnimator(enabled=False)
        disabled.start(PlaceAnimation(Cell(0, 1)))
        self.assertFalse(disabled.busy)


class SpySounds:
    def __init__(self) -> None:
        self.played: list[SoundEffect] = []

    def play(self, effect: SoundEffect) -> None:
        self.played.append(effect)


class GameWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.app = Application(LaunchOptions(debug=False, start_screen=ScreenId.GAME,
                                             input_mode=config.INPUT_MODE_MOUSE),
                               camera=make_fake_camera(), detector_factory=FakeDetector)
        self.addCleanup(self.app.shutdown)
        self.spy = SpySounds()
        self.app._ctx.sounds = self.spy
        self.game = self.app._screens[ScreenId.GAME]

    def click(self, row: int, col: int) -> None:
        pos = BoardRenderer.cell_rect(self.game._layout.board, Cell(row, col)).center
        self.app.handle_events([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=1)])

    def run_frames(self, seconds: float) -> None:
        for _ in range(round(seconds / FRAME) + 1):
            self.app.render_frame(FRAME)

    def test_place_animates_then_turn_changes_with_sound(self) -> None:
        self.click(0, 1)
        self.assertEqual(self.spy.played, [SoundEffect.COW_PLACE])
        self.assertEqual(self.game._animator.hidden_cells(), {Cell(0, 1)})
        self.app.render_frame(FRAME)
        self.assertNotIn(SoundEffect.TURN_CHANGE, self.spy.played)  # Waits for the drop.
        self.run_frames(config.PLACE_ANIMATION_TIME)
        self.assertFalse(self.game._animator.busy)
        self.assertEqual(self.spy.played, [SoundEffect.COW_PLACE, SoundEffect.TURN_CHANGE])
        self.assertGreater(self.game._status_info().turn_flash, 0.0)

    def test_every_outcome_has_its_sound(self) -> None:
        self.click(0, 0)  # Cows' turn: placing on a Tiger is rejected.
        self.click(0, 1)  # Cow placed at B1.
        self.run_frames(config.PLACE_ANIMATION_TIME)
        self.click(0, 0)  # Tiger selected.
        self.click(0, 0)  # Deselected.
        self.click(0, 0)
        self.click(0, 2)  # Jump B1: capture.
        self.assertIsInstance(self.game._animator._animations[0], CaptureAnimation)
        self.assertEqual(self.spy.played, [
            SoundEffect.INVALID_MOVE, SoundEffect.COW_PLACE, SoundEffect.TURN_CHANGE,
            SoundEffect.PIECE_SELECT, SoundEffect.MENU_CLICK, SoundEffect.PIECE_SELECT,
            SoundEffect.TIGER_CAPTURE])

    def test_frames_render_mid_animation(self) -> None:
        self.click(0, 1)
        self.run_frames(config.PLACE_ANIMATION_TIME / 2)  # Must draw without errors.

    def test_victory_sound_and_confetti_on_game_over(self) -> None:
        self.app.engine.state.cows_captured = config.COW_COUNT - 1
        self.click(0, 1)
        self.click(0, 0)
        self.click(0, 2)  # 12th capture.
        self.app.render_frame(config.GAME_OVER_DELAY + 0.1)
        self.assertIs(self.app.current_screen_id, ScreenId.GAME_OVER)
        self.assertEqual(self.spy.played[-1], SoundEffect.VICTORY)
        self.run_frames(0.2)

    def test_buttons_click(self) -> None:
        self.app.navigate(ScreenId.MENU)
        self.app._ctx.sounds = self.spy
        Button.on_any_click = lambda: self.spy.play(SoundEffect.MENU_CLICK)
        self.app.render_frame(FRAME)
        menu = self.app._screens[ScreenId.MENU]
        menu.on_select(menu._buttons[1].rect.center)  # HOW TO PLAY
        self.assertEqual(self.spy.played, [SoundEffect.MENU_CLICK])


class SoundManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)

    def test_generated_fallback_for_every_effect(self) -> None:
        manager = SoundManager(sounds_dir=self.dir)
        self.assertTrue(manager.available)  # SDL dummy audio driver in tests.
        self.assertEqual(set(manager.sources), set(SoundEffect))
        self.assertEqual(set(manager.sources.values()), {"generated"})
        for effect in SoundEffect:
            manager.play(effect)

    def test_asset_file_is_preferred_and_broken_file_falls_back(self) -> None:
        with wave.open(str(self.dir / "cow_place.wav"), "wb") as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(22050)
            out.writeframes(np.zeros(2205, dtype=np.int16).tobytes())
        (self.dir / "victory.wav").write_bytes(b"not a wav file")
        manager = SoundManager(sounds_dir=self.dir)
        self.assertEqual(manager.sources[SoundEffect.COW_PLACE], "file")
        self.assertEqual(manager.sources[SoundEffect.VICTORY], "generated")

    def test_no_audio_device_is_silent_not_fatal(self) -> None:
        with mock.patch("pygame.mixer.get_init", return_value=None), \
                mock.patch("pygame.mixer.init", side_effect=pygame.error("no device")):
            manager = SoundManager(sounds_dir=self.dir)
        self.assertFalse(manager.available)
        manager.play(SoundEffect.VICTORY)  # No exception.

    def test_disabled(self) -> None:
        manager = SoundManager(enabled=False, sounds_dir=self.dir)
        self.assertFalse(manager.available)
        manager.play(SoundEffect.MENU_CLICK)

    def test_synthesis_shape_and_range(self) -> None:
        samples = synthesize(GENERATED_SOUNDS[SoundEffect.VICTORY], channels=2)
        self.assertEqual(samples.ndim, 2)
        self.assertEqual(samples.shape[1], 2)
        self.assertEqual(samples.dtype, np.int16)
        self.assertLessEqual(int(np.abs(samples.astype(np.int32)).max()), 32767)
        self.assertGreater(int(np.abs(samples).max()), 1000)  # Actually audible.


class ConfettiTests(unittest.TestCase):
    def test_particles_fall_and_recycle(self) -> None:
        confetti = Confetti(200, 100, count=20, seed=1)
        start = [p.y for p in confetti.particles]
        confetti.update(0.1)
        self.assertTrue(all(p.y > y for p, y in zip(confetti.particles, start)))
        for _ in range(100):
            confetti.update(0.1)
        self.assertTrue(all(p.y <= 100 for p in confetti.particles))
        self.assertEqual(len(confetti.particles), 20)


if __name__ == "__main__":
    unittest.main()
