"""Board tests: initial position, parsing, queries."""

from __future__ import annotations

import unittest

from game.board import Board
from game.cell import Cell
from game.piece import Piece


class InitialBoardTests(unittest.TestCase):
    def test_initial_board_layout(self) -> None:
        self.assertEqual(Board.initial().to_strings(), ["T..T", "....", "....", "T..T"])

    def test_four_tigers_in_corners_and_no_cows(self) -> None:
        board = Board.initial()
        self.assertEqual(board.count(Piece.TIGER), 4)
        self.assertEqual(set(board.cells_with(Piece.TIGER)),
                         {Cell(0, 0), Cell(0, 3), Cell(3, 0), Cell(3, 3)})
        self.assertEqual(board.count(Piece.COW), 0)
        self.assertEqual(board.count(Piece.EMPTY), 12)


class BoardHelperTests(unittest.TestCase):
    def test_round_trip_strings(self) -> None:
        lines = ["TC.T", ".C..", "..C.", "T..T"]
        self.assertEqual(Board.from_strings(lines).to_strings(), lines)

    def test_rejects_bad_input(self) -> None:
        with self.assertRaises(ValueError):
            Board.from_strings(["T..X", "....", "....", "T..T"])
        with self.assertRaises(ValueError):
            Board.from_strings(["T..", "....", "....", "T..T"])

    def test_on_board_and_empty(self) -> None:
        board = Board.initial()
        self.assertTrue(board.is_on_board(Cell(3, 3)))
        self.assertFalse(board.is_on_board(Cell(4, 0)))
        self.assertFalse(board.is_on_board(Cell(0, -1)))
        self.assertFalse(board.is_empty(Cell(0, 0)))
        self.assertTrue(board.is_empty(Cell(1, 1)))
        self.assertFalse(board.is_empty(Cell(-1, 0)))  # Off-board is never "empty".

    def test_get_off_board_raises(self) -> None:
        with self.assertRaises(IndexError):
            Board.initial().get(Cell(4, 4))

    def test_copy_is_independent(self) -> None:
        board = Board.initial()
        clone = board.copy()
        clone.set(Cell(1, 1), Piece.COW)
        self.assertTrue(board.is_empty(Cell(1, 1)))
        self.assertNotEqual(board, clone)


if __name__ == "__main__":
    unittest.main()
