"""Start-up environment diagnostics.

Checks the Python version and that each required package can be imported,
without crashing when something is missing. The results are shown both on the
command line (``python main.py --check``) and on the launch screen.
"""

from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path

import config


@dataclass(frozen=True)
class DependencyStatus:
    """Result of checking a single dependency."""

    label: str
    ok: bool
    detail: str  # Version string when ok, otherwise a short error message.


# (display label, import name, distribution name for the version lookup,
#  attribute the game relies on). The attribute check catches broken installs
#  that still import, e.g. an empty "cv2" folder left behind by pip.
REQUIRED_PACKAGES: tuple[tuple[str, str, str, str], ...] = (
    ("NumPy", "numpy", "numpy", "ndarray"),
    ("OpenCV", "cv2", "opencv-contrib-python", "VideoCapture"),
    ("MediaPipe", "mediapipe", "mediapipe", "tasks"),
    ("pygame-ce", "pygame", "pygame-ce", "display"),
)


DETAIL_MAX_LENGTH = 80


def check_python_version() -> DependencyStatus:
    """Check that the running interpreter satisfies MIN_PYTHON_VERSION."""
    current = sys.version_info[:2]
    required = config.MIN_PYTHON_VERSION
    version = ".".join(str(part) for part in sys.version_info[:3])
    if current >= required:
        return DependencyStatus("Python", True, version)
    needed = ".".join(str(part) for part in required)
    return DependencyStatus("Python", False, f"{version} (need {needed}+)")


def check_package(label: str, import_name: str, dist_name: str,
                  required_attribute: str | None = None) -> DependencyStatus:
    """Import a package, verify it is functional and report its version."""
    try:
        module = importlib.import_module(import_name)
    except Exception as exc:  # noqa: BLE001 - any import failure is reportable
        # Include the message: it names the missing module (vital for packaged builds).
        return DependencyStatus(label, False, f"not importable: {exc}"[:DETAIL_MAX_LENGTH])
    if required_attribute and not hasattr(module, required_attribute):
        return DependencyStatus(label, False, "broken install - reinstall it")
    version = getattr(module, "__version__", None)
    if version is None:
        try:
            version = metadata.version(dist_name)
        except metadata.PackageNotFoundError:
            version = "unknown version"
    return DependencyStatus(label, True, str(version))


def check_dependencies() -> list[DependencyStatus]:
    """Check the interpreter and every required package."""
    results = [check_python_version()]
    results.extend(check_package(*package) for package in REQUIRED_PACKAGES)
    results.append(check_hand_model())
    return results


CAMERA_PROBE_TIMEOUT = 10.0  # seconds to wait for the first frames
CAMERA_PROBE_SAMPLE = 1.0  # seconds of frames used to measure FPS
CAMERA_PROBE_POLL = 0.05


def check_hand_model() -> DependencyStatus:
    """Check that the MediaPipe hand model file is present."""
    path = config.HAND_MODEL_FILE
    if path.is_file():
        return DependencyStatus("Hand model", True, f"{path.stat().st_size / 1e6:.1f} MB")
    return DependencyStatus("Hand model", False, "missing - run: python main.py --download-model")


def download_hand_model() -> Path:
    """Download the MediaPipe hand model to config.HAND_MODEL_FILE."""
    import urllib.request

    path = config.HAND_MODEL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    urllib.request.urlretrieve(config.HAND_MODEL_URL, temporary)
    temporary.replace(path)
    return path


def check_camera() -> DependencyStatus:
    """Open the webcam briefly and report resolution and frame rate."""
    import time

    from camera.camera import Camera, CameraStatus

    camera = Camera()
    camera.start()
    try:
        deadline = time.monotonic() + CAMERA_PROBE_TIMEOUT
        while not camera.running and time.monotonic() < deadline:
            if camera.status is CameraStatus.UNAVAILABLE:
                break
            time.sleep(CAMERA_PROBE_POLL)
        if not camera.running:
            return DependencyStatus("Camera", False, camera.message or "no frames received")
        time.sleep(CAMERA_PROBE_SAMPLE)
        frame = camera.latest_frame()
        width, height = frame.size
        detail = f"{width}x{height} @ {camera.fps:.0f} fps"
        if frame.too_dark:
            return DependencyStatus("Camera", False, f"{detail}, picture is black: camera "
                                                     "covered/shutter closed, or no light")
        return DependencyStatus("Camera", True, detail)
    finally:
        camera.stop()


def format_report(results: list[DependencyStatus]) -> str:
    """Format diagnostics as a plain-text report for the console."""
    width = max(len(result.label) for result in results)
    lines = [
        f"  [{'OK' if result.ok else 'MISSING':>7}]  {result.label:<{width}}  {result.detail}"
        for result in results
    ]
    return "\n".join(lines)
