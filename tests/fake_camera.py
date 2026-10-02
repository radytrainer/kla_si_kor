"""A fake capture device so tests never touch the real webcam."""

from __future__ import annotations

import threading

import numpy as np

import config
from camera.camera import Camera

FRAME_DELAY = 0.005  # seconds; keeps the fake from spinning a CPU core


class FakeCapture:
    """Mimics cv2.VideoCapture. Each read returns a frame whose left half is white.

    ``fail_after`` makes reads fail after N frames (simulates unplugging).
    """

    def __init__(self, opened: bool = True, fail_after: int | None = None) -> None:
        self._opened = opened
        self._fail_after = fail_after
        self.reads = 0
        self.released = False
        self._wait = threading.Event()

    def isOpened(self) -> bool:  # noqa: N802 - OpenCV naming
        return self._opened

    def read(self) -> tuple[bool, np.ndarray | None]:
        self._wait.wait(FRAME_DELAY)
        self.reads += 1
        if self._fail_after is not None and self.reads > self._fail_after:
            return False, None
        image = np.zeros((config.CAMERA_HEIGHT, config.CAMERA_WIDTH, 3), dtype=np.uint8)
        image[:, : config.CAMERA_WIDTH // 2] = 255
        return True, image

    def release(self) -> None:
        self.released = True


def make_fake_camera(mirror: bool = False) -> Camera:
    return Camera(capture_factory=FakeCapture, mirror=mirror)


class FakeDetector:
    """Stands in for HandDetector: returns ``hands`` for every frame."""

    def __init__(self, hands: tuple = (), fail: bool = False) -> None:
        self.hands = hands
        self.fail = fail
        self.calls = 0
        self.closed = False

    def detect(self, image_bgr: np.ndarray, timestamp_ms: int) -> tuple:
        self.calls += 1
        if self.fail:
            raise RuntimeError("detector exploded")
        return self.hands

    def close(self) -> None:
        self.closed = True
