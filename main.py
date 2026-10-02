"""Entry point for ខ្លាស៊ីគោ — Tigers vs Cows.

Usage:
    python main.py                 Launch the game window.
    python main.py --check         Print an environment check and exit.
    python main.py --download-model  Download the hand-tracking model (once).
    python main.py --fullscreen    Launch in fullscreen mode.
    python main.py --screen game   (developer) Open a screen directly.
"""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path

import config
from app.diagnostics import (check_camera, check_dependencies, check_python_version,
                             download_hand_model, format_report)

# Names accepted by --screen (must match ui.screen.ScreenId members).
SCREEN_CHOICES = ("menu", "game", "how_to_play", "camera_check", "calibration", "settings",
                  "system_check")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line options."""
    parser = argparse.ArgumentParser(description="Tigers vs Cows - Computer Vision Edition")
    parser.add_argument("--check", action="store_true",
                        help="print an environment/dependency report and exit")
    parser.add_argument("--download-model", action="store_true",
                        help="download the MediaPipe hand model (needed once)")
    parser.add_argument("--fullscreen", action="store_true", default=None,
                        help="start in fullscreen mode (this session only)")
    debug = parser.add_mutually_exclusive_group()
    debug.add_argument("--debug", dest="debug", action="store_true", default=None,
                       help="show debug information (this session only)")
    debug.add_argument("--no-debug", dest="debug", action="store_false",
                       help="hide debug information (this session only)")
    parser.add_argument("--input", choices=("gesture", "mouse"), default=None,
                        help="play with hand gestures (camera) or the mouse (this session)")
    parser.add_argument("--mute", action="store_true",
                        help="turn sound effects off (this session only)")
    parser.add_argument("--screen", choices=SCREEN_CHOICES, default=None,
                        help="(developer) open this screen directly")
    parser.add_argument("--max-frames", type=int, default=None,
                        help="(developer) exit automatically after N frames")
    parser.add_argument("--screenshot", type=Path, default=None,
                        help="(developer) save the final frame to this PNG file")
    return parser.parse_args(argv)


def run_check() -> int:
    """Print the dependency report; exit code 0 only if everything is fine."""
    results = check_dependencies()
    if all(result.ok for result in results):
        print("Testing camera (a few seconds)...")
        results.append(check_camera())
    print("Environment check:")
    print(format_report(results))
    problems = config.validate_config()
    for problem in problems:
        print(f"  [ CONFIG]  {problem}")
    healthy = all(result.ok for result in results) and not problems
    print("All good." if healthy else "Problems found - see above.")
    return 0 if healthy else 1


def run_download_model() -> int:
    """Download the hand-tracking model; exit code 0 on success."""
    print(f"Downloading hand model from {config.HAND_MODEL_URL} ...")
    try:
        path = download_hand_model()
    except OSError as exc:
        print(f"Download failed: {exc}")
        print(f"Download it manually and save it as {config.HAND_MODEL_FILE}")
        return 1
    print(f"Saved to {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Program entry point; returns the process exit code."""
    args = parse_args(argv)
    if args.download_model:
        return run_download_model()
    if args.check:
        return run_check()

    python_status = check_python_version()
    if not python_status.ok:
        print(f"Unsupported Python version: {python_status.detail}")
        return 1
    problems = config.validate_config()
    if problems:
        print("Invalid configuration in config.py:")
        print("\n".join(f"  - {problem}" for problem in problems))
        return 1

    try:
        from app.application import Application, LaunchOptions
        from ui.screen import ScreenId
    except ImportError as exc:
        print(f"Could not start: {exc}")
        print("Install the dependencies first:  pip install -r requirements.txt")
        return 1

    options = LaunchOptions(
        fullscreen=args.fullscreen,
        debug=args.debug,
        start_screen=ScreenId[args.screen.upper()] if args.screen else None,
        max_frames=args.max_frames,
        screenshot_path=args.screenshot,
        input_mode=args.input.upper() if args.input else None,
        sound=False if args.mute else None,
    )
    try:
        return Application(options).run()
    except Exception:
        write_crash_log()
        raise


def write_crash_log() -> None:
    """Save the current exception's traceback so players can report problems.

    The packaged game has no console, so without this the details would be lost.
    """
    try:
        config.CRASH_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with config.CRASH_LOG_FILE.open("a", encoding="utf-8") as log:
            stamp = f"{datetime.now():%Y-%m-%d %H:%M:%S}"
            log.write(f"\n=== {stamp} · version {config.APP_VERSION}\n")
            log.write(traceback.format_exc())
        print(f"Crash details saved to {config.CRASH_LOG_FILE}")
    except OSError:
        pass  # Never hide the original error behind a logging error.


if __name__ == "__main__":
    sys.exit(main())
