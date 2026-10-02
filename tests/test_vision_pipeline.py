"""VisionPipeline tests with a fake camera and fake detector (fast, no webcam)."""

from __future__ import annotations

import unittest

from tests.fake_camera import FakeDetector, make_fake_camera
from tests.test_camera import wait_until
from vision.hand_detector import Hand, HandDetectorError, Landmark
from vision.landmarks import LANDMARK_COUNT
from vision.pipeline import PipelineStatus, VisionPipeline

HAND = Hand(tuple(Landmark(0.5, 0.5) for _ in range(LANDMARK_COUNT)), "Right", 0.9)


class VisionPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pipelines: list[VisionPipeline] = []

    def tearDown(self) -> None:
        for pipeline in self.pipelines:
            pipeline.stop()

    def make(self, factory) -> VisionPipeline:
        pipeline = VisionPipeline(make_fake_camera(), factory)
        self.pipelines.append(pipeline)
        return pipeline

    def test_publishes_results_for_new_frames(self) -> None:
        detector = FakeDetector(hands=(HAND,))
        pipeline = self.make(lambda: detector)
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.latest_result() is not None))
        self.assertIs(pipeline.status, PipelineStatus.RUNNING)
        result = pipeline.latest_result()
        self.assertEqual(result.hands, (HAND,))
        self.assertGreaterEqual(result.detection_ms, 0.0)
        first = result.frame.index
        self.assertTrue(wait_until(lambda: pipeline.latest_result().frame.index > first))
        self.assertTrue(wait_until(lambda: pipeline.fps > 0))

    def test_results_include_tracked_players(self) -> None:
        from tests.test_player_tracker import hand_at
        from vision.player_tracker import TrackStatus

        pipeline = self.make(lambda: FakeDetector(hands=(hand_at(0.8), hand_at(0.2))))
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.latest_result() is not None))
        result = pipeline.latest_result()
        self.assertIs(result.player(1).status, TrackStatus.TRACKED)
        self.assertEqual(result.player(1).hand_index, 1)  # The hand on the left.
        self.assertEqual(result.player(2).hand_index, 0)

    def test_held_pinch_is_delivered_exactly_once(self) -> None:
        import time

        from tests.hand_factory import make_hand
        from vision.gesture_detector import GestureAction

        pinched_on_left = make_hand(x=0.3, pinch_gap=0.1)
        pipeline = self.make(lambda: FakeDetector(hands=(pinched_on_left,)))
        pipeline.start()
        events = []
        deadline = time.monotonic() + 1.5  # Far longer than PINCH_HOLD_TIME.
        while time.monotonic() < deadline:
            events.extend(pipeline.drain_events())  # UI polls every frame.
            time.sleep(1 / 60)
        self.assertEqual([(e.player_id, e.action) for e in events],
                         [(1, GestureAction.SELECT)])
        self.assertEqual(pipeline.drain_events(), [])

    def test_stop_discards_pending_events(self) -> None:
        from tests.hand_factory import make_hand

        pipeline = self.make(lambda: FakeDetector(hands=(make_hand(x=0.3, pinch_gap=0.1),)))
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.latest_result() is not None
                                   and pipeline.latest_result().gesture(1).pinch_progress >= 1))
        pipeline.stop()
        self.assertEqual(pipeline.drain_events(), [])

    def test_each_frame_detected_once(self) -> None:
        detector = FakeDetector()
        pipeline = self.make(lambda: detector)
        pipeline.start()
        self.assertTrue(wait_until(lambda: detector.calls >= 5))
        pipeline.stop()
        frames_seen = pipeline.camera  # Camera stopped; frame counter no longer grows.
        self.assertIsNone(frames_seen.latest_frame())
        self.assertTrue(detector.closed)

    def test_missing_model_reports_error(self) -> None:
        def factory():
            raise HandDetectorError("Hand model not found: hand_landmarker.task")

        pipeline = self.make(factory)
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.status is PipelineStatus.ERROR))
        self.assertIn("Hand model not found", pipeline.message)
        self.assertIsNone(pipeline.latest_result())

    def test_detector_that_always_fails_reports_error(self) -> None:
        pipeline = self.make(lambda: FakeDetector(fail=True))
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.status is PipelineStatus.ERROR))
        self.assertIn("keeps failing", pipeline.message)

    def test_stop_and_restart(self) -> None:
        pipeline = self.make(lambda: FakeDetector())
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.latest_result() is not None))
        pipeline.stop()
        self.assertIs(pipeline.status, PipelineStatus.STOPPED)
        self.assertIsNone(pipeline.latest_result())
        pipeline.start()
        self.assertTrue(wait_until(lambda: pipeline.latest_result() is not None))


if __name__ == "__main__":
    unittest.main()
