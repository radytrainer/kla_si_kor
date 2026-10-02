"""BoardCoordinateMapper / Homography tests."""

from __future__ import annotations

import unittest

import config
from vision.coordinate_mapper import (UNIT_SQUARE, BoardCoordinateMapper, Homography,
                                      rectangle_quad)

# A perspective-distorted board, as a camera looking down at an angle would see it.
TRAPEZOID = ((0.3, 0.2), (0.7, 0.2), (0.85, 0.8), (0.15, 0.8))


class HomographyTests(unittest.TestCase):
    def test_identity(self) -> None:
        h = Homography.from_points(UNIT_SQUARE, UNIT_SQUARE)
        u, v = h.apply((0.3, 0.7))
        self.assertAlmostEqual(u, 0.3)
        self.assertAlmostEqual(v, 0.7)

    def test_corners_map_exactly_and_inverse_round_trips(self) -> None:
        h = Homography.from_points(TRAPEZOID, UNIT_SQUARE)
        for source, target in zip(TRAPEZOID, UNIT_SQUARE):
            u, v = h.apply(source)
            self.assertAlmostEqual(u, target[0])
            self.assertAlmostEqual(v, target[1])
        x, y = h.inverse().apply(h.apply((0.42, 0.61)))
        self.assertAlmostEqual(x, 0.42)
        self.assertAlmostEqual(y, 0.61)

    def test_collinear_points_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Homography.from_points(((0, 0), (0.5, 0), (1, 0), (0.2, 0)), UNIT_SQUARE)


class MapperTests(unittest.TestCase):
    def test_default_region_from_config(self) -> None:
        mapper = BoardCoordinateMapper()
        left, top, right, bottom = config.BOARD_REGION
        self.assertEqual(mapper.corners, rectangle_quad(left, top, right, bottom))
        self.assertEqual(mapper.cell_at((left + 0.001, top + 0.001)), (0, 0))
        self.assertEqual(mapper.cell_at((right - 0.001, bottom - 0.001)), (3, 3))

    def test_every_cell_centre_maps_back(self) -> None:
        for corners in (None, TRAPEZOID):
            mapper = BoardCoordinateMapper(corners)
            for row in range(config.BOARD_ROWS):
                for col in range(config.BOARD_COLS):
                    with self.subTest(corners=corners, cell=(row, col)):
                        self.assertEqual(mapper.cell_at(mapper.cell_center(row, col)),
                                         (row, col))

    def test_outside_board_is_none(self) -> None:
        mapper = BoardCoordinateMapper(rectangle_quad(0.2, 0.1, 0.8, 0.9))
        for point in ((0.1, 0.5), (0.9, 0.5), (0.5, 0.05), (0.5, 0.95), (0.8, 0.9)):
            with self.subTest(point=point):
                self.assertIsNone(mapper.cell_at(point))

    def test_perspective_cells_follow_the_quad(self) -> None:
        mapper = BoardCoordinateMapper(TRAPEZOID)
        # Near the top edge the board is narrower: x=0.25 is outside at the top...
        self.assertIsNone(mapper.cell_at((0.25, 0.22)))
        # ...but inside (left column) near the wider bottom edge.
        self.assertEqual(mapper.cell_at((0.25, 0.78))[1], 0)

    def test_board_coordinates(self) -> None:
        mapper = BoardCoordinateMapper(rectangle_quad(0.2, 0.1, 0.8, 0.9))
        u, v = mapper.camera_to_board((0.5, 0.5))
        self.assertAlmostEqual(u, 0.5)
        self.assertAlmostEqual(v, 0.5)

    def test_wrong_corner_order_rejected(self) -> None:
        tl, tr, br, bl = rectangle_quad(0.2, 0.1, 0.8, 0.9)
        with self.assertRaises(ValueError):
            BoardCoordinateMapper((tl, bl, br, tr))  # Counter-clockwise.


if __name__ == "__main__":
    unittest.main()
