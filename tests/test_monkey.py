"""Phase 15: randomized "monkey" test of the whole application.

Thousands of random inputs (mouse, keys, gestures, screen changes, settings)
with random hands coming through the real vision pipeline. The test passes if
nothing crashes and the game state stays consistent. Seeded, so a failure can
be reproduced exactly.
"""

from __future__ import annotations

import random
import threading
import unittest
import warnings

import pygame

import config
from app.application import Application, LaunchOptions
from tests.fake_camera import make_fake_camera
from tests.hand_factory import make_hand
from ui.screen import ScreenId
from ui.settings_screen import OPTIONS
from vision.gesture_detector import GestureAction, GestureEvent

STEPS = 2500
SEEDS = (1, 2)
MAX_DT = 0.12
SCREENS = [screen for screen in ScreenId if screen is not ScreenId.EXIT]
KEYS = (pygame.K_ESCAPE, pygame.K_F11, pygame.K_a)


class RandomHands:
    """Detector returning 0-3 random hands (random place, pose and pinch)."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)
        self._lock = threading.Lock()

    def detect(self, image, timestamp_ms: int):
        with self._lock:
            rng = self._rng
            return tuple(make_hand(x=rng.uniform(0.05, 0.95), y=rng.uniform(0.3, 0.95),
                                   scale=rng.uniform(0.04, 0.15),
                                   fingers="".join(rng.choice("EC") for _ in range(4)),
                                   pinch_gap=rng.choice((None, 0.1, 0.3, 1.0)),
                                   handedness=rng.choice(("Left", "Right")))
                         for _ in range(rng.choice((0, 1, 2, 2, 3))))

    def close(self) -> None:
        pass


class MonkeyTest(unittest.TestCase):
    def setUp(self) -> None:
        warnings.filterwarnings("ignore", message="no fast renderer available")
        self.addCleanup(config.SETTINGS_FILE.unlink, missing_ok=True)
        self.addCleanup(config.CALIBRATION_FILE.unlink, missing_ok=True)

    def make_app(self, seed: int) -> Application:
        app = Application(LaunchOptions(start_screen=ScreenId.MENU, sound=False),
                          camera=make_fake_camera(),
                          detector_factory=lambda: RandomHands(seed))
        self.addCleanup(app.shutdown)
        return app

    def check_invariants(self, app: Application) -> None:
        state = app.engine.state
        self.assertEqual(state.tigers_on_board, config.TIGER_COUNT)
        self.assertEqual(state.cows_on_board + state.cows_captured + state.cows_to_place,
                         config.COW_COUNT)
        self.assertEqual(state.game_over, state.winner is not None)

    def random_step(self, app: Application, rng: random.Random) -> None:
        pos = (rng.randrange(config.WINDOW_WIDTH), rng.randrange(config.WINDOW_HEIGHT))
        roll = rng.random()
        if roll < 0.30:
            app.handle_events([pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0),
                                                  buttons=(0, 0, 0))])
        elif roll < 0.55:
            app.handle_events([pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos,
                                                  button=rng.choice((1, 1, 1, 3)))])
        elif roll < 0.60:
            app.handle_events([pygame.event.Event(pygame.KEYDOWN, key=rng.choice(KEYS))])
        elif roll < 0.80:
            action = rng.choice((GestureAction.SELECT, GestureAction.SELECT,
                                 GestureAction.CANCEL, GestureAction.MENU))
            position = (rng.random(), rng.random())
            app.vision._events.put(GestureEvent(rng.choice((1, 2)), action, position, 0.0))
        elif roll < 0.86:
            app.navigate(rng.choice(SCREENS))
        elif roll < 0.89:
            screen = app._screens[ScreenId.SETTINGS]
            screen.cycle(rng.choice(OPTIONS))
        app.render_frame(rng.uniform(0.0, MAX_DT))

    def test_random_inputs_never_crash(self) -> None:
        for seed in SEEDS:
            with self.subTest(seed=seed):
                rng = random.Random(seed)
                app = self.make_app(seed)
                for step in range(STEPS):
                    if not app.running:  # EXIT was pressed: start a fresh app.
                        app.shutdown()  # Stop its camera/vision threads first.
                        app = self.make_app(seed + step)
                    try:
                        self.random_step(app, rng)
                    except Exception as exc:  # Report the reproducible step.
                        raise AssertionError(f"seed {seed}, step {step}: {exc!r}") from exc
                    self.check_invariants(app)


if __name__ == "__main__":
    unittest.main()
