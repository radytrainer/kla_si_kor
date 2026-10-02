"""Hand detection with the MediaPipe Tasks HandLandmarker.

This is the only module that talks to MediaPipe. It converts MediaPipe
results into small immutable :class:`Hand` objects used by the rest of the
vision layer. Coordinates are normalised to the (mirrored) camera image:
x and y are in 0..1, (0, 0) is the top-left corner.
"""

from __future__ import annotations

import math
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

import numpy as np

import config
from vision import landmarks as lm

STDERR_FD = 2


@contextmanager
def quiet_native_stderr(enabled: bool = True) -> Iterator[None]:
    """Temporarily send native (C++) stderr to the null device.

    MediaPipe 1.x prints harmless start-up warnings from C++ that ignore the
    GLOG/TF environment variables. They only appear while the landmarker is
    created and on its first detection, so only those calls are wrapped.
    """
    if not enabled or sys.stderr is None:  # Windowed .exe: there is no console to quiet.
        yield
        return
    sys.stderr.flush()
    try:
        saved = os.dup(STDERR_FD)
    except OSError:  # No usable stderr descriptor.
        yield
        return
    try:
        with open(os.devnull, "w") as null:
            os.dup2(null.fileno(), STDERR_FD)
            try:
                yield
            finally:
                sys.stderr.flush()
                os.dup2(saved, STDERR_FD)
    finally:
        os.close(saved)


class HandDetectorError(RuntimeError):
    """Raised with a user-friendly message when the detector cannot start."""


@dataclass(frozen=True)
class Landmark:
    x: float
    y: float
    z: float = 0.0  # Relative depth (smaller = closer to the camera).


@dataclass(frozen=True)
class BoundingBox:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def center(self) -> tuple[float, float]:
        return (self.left + self.right) / 2, (self.top + self.bottom) / 2


@dataclass(frozen=True)
class Hand:
    """One detected hand in normalised image coordinates."""

    landmarks: tuple[Landmark, ...]
    handedness: str  # "Left" or "Right" as reported by MediaPipe.
    confidence: float  # Handedness classification score, 0..1.

    def point(self, index: int) -> Landmark:
        return self.landmarks[index]

    @property
    def wrist(self) -> Landmark:
        return self.landmarks[lm.WRIST]

    @property
    def thumb_tip(self) -> Landmark:
        return self.landmarks[lm.THUMB_TIP]

    @property
    def index_tip(self) -> Landmark:
        return self.landmarks[lm.INDEX_TIP]

    @property
    def middle_tip(self) -> Landmark:
        return self.landmarks[lm.MIDDLE_TIP]

    @property
    def ring_tip(self) -> Landmark:
        return self.landmarks[lm.RING_TIP]

    @property
    def pinky_tip(self) -> Landmark:
        return self.landmarks[lm.PINKY_TIP]

    @property
    def bounding_box(self) -> BoundingBox:
        xs = [p.x for p in self.landmarks]
        ys = [p.y for p in self.landmarks]
        return BoundingBox(min(xs), min(ys), max(xs), max(ys))

    @property
    def center(self) -> tuple[float, float]:
        return self.bounding_box.center

    @property
    def size(self) -> float:
        """Wrist to middle-finger knuckle distance: a scale reference for gestures."""
        wrist, knuckle = self.wrist, self.landmarks[lm.MIDDLE_MCP]
        return math.hypot(knuckle.x - wrist.x, knuckle.y - wrist.y)


def ensure_model_file(path: Path = config.HAND_MODEL_FILE) -> Path:
    """Return the model path or raise a helpful error if it is missing."""
    if not path.is_file():
        raise HandDetectorError(
            f"Hand model not found: {path.name}. "
            "Run  python main.py --download-model  (needs internet once)."
        )
    return path


class HandDetector:
    """Wraps MediaPipe HandLandmarker in VIDEO mode (uses temporal tracking)."""

    def __init__(self, model_path: Path = config.HAND_MODEL_FILE,
                 max_hands: int = config.MAX_NUM_HANDS,
                 detection_confidence: float = config.HAND_DETECTION_CONFIDENCE,
                 presence_confidence: float = config.HAND_PRESENCE_CONFIDENCE,
                 tracking_confidence: float = config.HAND_TRACKING_CONFIDENCE) -> None:
        ensure_model_file(model_path)
        try:
            import mediapipe as mp
            from mediapipe.tasks.python import vision
            from mediapipe.tasks.python.core.base_options import BaseOptions

            options = vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(model_path)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=max_hands,
                min_hand_detection_confidence=detection_confidence,
                min_hand_presence_confidence=presence_confidence,
                min_tracking_confidence=tracking_confidence,
            )
            with quiet_native_stderr(not config.DEBUG_MODE_NATIVE_LOGS):
                self._landmarker = vision.HandLandmarker.create_from_options(options)
        except Exception as exc:  # noqa: BLE001 - report any init failure clearly
            raise HandDetectorError(f"MediaPipe could not start: {exc}") from exc
        self._mp = mp
        self._last_timestamp_ms = -1
        self._first_detection = True

    def detect(self, image_bgr: np.ndarray, timestamp_ms: int) -> tuple[Hand, ...]:
        """Detect hands in a BGR image. Timestamps must increase (VIDEO mode)."""
        # MediaPipe rejects non-increasing timestamps; nudge duplicates forward.
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        rgb = np.ascontiguousarray(image_bgr[:, :, ::-1])
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        with quiet_native_stderr(self._first_detection and not config.DEBUG_MODE_NATIVE_LOGS):
            result = self._landmarker.detect_for_video(image, timestamp_ms)
        self._first_detection = False
        hands = []
        for points, categories in zip(result.hand_landmarks, result.handedness):
            best = categories[0]
            hands.append(Hand(
                landmarks=tuple(Landmark(p.x, p.y, p.z) for p in points),
                handedness=best.category_name,
                confidence=float(best.score),
            ))
        return tuple(hands)

    def close(self) -> None:
        self._landmarker.close()
