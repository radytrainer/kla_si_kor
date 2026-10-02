"""HandDetector tests using real MediaPipe on a public sample photo.

tests/data/woman_hands.jpg is MediaPipe's own hand-landmarker example image
(two hands). No webcam is used.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import cv2
import numpy as np

import config
from vision import landmarks as lm
from vision.hand_detector import (BoundingBox, Hand, HandDetector, HandDetectorError, Landmark,
                                  ensure_model_file)

SAMPLE_IMAGE = Path(__file__).parent / "data" / "woman_hands.jpg"
FRAME_MS = 33


@unittest.skipUnless(config.HAND_MODEL_FILE.is_file(), "hand model not downloaded")
class RealDetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.detector = HandDetector()
        cls.image = cv2.imread(str(SAMPLE_IMAGE))
        cls.timestamp = 0

    @classmethod
    def tearDownClass(cls) -> None:
        cls.detector.close()

    def detect(self, image: np.ndarray) -> tuple[Hand, ...]:
        type(self).timestamp += FRAME_MS
        return self.detector.detect(image, self.timestamp)

    def test_detects_both_hands_with_21_landmarks(self) -> None:
        hands = self.detect(self.image)
        self.assertEqual(len(hands), 2)
        for hand in hands:
            self.assertEqual(len(hand.landmarks), lm.LANDMARK_COUNT)
            self.assertGreater(hand.confidence, 0.5)
            self.assertIn(hand.handedness, ("Left", "Right"))
            for point in hand.landmarks:
                self.assertTrue(-0.1 <= point.x <= 1.1 and -0.1 <= point.y <= 1.1)
        self.assertEqual({hand.handedness for hand in hands}, {"Left", "Right"})

    def test_hand_geometry_helpers(self) -> None:
        hand = self.detect(self.image)[0]
        box = hand.bounding_box
        for point in hand.landmarks:
            self.assertTrue(box.left <= point.x <= box.right)
            self.assertTrue(box.top <= point.y <= box.bottom)
        self.assertGreater(hand.size, 0.0)
        self.assertEqual(hand.index_tip, hand.landmarks[lm.INDEX_TIP])
        self.assertEqual(hand.thumb_tip, hand.landmarks[lm.THUMB_TIP])

    def test_mirrored_image_swaps_hand_positions(self) -> None:
        normal = sorted(self.detect(self.image), key=lambda h: h.center[0])
        flipped = cv2.flip(self.image, 1)
        # VIDEO mode tracks hands from the previous frame; after this sudden jump the
        # tracker loses them for one frame and re-detects them on the next.
        self.detect(flipped)
        mirrored = sorted(self.detect(flipped), key=lambda h: h.center[0])
        self.assertEqual(len(mirrored), 2)
        # The left-most hand in the mirror is the right-most hand in the original.
        self.assertAlmostEqual(mirrored[0].center[0], 1.0 - normal[1].center[0], delta=0.05)

    def test_blank_image_has_no_hands(self) -> None:
        blank = np.zeros((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), dtype=np.uint8)
        self.assertEqual(self.detect(blank), ())

    def test_repeated_timestamp_is_accepted(self) -> None:
        self.detector.detect(self.image, 10**9)
        self.detector.detect(self.image, 10**9)  # Would raise inside MediaPipe unless handled.


class ModelFileTests(unittest.TestCase):
    def test_missing_model_gives_friendly_error(self) -> None:
        with self.assertRaises(HandDetectorError) as context:
            HandDetector(model_path=Path("does/not/exist.task"))
        self.assertIn("--download-model", str(context.exception))

    def test_ensure_model_file_returns_existing_path(self) -> None:
        if config.HAND_MODEL_FILE.is_file():
            self.assertEqual(ensure_model_file(), config.HAND_MODEL_FILE)


class HandDataTests(unittest.TestCase):
    def test_bounding_box_center(self) -> None:
        self.assertEqual(BoundingBox(0.2, 0.4, 0.6, 0.8).center, (0.4, 0.6000000000000001))

    def test_synthetic_hand_accessors(self) -> None:
        points = tuple(Landmark(i / 100, i / 50) for i in range(lm.LANDMARK_COUNT))
        hand = Hand(points, "Right", 0.9)
        self.assertEqual(hand.wrist, points[0])
        self.assertEqual(hand.pinky_tip, points[20])
        self.assertEqual(hand.bounding_box, BoundingBox(0.0, 0.0, 0.2, 0.4))


if __name__ == "__main__":
    unittest.main()
