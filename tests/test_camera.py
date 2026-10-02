"""Camera tests with a fake capture device (no real webcam needed)."""

from __future__ import annotations

import time
import unittest
from collections.abc import Callable
from unittest import mock

import numpy as np

import config
from camera.camera import Camera, CameraStatus
from tests.fake_camera import FakeCapture

WAIT_TIMEOUT = 3.0
POLL_INTERVAL = 0.01
FAST_RETRY = 0.05


def wait_until(condition: Callable[[], bool], timeout: float = WAIT_TIMEOUT) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(POLL_INTERVAL)
    return condition()


class CameraTests(unittest.TestCase):
    def setUp(self) -> None:
        # Retry quickly so failure/recovery tests finish fast.
        patcher = mock.patch.object(config, "CAMERA_RETRY_INTERVAL", FAST_RETRY)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cameras: list[Camera] = []

    def tearDown(self) -> None:
        for camera in self.cameras:
            camera.stop()

    def make(self, factory, mirror: bool = False) -> Camera:
        camera = Camera(capture_factory=factory, mirror=mirror)
        self.cameras.append(camera)
        return camera

    def test_starts_and_delivers_frames(self) -> None:
        camera = self.make(FakeCapture)
        self.assertIs(camera.status, CameraStatus.STOPPED)
        camera.start()
        self.assertTrue(wait_until(lambda: camera.running))
        self.assertTrue(wait_until(lambda: camera.fps > 0))
        frame = camera.latest_frame()
        self.assertEqual(frame.size, (config.CAMERA_WIDTH, config.CAMERA_HEIGHT))
        first_index = frame.index
        self.assertTrue(wait_until(lambda: camera.latest_frame().index > first_index))

    def test_mirroring_flips_left_and_right(self) -> None:
        plain = self.make(FakeCapture, mirror=False)
        mirrored = self.make(FakeCapture, mirror=True)
        plain.start()
        mirrored.start()
        self.assertTrue(wait_until(lambda: plain.running and mirrored.running))
        self.assertTrue(np.all(plain.latest_frame().image[:, 0] == 255))  # White on left.
        self.assertTrue(np.all(mirrored.latest_frame().image[:, 0] == 0))  # White moved right.

    def test_unavailable_camera_reports_and_keeps_retrying(self) -> None:
        attempts = []

        def factory():
            attempts.append(1)
            return FakeCapture(opened=False)

        camera = self.make(factory)
        camera.start()
        self.assertTrue(wait_until(lambda: camera.status is CameraStatus.UNAVAILABLE))
        self.assertIn("Privacy", camera.message)
        self.assertIsNone(camera.latest_frame())
        self.assertTrue(wait_until(lambda: len(attempts) >= 3))

    def test_factory_exception_is_handled(self) -> None:
        def factory():
            raise RuntimeError("driver crashed")

        camera = self.make(factory)
        camera.start()
        self.assertTrue(wait_until(lambda: camera.status is CameraStatus.UNAVAILABLE))

    def test_disconnect_then_reconnect(self) -> None:
        devices: list[FakeCapture] = []

        def factory():
            # First device dies after 5 frames; the next one works.
            device = FakeCapture(fail_after=5 if not devices else None)
            devices.append(device)
            return device

        camera = self.make(factory)
        with mock.patch.object(config, "CAMERA_MAX_READ_FAILURES", 3):
            camera.start()
            self.assertTrue(wait_until(lambda: len(devices) >= 2))
            self.assertTrue(devices[0].released)
            self.assertTrue(wait_until(lambda: camera.running))

    def test_camera_becomes_available_later(self) -> None:
        attempts = []

        def factory():
            attempts.append(1)
            return FakeCapture(opened=len(attempts) > 2)

        camera = self.make(factory)
        camera.start()
        self.assertTrue(wait_until(lambda: camera.running))

    def test_stop_releases_device_and_clears_frame(self) -> None:
        devices: list[FakeCapture] = []

        def factory():
            devices.append(FakeCapture())
            return devices[-1]

        camera = self.make(factory)
        camera.start()
        self.assertTrue(wait_until(lambda: camera.running))
        camera.stop()
        self.assertIs(camera.status, CameraStatus.STOPPED)
        self.assertIsNone(camera.latest_frame())
        self.assertTrue(devices[-1].released)

    def test_start_twice_and_restart(self) -> None:
        camera = self.make(FakeCapture)
        camera.start()
        camera.start()  # No second thread.
        self.assertTrue(wait_until(lambda: camera.running))
        camera.stop()
        camera.start()
        self.assertTrue(wait_until(lambda: camera.running))


class DarkPictureTests(unittest.TestCase):
    def test_black_frame_is_too_dark(self) -> None:
        from camera.camera import Frame

        black = Frame(np.zeros((4, 4, 3), dtype=np.uint8), 0.0, 1)
        lit = Frame(np.full((4, 4, 3), 120, dtype=np.uint8), 0.0, 2)
        self.assertTrue(black.too_dark)
        self.assertFalse(lit.too_dark)

    def test_check_reports_a_black_picture(self) -> None:
        from app import diagnostics

        class BlackCapture(FakeCapture):
            def read(self):
                ok, image = super().read()
                return ok, image * 0

        black_camera = mock.patch("camera.camera.open_opencv_capture", side_effect=BlackCapture)
        short_sample = mock.patch.object(diagnostics, "CAMERA_PROBE_SAMPLE", 0.2)
        with black_camera, short_sample:
            status = diagnostics.check_camera()
        self.assertFalse(status.ok)
        self.assertIn("black", status.detail)


class CameraViewTests(unittest.TestCase):
    def test_frame_conversion_and_fit(self) -> None:
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame

        from ui.camera_view import fit_rect, frame_to_surface

        image = np.zeros((2, 4, 3), dtype=np.uint8)
        image[0, 0] = (255, 0, 0)  # Blue in BGR.
        surface = frame_to_surface(image)
        self.assertEqual(surface.get_size(), (4, 2))
        self.assertEqual(tuple(surface.get_at((0, 0)))[:3], (0, 0, 255))
        rect = fit_rect((640, 480), pygame.Rect(0, 0, 720, 540))
        self.assertEqual(rect.size, (720, 540))
        wide = fit_rect((640, 480), pygame.Rect(0, 0, 1000, 300))
        self.assertEqual(wide.size, (400, 300))
        self.assertEqual(wide.center, (500, 150))


if __name__ == "__main__":
    unittest.main()
