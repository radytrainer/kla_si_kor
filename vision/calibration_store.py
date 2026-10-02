"""Persistence for the four normalized camera points defining the board."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

import config
from vision.coordinate_mapper import BoardCoordinateMapper, Quad, rectangle_quad


def load_corners(path: Path = config.CALIBRATION_FILE) -> Quad | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        points = tuple(tuple(float(v) for v in point) for point in value["corners"])
        # Reuse mapper validation so malformed or degenerate files fall back cleanly.
        return BoardCoordinateMapper(points).corners
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError,
            np.linalg.LinAlgError):
        return None


def save_corners(corners: Quad, path: Path = config.CALIBRATION_FILE) -> None:
    validated = BoardCoordinateMapper(corners).corners
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"version": 1, "corners": validated}, indent=2) + "\n",
                    encoding="utf-8")


def clear_corners(path: Path = config.CALIBRATION_FILE) -> None:
    """Forget the saved calibration (the default region is used again)."""
    path.unlink(missing_ok=True)


def default_corners() -> Quad:
    return rectangle_quad(*config.BOARD_REGION)
