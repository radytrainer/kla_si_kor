"""Maps fingertip positions in the camera image onto the board.

camera (x, y)  ->  board (u, v)  ->  cell (row, col)

(u, v) is (0, 0) at the board's top-left and (1, 1) at its bottom-right. The
board region in the camera is any quadrilateral (top-left, top-right,
bottom-right, bottom-left), handled with a perspective transform
(homography), so calibration (Phase 12) can supply four measured corners.
Returns plain (row, col) tuples to keep this module independent of the game.
"""

from __future__ import annotations

import math

import numpy as np

import config

Point = tuple[float, float]
Quad = tuple[Point, Point, Point, Point]  # TL, TR, BR, BL
UNIT_SQUARE: Quad = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))
MIN_AREA = 1e-4  # Smaller quads (normalised units) are rejected as degenerate.


class Homography:
    """3×3 perspective transform between two planes."""

    def __init__(self, matrix: np.ndarray) -> None:
        self.matrix = matrix

    @classmethod
    def from_points(cls, source: Quad, target: Quad) -> Homography:
        """Solve the transform mapping four source points onto four target points."""
        rows, rhs = [], []
        for (x, y), (u, v) in zip(source, target):
            rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
            rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
            rhs.extend([u, v])
        try:
            h = np.linalg.solve(np.array(rows, dtype=float), np.array(rhs, dtype=float))
        except np.linalg.LinAlgError as exc:
            raise ValueError("Board corners do not form a valid quadrilateral") from exc
        return cls(np.append(h, 1.0).reshape(3, 3))

    def apply(self, point: Point) -> Point:
        x, y, w = self.matrix @ np.array([point[0], point[1], 1.0])
        return float(x / w), float(y / w)

    def inverse(self) -> Homography:
        return Homography(np.linalg.inv(self.matrix))


def quad_area(quad: Quad) -> float:
    """Signed area (shoelace formula); positive for clockwise-on-screen order."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(quad, quad[1:] + quad[:1]):
        total += x1 * y2 - x2 * y1
    return total / 2


def rectangle_quad(left: float, top: float, right: float, bottom: float) -> Quad:
    return ((left, top), (right, top), (right, bottom), (left, bottom))


class BoardCoordinateMapper:
    """Converts camera coordinates to board coordinates and cells."""

    def __init__(self, corners: Quad | None = None, rows: int = config.BOARD_ROWS,
                 cols: int = config.BOARD_COLS) -> None:
        self.rows = rows
        self.cols = cols
        self.set_corners(corners if corners is not None else rectangle_quad(*config.BOARD_REGION))

    def set_corners(self, corners: Quad) -> None:
        """Replace the calibrated quadrilateral after validating its geometry."""
        corners = tuple(tuple(map(float, p)) for p in corners)
        if (len(corners) != 4 or any(len(p) != 2 for p in corners)
                or any(not 0.0 <= value <= 1.0 for point in corners for value in point)
                or quad_area(corners) < MIN_AREA):
            raise ValueError("Board corners must be TL, TR, BR, BL and enclose an area")
        turns = []
        for index in range(4):
            ax, ay = corners[(index + 1) % 4][0] - corners[index][0], \
                corners[(index + 1) % 4][1] - corners[index][1]
            bx, by = corners[(index + 2) % 4][0] - corners[(index + 1) % 4][0], \
                corners[(index + 2) % 4][1] - corners[(index + 1) % 4][1]
            turns.append(ax * by - ay * bx)
        if min(turns) <= MIN_AREA:
            raise ValueError("Board corners must form a convex TL, TR, BR, BL quadrilateral")
        transform = Homography.from_points(corners, UNIT_SQUARE)
        self.corners = corners
        self._to_board = transform
        self._to_camera = transform.inverse()

    def camera_to_board(self, point: Point) -> Point:
        """(u, v) board coordinates; inside the board when both are within 0..1."""
        return self._to_board.apply(point)

    def board_to_camera(self, point: Point) -> Point:
        return self._to_camera.apply(point)

    def cell_at(self, point: Point) -> tuple[int, int] | None:
        """(row, col) under a camera point, or None if outside the board."""
        u, v = self.camera_to_board(point)
        if not (0.0 <= u < 1.0 and 0.0 <= v < 1.0) or math.isnan(u) or math.isnan(v):
            return None
        return int(v * self.rows), int(u * self.cols)

    def cell_center(self, row: int, col: int) -> Point:
        """Camera coordinates of a cell's centre (useful for tests and hints)."""
        return self.board_to_camera(((col + 0.5) / self.cols, (row + 0.5) / self.rows))
