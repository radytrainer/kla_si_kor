"""The computer opponent: its rules match the engine, it plays sensibly and fast."""

from __future__ import annotations

import random
import time
import unittest

import config
from game.ai import (LEVELS, ComputerPlayer, apply_move, legal_moves, position_from_state,
                     to_move_object)
from game.cell import Cell
from game.game_engine import GameEngine
from game.state import Phase, Side
from tests.helpers import COW_PLAYER, TIGER_PLAYER, engine_from

MAX_TURNS = 300
MAX_THINK_SECONDS = 0.5  # The UI thread waits for the computer's choice.


def play(engine: GameEngine, move) -> None:
    if move.from_cell == move.to_cell:
        engine.place_cow(move.to_cell)
    else:
        engine.move_piece(move.from_cell, move.to_cell)


def play_game(tiger: ComputerPlayer, cow: ComputerPlayer) -> GameEngine:
    engine = GameEngine()
    players = {TIGER_PLAYER: tiger, COW_PLAYER: cow}
    for _ in range(MAX_TURNS):
        if engine.state.game_over:
            break
        play(engine, players[engine.current_player].choose_move(engine.state))
    return engine


class RulesAgreeWithEngineTests(unittest.TestCase):
    def test_random_games(self) -> None:
        """Every position of many random games: same moves, same result of each move."""
        for seed in range(30):
            rng = random.Random(seed)
            engine = GameEngine()
            for _ in range(MAX_TURNS):
                if engine.state.game_over:
                    break
                position = position_from_state(engine.state)
                moves = legal_moves(position)
                self.assertEqual({to_move_object(m) for m in moves},
                                 set(engine.get_legal_moves(engine.current_player)))
                move = rng.choice(moves)
                expected = apply_move(position, move)
                play(engine, to_move_object(move))
                actual = position_from_state(engine.state)
                self.assertEqual(actual.cells, expected.cells)
                self.assertEqual((actual.placed, actual.captured, actual.winner),
                                 (expected.placed, expected.captured, expected.winner))
                if not engine.state.game_over:
                    self.assertEqual(actual.to_move, expected.to_move)

    def test_cows_that_cannot_move_pass(self) -> None:
        # Tiger A1 steps to B1; the only empty cell, A1, is then walled in by Tigers.
        engine = engine_from(["T.CC", "TCCC", "CCCC", "CCTT"], side=Side.TIGER,
                             cows_captured=1)
        position = position_from_state(engine.state)
        after = apply_move(position, (0, 1, -1))
        play(engine, to_move_object((0, 1, -1)))
        self.assertIs(engine.state.current_side, Side.TIGER)
        self.assertEqual(after.to_move, position_from_state(engine.state).to_move)
        self.assertIsNone(after.winner)


class ComputerPlayerTests(unittest.TestCase):
    def test_every_level_plays_legal_moves_for_both_sides(self) -> None:
        for level in LEVELS:
            with self.subTest(level=level):
                engine = GameEngine()
                players = {p: ComputerPlayer(level, random.Random(p)) for p in (1, 2)}
                for _ in range(40):
                    if engine.state.game_over:
                        break
                    move = players[engine.current_player].choose_move(engine.state)
                    self.assertIn(move, engine.get_legal_moves(engine.current_player))
                    play(engine, move)

    def test_takes_the_winning_capture(self) -> None:
        engine = engine_from(["TC..", "....", "....", "T..T"], side=Side.TIGER,
                             cows_captured=config.COW_COUNT - 1)
        move = ComputerPlayer("NORMAL").choose_move(engine.state)
        self.assertEqual((move.from_cell, move.to_cell), (Cell(0, 0), Cell(0, 2)))

    def test_cows_trap_the_last_tiger_when_they_can(self) -> None:
        engine = engine_from(["TC..", "C.C.", "C...", "...."], side=Side.COW)
        # The Tiger's only move is jumping B1 to C1; the Cow on C2 stepping up closes it.
        move = ComputerPlayer("HARD").choose_move(engine.state)
        play(engine, move)
        self.assertIs(engine.state.winner, Side.COW)

    def test_no_move_when_game_is_over(self) -> None:
        engine = engine_from(["TC..", "....", "....", "T..T"], side=Side.TIGER,
                             cows_captured=config.COW_COUNT - 1)
        play(engine, ComputerPlayer("NORMAL").choose_move(engine.state))
        self.assertIs(engine.state.phase, Phase.GAME_OVER)
        self.assertIsNone(ComputerPlayer("NORMAL").choose_move(engine.state))

    def test_unknown_level(self) -> None:
        with self.assertRaises(ValueError):
            ComputerPlayer("IMPOSSIBLE")

    def test_levels_match_the_settings_choices(self) -> None:
        self.assertEqual(set(LEVELS), set(config.COMPUTER_LEVELS) - {"OFF"})

    def test_hard_beats_easy_on_both_sides(self) -> None:
        for seed in range(2):
            tigers = play_game(ComputerPlayer("HARD", random.Random(seed)),
                               ComputerPlayer("EASY", random.Random(seed + 10)))
            self.assertIs(tigers.state.winner, Side.TIGER)
            cows = play_game(ComputerPlayer("EASY", random.Random(seed)),
                             ComputerPlayer("HARD", random.Random(seed + 10)))
            self.assertIsNot(cows.state.winner, Side.TIGER)

    def test_hard_is_fast_enough_for_the_ui(self) -> None:
        engine = GameEngine()
        players = {p: ComputerPlayer("HARD", random.Random(p)) for p in (1, 2)}
        slowest = 0.0
        for _ in range(60):
            if engine.state.game_over:
                break
            started = time.perf_counter()
            move = players[engine.current_player].choose_move(engine.state)
            slowest = max(slowest, time.perf_counter() - started)
            play(engine, move)
        self.assertLess(slowest, MAX_THINK_SECONDS)


if __name__ == "__main__":
    unittest.main()
