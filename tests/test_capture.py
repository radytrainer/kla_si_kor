"""Tiger capture tests."""

from __future__ import annotations

import unittest

from game.board import Board
from game.capture import can_tiger_capture, capture_cow, get_tiger_captures
from game.cell import Cell
from game.tiger import get_tiger_moves, validate_tiger_move

C = Cell


class CaptureTests(unittest.TestCase):
    def test_horizontal_capture(self) -> None:
        board = Board.from_strings(["TC..", "....", "....", "...."])
        self.assertTrue(can_tiger_capture(board, C(0, 0), C(0, 2)).valid)
        validation, move = validate_tiger_move(board, C(0, 0), C(0, 2))
        self.assertTrue(validation.valid)
        self.assertEqual(move.captured, C(0, 1))

    def test_vertical_capture(self) -> None:
        board = Board.from_strings(["T...", "C...", "....", "...."])
        captures = get_tiger_captures(board, C(0, 0))
        self.assertEqual([(m.to_cell, m.captured) for m in captures], [(C(2, 0), C(1, 0))])

    def test_capture_in_every_direction(self) -> None:
        board = Board.from_strings([".....", "..C..", ".CTC.", "..C..", "....."])
        targets = {m.to_cell for m in get_tiger_captures(board, C(2, 2))}
        self.assertEqual(targets, {C(0, 2), C(4, 2), C(2, 0), C(2, 4)})

    def test_tiger_cannot_jump_tiger(self) -> None:
        board = Board.from_strings(["TT..", "....", "....", "...."])
        validation = can_tiger_capture(board, C(0, 0), C(0, 2))
        self.assertFalse(validation.valid)
        self.assertEqual(validation.reason, "Tiger cannot jump over another Tiger")

    def test_tiger_cannot_land_on_occupied_cell(self) -> None:
        for row in ("TCC.", "TCT."):
            with self.subTest(row=row):
                board = Board.from_strings([row, "....", "....", "...."])
                validation = can_tiger_capture(board, C(0, 0), C(0, 2))
                self.assertEqual(validation.code, "occupied")

    def test_no_diagonal_capture(self) -> None:
        board = Board.from_strings(["T...", ".C..", "....", "...."])
        self.assertEqual(can_tiger_capture(board, C(0, 0), C(2, 2)).code, "diagonal")
        self.assertEqual(get_tiger_captures(board, C(0, 0)), [])

    def test_no_capture_off_board(self) -> None:
        board = Board.from_strings([".TC.", "....", "....", "...."])
        # Landing cell (0, 3) is empty and on board -> valid; beyond edge is impossible.
        self.assertTrue(can_tiger_capture(board, C(0, 1), C(0, 3)).valid)
        edge = Board.from_strings(["..TC", "....", "....", "...."])
        self.assertEqual(get_tiger_captures(edge, C(0, 2)), [])

    def test_cannot_jump_empty_or_step_capture(self) -> None:
        board = Board.from_strings(["T...", "....", "....", "...."])
        self.assertEqual(can_tiger_capture(board, C(0, 0), C(0, 2)).code, "jump_empty")
        self.assertEqual(can_tiger_capture(board, C(0, 0), C(0, 1)).code, "not_a_jump")

    def test_tiger_moves_include_captures(self) -> None:
        board = Board.from_strings(["TC..", "....", "....", "...."])
        targets = {m.to_cell for m in get_tiger_moves(board, C(0, 0))}
        self.assertEqual(targets, {C(1, 0), C(0, 2)})

    def test_capture_cow_removes_only_cows(self) -> None:
        board = Board.from_strings(["TC..", "....", "....", "...."])
        capture_cow(board, C(0, 1))
        self.assertTrue(board.is_empty(C(0, 1)))
        with self.assertRaises(ValueError):
            capture_cow(board, C(0, 0))


if __name__ == "__main__":
    unittest.main()
