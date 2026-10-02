"""Gesture tests: pose classification, pinch debouncing, cooldown, smoothing."""

from __future__ import annotations

import math
import unittest
from pathlib import Path

import config
from tests.hand_factory import make_hand
from vision.gesture_detector import (GestureAction, GestureRecognizer, HoldTrigger, PinchPhase,
                                     PlayerGestureTracker, Pose, analyse_hand, pinch_distance)
from vision.hand_detector import Hand
from vision.player_tracker import PlayerSnapshot, TrackStatus
from vision.smoothing import CursorSmoother

FRAME = 1 / 30
OPEN = make_hand(pinch_gap=1.0)
POINTING = make_hand(fingers="ECCC")
PINCHED = make_hand(pinch_gap=0.1)
FIST = make_hand(fingers="CCCC", pinch_gap=0.1)  # Thumb near the index, but it's a fist.


def tracked(hand: Hand, player_id: int = 1) -> PlayerSnapshot:
    return PlayerSnapshot(player_id, TrackStatus.TRACKED, hand, 0)


class PoseTests(unittest.TestCase):
    def test_open_palm(self) -> None:
        pose = analyse_hand(make_hand(fingers="EEEE"))
        self.assertTrue(pose.is_open_palm)
        self.assertFalse(pose.is_fist or pose.is_pointing)

    def test_relaxed_hand_is_not_open_palm(self) -> None:
        """Four straight fingers with the thumb resting in is a relaxed hand, not ✋."""
        pose = analyse_hand(make_hand(fingers="EEEE", thumb_tucked=True))
        self.assertTrue(all(pose.extended))
        self.assertFalse(pose.is_open_palm)

    def test_point(self) -> None:
        pose = analyse_hand(POINTING)
        self.assertTrue(pose.is_pointing)
        self.assertFalse(pose.is_open_palm or pose.is_fist)

    def test_fist(self) -> None:
        self.assertTrue(analyse_hand(make_hand(fingers="CCCC")).is_fist)

    def test_pinch_distance_is_scale_invariant(self) -> None:
        near = pinch_distance(make_hand(scale=0.25, pinch_gap=0.2))
        far = pinch_distance(make_hand(scale=0.06, pinch_gap=0.2))
        self.assertAlmostEqual(near, far, places=6)
        self.assertLess(pinch_distance(PINCHED), config.PINCH_THRESHOLD)
        self.assertGreater(pinch_distance(OPEN), config.PINCH_RELEASE_THRESHOLD)


class HoldTriggerTests(unittest.TestCase):
    def test_fires_once_after_hold_time(self) -> None:
        trigger = HoldTrigger(hold_time=0.3, release_time=0.1)
        fired = [trigger.update(True, t * FRAME) for t in range(60)]
        self.assertEqual(fired.count(True), 1)
        self.assertEqual(fired.index(True), 9)  # 9 frames * 1/30 s = 0.3 s

    def test_flicker_does_not_rearm(self) -> None:
        trigger = HoldTrigger(hold_time=0.1, release_time=0.1)
        pattern = [True] * 6 + [False] + [True] * 6  # One open frame mid-hold.
        fired = [trigger.update(c, t * FRAME) for t, c in enumerate(pattern)]
        self.assertEqual(fired.count(True), 1)

    def test_rearms_after_real_release(self) -> None:
        trigger = HoldTrigger(hold_time=0.1, release_time=0.1)
        pattern = [True] * 6 + [False] * 5 + [True] * 6
        fired = [trigger.update(c, t * FRAME) for t, c in enumerate(pattern)]
        self.assertEqual(fired.count(True), 2)

    def test_short_touch_never_fires(self) -> None:
        trigger = HoldTrigger(hold_time=0.3, release_time=0.1)
        pattern = [True] * 3 + [False] * 10
        self.assertFalse(any(trigger.update(c, t * FRAME) for t, c in enumerate(pattern)))

    def test_blocked_while_not_allowed(self) -> None:
        trigger = HoldTrigger(hold_time=0.1, release_time=0.1)
        fired = [trigger.update(True, t * FRAME, allowed=t > 10) for t in range(20)]
        self.assertFalse(any(fired))  # Hold completed while blocked; no late firing.
        self.assertTrue(trigger.blocked)


class PinchTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = PlayerGestureTracker(player_id=1)
        self.now = 0.0
        self.events = []

    def feed(self, hand: Hand | None, frames: int = 1, status: TrackStatus = TrackStatus.TRACKED):
        state = None
        for _ in range(frames):
            self.now += FRAME
            snapshot = PlayerSnapshot(1, status if hand else TrackStatus.ABSENT, hand,
                                      0 if status is TrackStatus.TRACKED else None)
            state, events = self.tracker.update(snapshot, self.now)
            self.events.extend(events)
        return state

    def selects(self) -> int:
        return sum(1 for e in self.events if e.action is GestureAction.SELECT)

    def test_one_pinch_one_select_even_when_held_long(self) -> None:
        self.feed(OPEN, 5)
        state = self.feed(PINCHED, 90)  # Held for 3 seconds.
        self.assertEqual(self.selects(), 1)
        self.assertIs(state.pinch_phase, PinchPhase.TRIGGERED)
        self.assertIs(state.pose, Pose.PINCH)

    def test_pinch_needs_hold_time(self) -> None:
        self.feed(OPEN, 5)
        frames_needed = math.ceil(config.PINCH_HOLD_TIME / FRAME)
        state = self.feed(PINCHED, frames_needed - 1)
        self.assertEqual(self.selects(), 0)
        self.assertIs(state.pinch_phase, PinchPhase.HOLD)
        self.assertGreater(state.pinch_progress, 0.5)
        self.feed(PINCHED, 2)
        self.assertEqual(self.selects(), 1)

    def test_accidental_touch_is_ignored(self) -> None:
        self.feed(OPEN, 5)
        self.feed(PINCHED, 2)
        self.feed(OPEN, 10)
        self.assertEqual(self.selects(), 0)

    def test_hysteresis_keeps_pinch_between_thresholds(self) -> None:
        middle = (config.PINCH_THRESHOLD + config.PINCH_RELEASE_THRESHOLD) / 2
        between = make_hand(pinch_gap=middle)
        self.feed(OPEN, 3)
        self.assertIsNot(self.feed(between, 3).pose, Pose.PINCH)  # Not closed from open.
        self.feed(PINCHED, 3)
        self.assertIs(self.feed(between, 3).pose, Pose.PINCH)  # Stays closed.

    def test_noisy_frames_during_hold_do_not_double_fire(self) -> None:
        self.feed(OPEN, 5)
        for _ in range(10):  # Pinch with a single "open" noise frame every 6 frames.
            self.feed(PINCHED, 5)
            self.feed(OPEN, 1)
        self.assertEqual(self.selects(), 1)

    def test_second_pinch_after_release_and_cooldown(self) -> None:
        self.feed(OPEN, 5)
        self.feed(PINCHED, 15)
        self.feed(OPEN, math.ceil(config.ACTION_COOLDOWN / FRAME) + 5)
        self.feed(PINCHED, 15)
        self.assertEqual(self.selects(), 2)

    def test_quick_repinch_during_cooldown_is_ignored(self) -> None:
        self.feed(OPEN, 5)
        hold = math.ceil(config.PINCH_HOLD_TIME / FRAME) + 1
        self.feed(PINCHED, hold)
        self.feed(OPEN, math.ceil(config.GESTURE_RELEASE_TIME / FRAME) + 1)
        state = self.feed(PINCHED, hold)  # Second pinch completes inside the cooldown.
        self.assertGreater(state.cooldown_remaining, 0.0)
        self.assertEqual(self.selects(), 1)
        self.assertIs(state.pinch_phase, PinchPhase.BLOCKED)
        self.feed(PINCHED, 30)  # Still held after the cooldown ends: no late firing.
        self.assertEqual(self.selects(), 1)

    def test_event_uses_position_from_before_the_pinch(self) -> None:
        target = make_hand(x=0.3, y=0.6, pinch_gap=1.0)
        self.feed(target, 20)  # Hovering over the target; cursor settles.
        dragged = make_hand(x=0.36, y=0.64, pinch_gap=0.1)  # Closing drags the fingertip.
        self.feed(dragged, 15)
        event = next(e for e in self.events if e.action is GestureAction.SELECT)
        expected = (target.index_tip.x, target.index_tip.y)
        self.assertAlmostEqual(event.position[0], expected[0], delta=0.01)
        self.assertAlmostEqual(event.position[1], expected[1], delta=0.01)

    def test_quick_move_then_pinch_uses_the_new_target(self) -> None:
        self.feed(make_hand(x=0.3, y=0.6, pinch_gap=1.0), 20)  # Hovering the old target.
        new_target = make_hand(x=0.45, y=0.6, pinch_gap=0.1)  # Jump one cell and pinch.
        self.feed(new_target, 15)
        event = next(e for e in self.events if e.action is GestureAction.SELECT)
        self.assertAlmostEqual(event.position[0], new_target.index_tip.x, delta=0.01)

    def test_fist_with_thumb_near_index_is_cancel_not_select(self) -> None:
        self.feed(OPEN, 5)
        state = self.feed(FIST, 30)
        self.assertIs(state.pose, Pose.FIST)
        self.assertEqual(self.selects(), 0)
        self.assertEqual([e.action for e in self.events], [GestureAction.CANCEL])

    def test_open_palm_held_gives_one_menu_event(self) -> None:
        self.feed(OPEN, 60)
        self.assertEqual([e.action for e in self.events], [GestureAction.MENU])

    def test_relaxed_open_hand_never_pauses(self) -> None:
        self.feed(make_hand(thumb_tucked=True), 120)
        self.assertEqual(self.events, [])

    def test_moving_open_palm_never_pauses(self) -> None:
        for step in range(120):  # Open hand sweeping across the board for 4 s.
            self.feed(make_hand(x=0.2 + (step % 40) * 0.015, pinch_gap=1.0))
        self.assertEqual(self.events, [])

    def test_open_palm_needs_full_hold_time(self) -> None:
        frames = int(config.OPEN_PALM_HOLD_TIME / FRAME) - 3
        self.feed(OPEN, frames)
        self.assertEqual(self.events, [])

    def test_pointing_moves_cursor_without_events(self) -> None:
        for step in range(30):
            state = self.feed(make_hand(x=0.2 + step * 0.01, fingers="ECCC"))
        self.assertIs(state.pose, Pose.POINT)
        self.assertEqual(self.events, [])
        self.assertAlmostEqual(state.cursor[0], state.raw_tip[0], delta=0.02)

    def test_lost_hand_freezes_and_absent_resets(self) -> None:
        self.feed(OPEN, 5)
        self.feed(PINCHED, 3)
        lost = self.feed(PINCHED, 3, status=TrackStatus.LOST)
        self.assertFalse(lost.tracked)
        self.assertIsNotNone(lost.cursor)  # Last cursor kept while lost.
        self.assertEqual(self.selects(), 0)  # Timers do not run while lost.
        absent = self.feed(None, 1)
        self.assertIsNone(absent.cursor)
        self.assertIs(absent.pinch_phase, PinchPhase.IDLE)


class RecognizerTests(unittest.TestCase):
    def test_players_are_independent(self) -> None:
        recognizer = GestureRecognizer()
        events = []
        now = 0.0
        for _ in range(30):
            now += FRAME
            _, new = recognizer.update((tracked(PINCHED, 1), tracked(OPEN, 2)), now)
            events.extend(new)
        self.assertEqual([(e.player_id, e.action) for e in events],
                         [(1, GestureAction.SELECT)])


class SmoothingTests(unittest.TestCase):
    def test_no_smoothing_is_raw(self) -> None:
        smoother = CursorSmoother(smoothing=0.0)
        smoother.update((0.5, 0.5), 0.0)
        self.assertEqual(smoother.update((0.6, 0.4), FRAME), (0.6, 0.4))

    def test_jitter_is_reduced_when_still(self) -> None:
        smoother = CursorSmoother(smoothing=0.6, fast_speed=1.5)
        jitter = [(0.5 + (0.004 if i % 2 else -0.004), 0.5) for i in range(60)]
        outputs = [smoother.update(p, i * FRAME)[0] for i, p in enumerate(jitter)]
        raw_spread = max(p[0] for p in jitter) - min(p[0] for p in jitter)
        smooth_spread = max(outputs[30:]) - min(outputs[30:])
        self.assertLess(smooth_spread, raw_spread * 0.5)

    def test_fast_motion_is_not_delayed(self) -> None:
        smoother = CursorSmoother(smoothing=0.6, fast_speed=1.5)
        smoother.update((0.1, 0.5), 0.0)
        result = smoother.update((0.3, 0.5), FRAME)  # 6 widths/s: faster than fast_speed.
        self.assertAlmostEqual(result[0], 0.3)


@unittest.skipUnless(config.HAND_MODEL_FILE.is_file(), "hand model not downloaded")
class RealPhotoPoseTests(unittest.TestCase):
    def test_sample_photo_relaxed_open_hands(self) -> None:
        """Relaxed open hands must be fully *released* (above the release threshold)
        and must not count as a deliberate ✋ (which would pause the game)."""
        import cv2

        from vision.hand_detector import HandDetector

        detector = HandDetector()
        try:
            image = cv2.imread(str(Path(__file__).parent / "data" / "woman_hands.jpg"))
            hands = detector.detect(image, 0)
        finally:
            detector.close()
        self.assertEqual(len(hands), 2)
        for hand in hands:
            self.assertGreater(pinch_distance(hand), config.PINCH_RELEASE_THRESHOLD)
            self.assertFalse(analyse_hand(hand).is_open_palm)


if __name__ == "__main__":
    unittest.main()
