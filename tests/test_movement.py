"""Movement tests for Tigers and Cows (steps only; captures are in test_capture)."""

from __future__ import annotations

import unittest

from game.board import Board
from game.cell import Cell
from game.cow import get_cow_moves, validate_cow_move
from game.tiger import get_tiger_moves, validate_tiger_move

C = Cell


class TigerMovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.board = Board.from_strings(["....",
                                         ".T..",
                                         "....",
                                         "...."])

    def test_valid_orthogonal_steps(self) -> None:
        for target in (C(0, 1), C(2, 1), C(1, 0), C(1, 2)):
            with self.subTest(target=target):
                validation, move = validate_tiger_move(self.board, C(1, 1), target)
                self.assertTrue(validation.valid, validation.reason)
                self.assertFalse(move.is_capture)

    def test_diagonal_rejected(self) -> None:
        validation, move = validate_tiger_move(self.board, C(1, 1), C(2, 2))
        self.assertFalse(validation.valid)
        self.assertIsNone(move)
        self.assertEqual(validation.reason, "Tiger cannot move diagonally")
        self.assertEqual(validation.to_dict(),
                         {"valid": False, "reason": "Tiger cannot move diagonally"})

    def test_two_cells_without_cow_rejected(self) -> None:
        validation, _ = validate_tiger_move(self.board, C(1, 1), C(3, 1))
        self.assertFalse(validation.valid)
        self.assertEqual(validation.code, "jump_empty")

    def test_three_cells_rejected(self) -> None:
        board = Board.from_strings(["T...", "....", "....", "...."])
        validation, _ = validate_tiger_move(board, C(0, 0), C(0, 3))
        self.assertEqual(validation.code, "too_far")

    def test_same_cell_and_off_board_rejected(self) -> None:
        self.assertEqual(validate_tiger_move(self.board, C(1, 1), C(1, 1))[0].code, "same_cell")
        self.assertEqual(validate_tiger_move(self.board, C(1, 1), C(1, 4))[0].code, "off_board")

    def test_cannot_step_onto_occupied_cell(self) -> None:
        board = Board.from_strings(["....", ".TT.", ".C..", "...."])
        self.assertEqual(validate_tiger_move(board, C(1, 1), C(1, 2))[0].code, "occupied")
        self.assertEqual(validate_tiger_move(board, C(1, 1), C(2, 1))[0].code, "occupied")

    def test_corner_tiger_moves(self) -> None:
        moves = get_tiger_moves(Board.initial(), C(0, 0))
        self.assertEqual({m.to_cell for m in moves}, {C(0, 1), C(1, 0)})


class CowMovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.board = Board.from_strings(["....",
                                         ".C..",
                                         "....",
                                         "...T"])

    def test_valid_orthogonal_steps(self) -> None:
        moves = get_cow_moves(self.board, C(1, 1))
        self.assertEqual({m.to_cell for m in moves}, {C(0, 1), C(2, 1), C(1, 0), C(1, 2)})
        validation, move = validate_cow_move(self.board, C(1, 1), C(1, 2))
        self.assertTrue(validation.valid)
        self.assertIsNotNone(move)

    def test_diagonal_rejected(self) -> None:
        validation, _ = validate_cow_move(self.board, C(1, 1), C(0, 0))
        self.assertEqual(validation.reason, "Cow cannot move diagonally")

    def test_cow_cannot_jump(self) -> None:
        validation, _ = validate_cow_move(self.board, C(1, 1), C(3, 1))
        self.assertEqual(validation.reason, "Cow cannot jump")

    def test_cow_cannot_jump_over_tiger(self) -> None:
        board = Board.from_strings(["....", "CT..", "....", "...."])
        self.assertEqual(validate_cow_move(board, C(1, 0), C(1, 2))[0].code, "cow_jump")

    def test_cow_cannot_capture_tiger(self) -> None:
        board = Board.from_strings(["....", "CT..", "....", "...."])
        validation, _ = validate_cow_move(board, C(1, 0), C(1, 1))
        self.assertEqual(validation.reason, "Cow cannot capture a Tiger")

    def test_cow_cannot_move_onto_cow(self) -> None:
        board = Board.from_strings(["....", "CC..", "....", "...."])
        self.assertEqual(validate_cow_move(board, C(1, 0), C(1, 1))[0].code, "occupied")

    def test_blocked_cow_has_no_moves(self) -> None:
        board = Board.from_strings(["CT..", "T...", "....", "...."])
        self.assertEqual(get_cow_moves(board, C(0, 0)), [])


if __name__ == "__main__":
    unittest.main()
