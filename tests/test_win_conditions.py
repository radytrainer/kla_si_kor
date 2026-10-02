"""Win-condition tests (pure functions and through the engine)."""

from __future__ import annotations

import unittest

import config
from game.board import Board
from game.state import Phase, Side
from game.win_condition import (check_cow_win, check_tiger_win, cows_have_legal_move,
                                tigers_have_legal_move)
from tests.helpers import COW_PLAYER, TIGER_PLAYER, engine_from, select

# Tigers in the corners, walled in by Cows two deep: no step, no capture.
TRAPPED = ["TCCT",
           "CCCC",
           "CCCC",
           "TCCT"]


class PureWinConditionTests(unittest.TestCase):
    def test_tiger_win_needs_all_cows(self) -> None:
        self.assertFalse(check_tiger_win(config.COW_COUNT - 1))
        self.assertTrue(check_tiger_win(config.COW_COUNT))

    def test_trapped_tigers(self) -> None:
        board = Board.from_strings(TRAPPED)
        self.assertFalse(tigers_have_legal_move(board))
        self.assertTrue(check_cow_win(board))

    def test_tigers_with_capture_are_not_trapped(self) -> None:
        board = Board.from_strings(["TC.T", "CCCC", "CCCC", "TCCT"])
        self.assertTrue(tigers_have_legal_move(board))
        self.assertFalse(check_cow_win(board))

    def test_initial_position_not_a_win(self) -> None:
        self.assertFalse(check_cow_win(Board.initial()))

    def test_cows_blocked(self) -> None:
        self.assertFalse(cows_have_legal_move(Board.from_strings(TRAPPED)))


class EngineWinTests(unittest.TestCase):
    def test_tigers_win_by_capturing_last_cow(self) -> None:
        engine = engine_from(["TC..", "....", "....", "...T"],
                             cows_captured=config.COW_COUNT - 1)
        select(engine, TIGER_PLAYER, 0, 0)
        result = select(engine, TIGER_PLAYER, 0, 2)
        self.assertTrue(result.valid)
        self.assertTrue(engine.state.game_over)
        self.assertIs(engine.state.phase, Phase.GAME_OVER)
        self.assertIs(engine.state.winner, Side.TIGER)
        self.assertEqual(engine.state.cows_captured, config.COW_COUNT)

    def test_cows_win_when_move_traps_tigers(self) -> None:
        engine = engine_from(["TCCT",
                              ".CCC",
                              "CCCC",
                              "TCCT"], side=Side.COW)
        # Before the move a Tiger can still reach A2 (step or jump).
        self.assertTrue(tigers_have_legal_move(engine.state.board))
        # Cow B2 -> A2 leaves only B2 empty, which no Tiger can reach.
        select(engine, COW_PLAYER, 1, 1)
        result = select(engine, COW_PLAYER, 1, 0)
        self.assertTrue(result.valid, result.reason)
        self.assertIs(engine.state.winner, Side.COW)
        self.assertEqual(engine.state.win_reason, "The Tigers have no legal moves")

    def test_cow_win_when_last_placement_fills_board(self) -> None:
        engine = engine_from(["TCCT",
                              "CCCC",
                              "CCC.",
                              "TCCT"], side=Side.COW, phase=Phase.COW_PLACEMENT)
        self.assertEqual(engine.state.cows_to_place, 1)
        result = select(engine, COW_PLAYER, 2, 3)
        self.assertTrue(result.valid, result.reason)
        self.assertIs(engine.state.phase, Phase.GAME_OVER)
        self.assertIs(engine.state.winner, Side.COW)

    def test_no_winner_while_tigers_can_move(self) -> None:
        engine = engine_from(["TC..", "....", "....", "...T"])
        select(engine, TIGER_PLAYER, 3, 3)
        select(engine, TIGER_PLAYER, 2, 3)
        self.assertFalse(engine.state.game_over)
        self.assertIsNone(engine.state.winner)


if __name__ == "__main__":
    unittest.main()
