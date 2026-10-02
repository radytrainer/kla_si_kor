"""Threaded webcam capture.

Frames are read on a background thread so a slow camera never stalls the UI.
The UI only ever asks for the *latest* frame. The camera recovers by itself:
if it cannot be opened, or is unplugged, it is retried every
CAMERA_RETRY_INTERVAL seconds and the status explains what is wrong.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import cv2
import numpy as np

import config

MIRROR_HORIZONTAL = 1  # cv2.flip code for a left/right mirror.

UNAVAILABLE_MESSAGE = (
    "Camera not available. Check that it is connected, not used by another app, "
    "and allowed in Windows Settings > Privacy & security > Camera."
)
DISCONNECTED_MESSAGE = "Camera stopped sending images. Reconnecting..."


class CameraStatus(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    UNAVAILABLE = "UNAVAILABLE"  # Could not be opened (missing, busy, no permission).
    DISCONNECTED = "DISCONNECTED"  # Was running, then frames stopped arriving.


class CaptureDevice(Protocol):
    """The subset of cv2.VideoCapture used here (lets tests inject a fake)."""

    def isOpened(self) -> bool: ...  # noqa: N802 - OpenCV naming
    def read(self) -> tuple[bool, np.ndarray | None]: ...
    def release(self) -> None: ...


CaptureFactory = Callable[[], CaptureDevice | None]


@dataclass(frozen=True)
class Frame:
    """One camera image (BGR, already mirrored if configured)."""

    image: np.ndarray
    timestamp: float
    index: int

    @property
    def size(self) -> tuple[int, int]:
        height, width = self.image.shape[:2]
        return width, height

    @property
    def too_dark(self) -> bool:
        """Almost black: camera covered, privacy shutter closed, or no light."""
        return float(self.image.mean()) < config.CAMERA_DARK_THRESHOLD


def open_opencv_capture(index: int = config.CAMERA_INDEX) -> CaptureDevice | None:
    """Open a webcam with OpenCV, trying the fastest Windows backend first."""
    backends = [cv2.CAP_DSHOW] if config.CAMERA_USE_DIRECTSHOW else []
    backends += [cv2.CAP_MSMF, cv2.CAP_ANY]
    for backend in backends:
        capture = cv2.VideoCapture(index, backend)
        if capture.isOpened():
            capture.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
            capture.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
            capture.set(cv2.CAP_PROP_FPS, config.CAMERA_REQUESTED_FPS)
            return capture
        capture.release()
    return None


class Camera:
    """Background-thread camera with automatic retry and FPS measurement."""

    def __init__(self, capture_factory: CaptureFactory | None = None,
                 mirror: bool = config.CAMERA_MIRROR,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._custom_factory = capture_factory is not None
        self.index = config.CAMERA_INDEX
        self._factory: CaptureFactory = capture_factory or open_opencv_capture
        self._mirror = mirror
        self._clock = clock
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._latest: Frame | None = None
        self._status = CameraStatus.STOPPED
        self._message = ""
        self._frame_times: deque[float] = deque()

    # -- public API (called from the UI thread) --------------------------------
    @property
    def status(self) -> CameraStatus:
        with self._lock:
            return self._status

    @property
    def message(self) -> str:
        with self._lock:
            return self._message

    @property
    def running(self) -> bool:
        return self.status is CameraStatus.RUNNING

    @property
    def fps(self) -> float:
        """Frames per second actually delivered by the camera."""
        with self._lock:
            times = list(self._frame_times)
        if len(times) < 2:
            return 0.0
        return (len(times) - 1) / max(times[-1] - times[0], 1e-6)

    def latest_frame(self) -> Frame | None:
        """The most recent frame, or None if no frame has arrived yet."""
        with self._lock:
            return self._latest

    def set_index(self, index: int) -> None:
        """Switch to another webcam (restarts capture if it was running)."""
        if index == self.index:
            return
        self.index = index
        if not self._custom_factory:
            self._factory = lambda: open_opencv_capture(index)
        if self._thread is not None:
            self.stop()
            self.start()

    def start(self) -> None:
        """Start capturing in the background (no-op if already started)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._set_status(CameraStatus.STARTING, "Starting camera...")
        self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop capturing and release the device."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=config.CAMERA_STOP_TIMEOUT)
            self._thread = None
        with self._lock:
            self._latest = None
            self._frame_times.clear()
        self._set_status(CameraStatus.STOPPED, "")

    # -- capture thread --------------------------------------------------------------
    def _set_status(self, status: CameraStatus, message: str) -> None:
        with self._lock:
            self._status = status
            self._message = message

    def _run(self) -> None:
        while not self._stop_event.is_set():
            device = self._open()
            if device is None:
                self._set_status(CameraStatus.UNAVAILABLE, UNAVAILABLE_MESSAGE)
                self._stop_event.wait(config.CAMERA_RETRY_INTERVAL)
                continue
            try:
                self._capture_loop(device)
            finally:
                device.release()
            if not self._stop_event.is_set():
                self._set_status(CameraStatus.DISCONNECTED, DISCONNECTED_MESSAGE)
                self._stop_event.wait(config.CAMERA_RETRY_INTERVAL)

    def _open(self) -> CaptureDevice | None:
        try:
            device = self._factory()
        except Exception:  # noqa: BLE001 - driver errors must not kill the thread
            return None
        if device is not None and not device.isOpened():
            device.release()
            return None
        return device

    def _capture_loop(self, device: CaptureDevice) -> None:
        """Read frames until stopped or until reads keep failing."""
        failures = 0
        index = 0
        while not self._stop_event.is_set():
            try:
                ok, image = device.read()
            except Exception:  # noqa: BLE001
                ok, image = False, None
            if not ok or image is None:
                failures += 1
                if failures >= config.CAMERA_MAX_READ_FAILURES:
                    return
                continue
            failures = 0
            if self._mirror:
                image = cv2.flip(image, MIRROR_HORIZONTAL)
            now = self._clock()
            index += 1
            with self._lock:
                self._latest = Frame(image, now, index)
                self._frame_times.append(now)
                while now - self._frame_times[0] > config.CAMERA_FPS_WINDOW:
                    self._frame_times.popleft()
                if self._status is not CameraStatus.RUNNING:
                    self._status = CameraStatus.RUNNING
                    self._message = ""
