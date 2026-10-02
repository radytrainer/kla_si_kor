"""Background vision pipeline: camera frames -> hand detection -> latest result.

Hand detection takes ~20 ms per frame, which would halve the UI frame rate if
it ran in the UI loop. The pipeline runs it on its own thread and publishes
the latest :class:`VisionResult`; the UI only reads that result.
"""

from __future__ import annotations

import queue
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np

import config
from camera.camera import Camera, Frame
from vision.gesture_detector import (GestureEvent, GestureRecognizer, GestureState,
                                     GestureTuning)
from vision.hand_detector import Hand, HandDetector, HandDetectorError
from vision.player_tracker import PlayerSnapshot, PlayerTracker

MS_PER_SECOND = 1000
MAX_CONSECUTIVE_ERRORS = 30  # then report the detector as broken


class Detector(Protocol):
    def detect(self, image_bgr: np.ndarray, timestamp_ms: int) -> tuple[Hand, ...]: ...
    def close(self) -> None: ...


DetectorFactory = Callable[[], Detector]


class PipelineStatus(Enum):
    STOPPED = "STOPPED"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    ERROR = "ERROR"  # The detector could not start (e.g. missing model).


@dataclass(frozen=True)
class VisionResult:
    """Hands detected in one camera frame, their players, and timing information."""

    frame: Frame
    hands: tuple[Hand, ...]
    detection_ms: float
    players: tuple[PlayerSnapshot, ...] = ()
    gestures: tuple[GestureState, ...] = ()

    def player(self, player_id: int) -> PlayerSnapshot | None:
        return next((p for p in self.players if p.player_id == player_id), None)

    def gesture(self, player_id: int) -> GestureState | None:
        return next((g for g in self.gestures if g.player_id == player_id), None)


class VisionPipeline:
    """Owns the camera lifecycle and runs hand detection on a worker thread."""

    def __init__(self, camera: Camera, detector_factory: DetectorFactory = HandDetector,
                 clock: Callable[[], float] = time.monotonic,
                 tracker: PlayerTracker | None = None) -> None:
        self.camera = camera
        self._factory = detector_factory
        self.tracker = tracker if tracker is not None else PlayerTracker()
        self.gestures = GestureRecognizer()
        # Gesture events are queued so each one reaches the UI exactly once.
        self._events: queue.SimpleQueue[GestureEvent] = queue.SimpleQueue()
        self._clock = clock
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._result: VisionResult | None = None
        self._status = PipelineStatus.STOPPED
        self._message = ""
        self._result_times: deque[float] = deque()

    # -- public API (UI thread) ------------------------------------------------
    @property
    def status(self) -> PipelineStatus:
        with self._lock:
            return self._status

    @property
    def message(self) -> str:
        with self._lock:
            return self._message

    @property
    def fps(self) -> float:
        """Detection results per second."""
        with self._lock:
            times = list(self._result_times)
        if len(times) < 2:
            return 0.0
        return (len(times) - 1) / max(times[-1] - times[0], 1e-6)

    def latest_result(self) -> VisionResult | None:
        with self._lock:
            return self._result

    def set_gesture_tuning(self, tuning: GestureTuning) -> None:
        """Apply new pinch thresholds / smoothing (safe while running)."""
        self.gestures.set_tuning(tuning)

    def drain_events(self) -> list[GestureEvent]:
        """Return (and remove) every gesture event produced since the last call."""
        events: list[GestureEvent] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except queue.Empty:
                return events

    def start(self) -> None:
        """Start the camera and the detection thread (no-op if running)."""
        self.camera.start()
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.tracker.reset()
        self.gestures.reset()
        self.drain_events()
        self._set_status(PipelineStatus.STARTING, "")
        self._thread = threading.Thread(target=self._run, name="vision", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop detection and release the camera."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=config.CAMERA_STOP_TIMEOUT)
            self._thread = None
        self.camera.stop()
        self.drain_events()  # Never deliver stale gestures to the next screen.
        with self._lock:
            self._result = None
            self._result_times.clear()
            if self._status is not PipelineStatus.ERROR:
                self._status = PipelineStatus.STOPPED

    # -- worker thread ---------------------------------------------------------------
    def _set_status(self, status: PipelineStatus, message: str) -> None:
        with self._lock:
            self._status = status
            self._message = message

    def _run(self) -> None:
        try:
            detector = self._factory()
        except HandDetectorError as exc:
            self._set_status(PipelineStatus.ERROR, str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            self._set_status(PipelineStatus.ERROR, f"Hand detector failed to start: {exc}")
            return
        try:
            self._set_status(PipelineStatus.RUNNING, "")
            self._detect_loop(detector)
        finally:
            detector.close()

    def _detect_loop(self, detector: Detector) -> None:
        last_index = -1
        errors = 0
        while not self._stop_event.is_set():
            frame = self.camera.latest_frame()
            if frame is None or frame.index == last_index:
                self._stop_event.wait(config.VISION_IDLE_WAIT)
                continue
            last_index = frame.index
            started = self._clock()
            try:
                hands = detector.detect(frame.image, int(frame.timestamp * MS_PER_SECOND))
            except Exception as exc:  # noqa: BLE001 - one bad frame must not stop tracking
                errors += 1
                if errors >= MAX_CONSECUTIVE_ERRORS:
                    self._set_status(PipelineStatus.ERROR, f"Hand detection keeps failing: {exc}")
                    return
                continue
            errors = 0
            finished = self._clock()
            players = self.tracker.update(hands, frame.timestamp)
            gestures, events = self.gestures.update(players, frame.timestamp)
            for event in events:
                self._events.put(event)
            result = VisionResult(frame, hands, (finished - started) * MS_PER_SECOND, players,
                                  gestures)
            with self._lock:
                self._result = result
                self._result_times.append(finished)
                while finished - self._result_times[0] > config.CAMERA_FPS_WINDOW:
                    self._result_times.popleft()
