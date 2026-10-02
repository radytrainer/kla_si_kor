"""PlayerTracker tests with synthetic hands at known positions."""

from __future__ import annotations

import unittest

import config
from vision.hand_detector import Hand, Landmark
from vision.landmarks import LANDMARK_COUNT
from vision.player_tracker import (HandednessRule, PlayerTracker, ScreenSideRule, TrackStatus,
                                   best_matching)

FRAME = 1 / 30
HAND_HALF_SIZE = 0.05


def hand_at(x: float, y: float = 0.5, handedness: str = "Right") -> Hand:
    """A synthetic hand whose bounding-box centre is (x, y)."""
    points = [Landmark(x - HAND_HALF_SIZE, y - HAND_HALF_SIZE),
              Landmark(x + HAND_HALF_SIZE, y + HAND_HALF_SIZE)]
    points += [Landmark(x, y)] * (LANDMARK_COUNT - len(points))
    return Hand(tuple(points), handedness, 0.9)


class TrackerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tracker = PlayerTracker(ScreenSideRule("LEFT"))
        self.now = 0.0

    def step(self, *hands: Hand, dt: float = FRAME):
        self.now += dt
        return {p.player_id: p for p in self.tracker.update(tuple(hands), self.now)}

    def player_x(self, players, player_id: int) -> float:
        return players[player_id].hand.center[0]


class InitialAssignmentTests(TrackerTestCase):
    def test_left_hand_is_player_1_right_hand_is_player_2(self) -> None:
        players = self.step(hand_at(0.8), hand_at(0.2))  # Detection order: right first.
        self.assertEqual(players[1].status, TrackStatus.TRACKED)
        self.assertAlmostEqual(self.player_x(players, 1), 0.2)
        self.assertAlmostEqual(self.player_x(players, 2), 0.8)
        self.assertEqual((players[1].hand_index, players[2].hand_index), (1, 0))

    def test_no_hands(self) -> None:
        players = self.step()
        self.assertEqual({p.status for p in players.values()}, {TrackStatus.ABSENT})
        self.assertFalse(players[1].present)

    def test_single_hand_only_assigns_its_side(self) -> None:
        players = self.step(hand_at(0.7))
        self.assertIs(players[1].status, TrackStatus.ABSENT)
        self.assertIs(players[2].status, TrackStatus.TRACKED)

    def test_player_1_side_can_be_swapped(self) -> None:
        self.tracker = PlayerTracker(ScreenSideRule("RIGHT"))
        players = self.step(hand_at(0.2), hand_at(0.8))
        self.assertAlmostEqual(self.player_x(players, 1), 0.8)

    def test_handedness_rule(self) -> None:
        self.tracker = PlayerTracker(HandednessRule())
        players = self.step(hand_at(0.8, handedness="Left"), hand_at(0.2, handedness="Right"))
        self.assertAlmostEqual(self.player_x(players, 1), 0.8)
        self.assertAlmostEqual(self.player_x(players, 2), 0.2)

    def test_second_hand_on_same_side_is_ignored(self) -> None:
        players = self.step(hand_at(0.2), hand_at(0.3))
        self.assertIs(players[1].status, TrackStatus.TRACKED)
        self.assertIs(players[2].status, TrackStatus.ABSENT)


class StabilityTests(TrackerTestCase):
    def test_identity_stable_when_detection_order_flips(self) -> None:
        self.step(hand_at(0.2), hand_at(0.8))
        for frame in range(20):
            hands = (hand_at(0.2), hand_at(0.8))
            players = self.step(*(hands if frame % 2 else hands[::-1]))
            self.assertAlmostEqual(self.player_x(players, 1), 0.2)
            self.assertAlmostEqual(self.player_x(players, 2), 0.8)

    def test_player_can_reach_across_the_middle(self) -> None:
        self.step(hand_at(0.2), hand_at(0.9))
        x = 0.2
        while x < 0.75:  # Player 1 reaches into Player 2's half.
            x += 0.03
            players = self.step(hand_at(x), hand_at(0.9))
        self.assertAlmostEqual(self.player_x(players, 1), x)
        self.assertAlmostEqual(self.player_x(players, 2), 0.9)

    def test_hands_passing_each_other_do_not_swap(self) -> None:
        self.step(hand_at(0.2, 0.3), hand_at(0.8, 0.7))
        left, right = 0.2, 0.8
        for _ in range(20):  # Cross over: P1 moves right (top), P2 left (bottom).
            left, right = left + 0.03, right - 0.03
            players = self.step(hand_at(right, 0.7), hand_at(left, 0.3))
        self.assertAlmostEqual(self.player_x(players, 1), left)  # Now on the right.
        self.assertAlmostEqual(self.player_x(players, 2), right)  # Now on the left.

    def test_new_hand_on_player_side_is_ignored_while_player_tracked(self) -> None:
        self.step(hand_at(0.2), hand_at(0.8))
        players = self.step(hand_at(0.2), hand_at(0.8), hand_at(0.4))
        self.assertAlmostEqual(self.player_x(players, 1), 0.2)
        self.assertAlmostEqual(self.player_x(players, 2), 0.8)


class LostHandTests(TrackerTestCase):
    def test_brief_dropout_keeps_identity(self) -> None:
        self.step(hand_at(0.2), hand_at(0.8))
        players = self.step(hand_at(0.8))  # Player 1 flickers out for one frame.
        self.assertIs(players[1].status, TrackStatus.LOST)
        self.assertAlmostEqual(self.player_x(players, 1), 0.2)  # Last position kept.
        self.assertAlmostEqual(players[1].lost_for, FRAME)
        players = self.step(hand_at(0.22), hand_at(0.8))
        self.assertIs(players[1].status, TrackStatus.TRACKED)

    def test_dropout_while_reaching_across_is_reacquired(self) -> None:
        self.step(hand_at(0.2), hand_at(0.9))
        for x in (0.3, 0.4, 0.5, 0.6, 0.65):
            self.step(hand_at(x), hand_at(0.9))
        self.step(hand_at(0.9))  # Player 1 (at 0.65, in P2's half) lost for a frame.
        players = self.step(hand_at(0.67), hand_at(0.9))
        self.assertAlmostEqual(self.player_x(players, 1), 0.67)
        self.assertAlmostEqual(self.player_x(players, 2), 0.9)

    def test_fast_jump_across_the_midline_is_recovered(self) -> None:
        # Player 1 reaches into Player 2's half; a dropout plus a fast move puts the
        # hand far from its last position, on Player 2's side. It must stay Player 1.
        self.step(hand_at(0.2), hand_at(0.9))
        for x in (0.3, 0.4, 0.5, 0.55):
            self.step(hand_at(x), hand_at(0.9))
        self.step(hand_at(0.9))  # Player 1 dropped out for a frame.
        players = self.step(hand_at(0.55 + config.TRACK_MAX_DISTANCE + 0.02), hand_at(0.9))
        self.assertIs(players[1].status, TrackStatus.TRACKED)
        self.assertAlmostEqual(self.player_x(players, 2), 0.9)

    def test_extra_hand_is_not_given_to_an_absent_player(self) -> None:
        self.step(hand_at(0.8))  # Only Player 2 has ever been seen.
        players = self.step(hand_at(0.8), hand_at(0.7))
        self.assertIs(players[1].status, TrackStatus.ABSENT)

    def test_absent_after_grace_time(self) -> None:
        self.step(hand_at(0.2), hand_at(0.8))
        players = self.step(hand_at(0.8), dt=config.HAND_LOST_GRACE_TIME / 2)
        self.assertIs(players[1].status, TrackStatus.LOST)
        players = self.step(hand_at(0.8), dt=config.HAND_LOST_GRACE_TIME)
        self.assertIs(players[1].status, TrackStatus.ABSENT)
        self.assertIsNone(players[1].hand)

    def test_returning_hand_after_absence_uses_side_rule(self) -> None:
        self.step(hand_at(0.2), hand_at(0.8))
        self.step(dt=config.HAND_LOST_GRACE_TIME + 0.1)
        players = self.step(hand_at(0.7), hand_at(0.3))
        self.assertAlmostEqual(self.player_x(players, 1), 0.3)
        self.assertAlmostEqual(self.player_x(players, 2), 0.7)

    def test_teleport_beyond_max_distance_is_a_new_hand(self) -> None:
        self.step(hand_at(0.1))
        players = self.step(hand_at(0.1 + config.TRACK_MAX_DISTANCE + 0.5))  # Right side.
        self.assertIs(players[2].status, TrackStatus.TRACKED)
        self.assertIs(players[1].status, TrackStatus.LOST)

    def test_reset(self) -> None:
        self.step(hand_at(0.2), hand_at(0.8))
        self.tracker.reset()
        self.assertEqual({p.status for p in self.tracker.players}, {TrackStatus.ABSENT})


class MatchingTests(unittest.TestCase):
    def test_minimum_total_cost_beats_greedy(self) -> None:
        # Greedy would take (0,0)=0.10 and then (1,1)=0.50; the optimum is 0.23.
        costs = [[0.10, 0.11], [0.12, 0.50]]
        self.assertEqual(best_matching(costs, 1.0), {0: 1, 1: 0})

    def test_pairs_above_threshold_are_not_matched(self) -> None:
        self.assertEqual(best_matching([[0.9]], 0.25), {})
        self.assertEqual(best_matching([[0.1, 0.9]], 0.25), {0: 0})

    def test_empty(self) -> None:
        self.assertEqual(best_matching([], 0.25), {})


if __name__ == "__main__":
    unittest.main()


@unittest.skipUnless(config.HAND_MODEL_FILE.is_file(), "hand model not downloaded")
class RealDetectionTrackingTests(unittest.TestCase):
    """Real MediaPipe + tracker: slide the sample photo so Player 1 crosses the midline."""

    FRAMES = 30
    SHIFT = 0.20  # Total horizontal shift, as a fraction of the canvas width.

    def test_identity_survives_crossing_the_midline(self) -> None:
        from pathlib import Path

        import cv2
        import numpy as np

        from vision.hand_detector import HandDetector

        photo = cv2.imread(str(Path(__file__).parent / "data" / "woman_hands.jpg"))
        height, width = photo.shape[:2]
        # Double-width canvas with the photo centred: the woman's hands start at
        # x ~ 0.39 (left of the midline) and x ~ 0.56 (right of it).
        canvas = np.zeros((height, width * 2, 3), dtype=np.uint8)
        offset = width // 2
        canvas[:, offset:offset + width] = photo
        detector = HandDetector()
        tracker = PlayerTracker(ScreenSideRule("LEFT"))
        try:
            trail: list[tuple[float, float]] = []
            for frame in range(self.FRAMES + 1):
                dx = int(self.SHIFT * canvas.shape[1] * frame / self.FRAMES)
                shifted = np.roll(canvas, dx, axis=1)
                hands = detector.detect(shifted, frame * 33)
                players = {p.player_id: p for p in tracker.update(hands, frame / 30)}
                if players[1].status is TrackStatus.TRACKED and \
                        players[2].status is TrackStatus.TRACKED:
                    trail.append((players[1].hand.center[0], players[2].hand.center[0]))
        finally:
            detector.close()
        self.assertGreater(len(trail), self.FRAMES * 0.8, "hands lost too often")
        start, end = trail[0], trail[-1]
        self.assertLess(start[0], 0.5)  # Player 1 began on the left...
        self.assertGreater(end[0], 0.5)  # ...ended on Player 2's side...
        for p1_x, p2_x in trail:  # ...and was never confused with Player 2.
            self.assertLess(p1_x, p2_x)
