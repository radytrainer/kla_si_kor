"""GameEngine tests: events, turns, phases, validation, history, restart, stats."""

from __future__ import annotations

import random
import unittest

import config
from game.cell import Cell
from game.events import Action, GameEvent
from game.game_engine import GameEngine, Outcome
from game.piece import Piece
from game.state import MoveKind, Phase, Side
from tests.helpers import COW_PLAYER, TIGER_PLAYER, FakeClock, engine_from, select

C = Cell


class InitialStateTests(unittest.TestCase):
    def test_new_game(self) -> None:
        state = GameEngine().state
        self.assertEqual(state.board.to_strings(), ["T..T", "....", "....", "T..T"])
        self.assertEqual(state.tigers_on_board, 4)
        self.assertIs(state.current_side, Side.COW)  # Cows go first.
        self.assertIs(state.phase, Phase.COW_PLACEMENT)
        self.assertEqual((state.cows_to_place, state.cows_captured), (12, 0))
        self.assertIsNone(state.selected)
        self.assertIsNone(state.winner)
        self.assertEqual(state.move_history, [])

    def test_player_mapping_from_config(self) -> None:
        engine = GameEngine()
        self.assertIs(engine.side_of_player(1), Side[config.PLAYER_1_SIDE])
        self.assertIs(engine.side_of_player(2), Side[config.PLAYER_2_SIDE])
        self.assertEqual(engine.current_player, COW_PLAYER)
        with self.assertRaises(ValueError):
            engine.side_of_player(3)


class PlacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = GameEngine()

    def test_place_cow_then_turn_switches_to_tiger(self) -> None:
        result = select(self.engine, COW_PLAYER, 1, 1)
        self.assertIs(result.outcome, Outcome.PLACED)
        self.assertIs(self.engine.state.board.get(C(1, 1)), Piece.COW)
        self.assertEqual(self.engine.state.cows_to_place, 11)
        self.assertIs(self.engine.state.current_side, Side.TIGER)
        self.assertEqual(result.record.describe(), "Cow placed at B2")

    def test_cannot_place_on_occupied_cell(self) -> None:
        result = select(self.engine, COW_PLAYER, 0, 0)
        self.assertFalse(result.valid)
        self.assertEqual(result.validation.code, "occupied")
        self.assertIs(self.engine.state.current_side, Side.COW)

    def test_tiger_cannot_act_on_cow_turn(self) -> None:
        result = select(self.engine, TIGER_PLAYER, 0, 0)
        self.assertEqual(result.to_dict(), {"valid": False, "reason": "It is not your turn",
                                            "outcome": "REJECTED"})

    def test_cows_cannot_move_during_placement(self) -> None:
        select(self.engine, COW_PLAYER, 1, 1)
        select(self.engine, TIGER_PLAYER, 0, 0)
        select(self.engine, TIGER_PLAYER, 0, 1)  # Tiger A1 -> B1.
        self.assertIs(self.engine.state.current_side, Side.COW)
        self.assertEqual(self.engine.select_piece(C(1, 1), COW_PLAYER).validation.code,
                         "cows_locked")
        self.assertEqual(self.engine.validate_move(C(1, 1), C(1, 2))[0].code, "cows_locked")
        # Selecting the Cow's own cell during placement is "occupied", not a selection.
        self.assertEqual(select(self.engine, COW_PLAYER, 1, 1).validation.code, "occupied")

    def test_tiger_moves_and_captures_during_placement(self) -> None:
        select(self.engine, COW_PLAYER, 0, 1)  # Cow B1 next to Tiger A1.
        select(self.engine, TIGER_PLAYER, 0, 0)
        result = select(self.engine, TIGER_PLAYER, 0, 2)  # A1 jumps B1 -> C1.
        self.assertIs(result.outcome, Outcome.CAPTURED)
        self.assertEqual(self.engine.state.cows_captured, 1)
        self.assertEqual(self.engine.state.cows_to_place, 11)  # Placement count unchanged.
        self.assertIs(self.engine.state.phase, Phase.COW_PLACEMENT)
        self.assertEqual(result.record.describe(), "Tiger captured Cow at B1 (A1 → C1)")

    def test_phase_changes_after_twelfth_cow(self) -> None:
        engine = engine_from(["T..T", "CCCC", "CCC.", "T..T"], side=Side.COW,
                             phase=Phase.COW_PLACEMENT, cows_placed=11, cows_captured=4)
        result = select(engine, COW_PLAYER, 2, 3)
        self.assertIs(result.outcome, Outcome.PLACED)
        self.assertIs(engine.state.phase, Phase.MOVEMENT)
        self.assertIs(engine.state.current_side, Side.TIGER)
        self.assertEqual(engine.state.cows_to_place, 0)


class SelectionAndMovementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = engine_from(["T..T", ".C..", "....", "T..T"])

    def test_select_move_and_turn_switch(self) -> None:
        self.assertIs(select(self.engine, TIGER_PLAYER, 0, 0).outcome, Outcome.SELECTED)
        self.assertEqual(self.engine.legal_targets(), frozenset({C(0, 1), C(1, 0)}))
        result = select(self.engine, TIGER_PLAYER, 1, 0)
        self.assertIs(result.outcome, Outcome.MOVED)
        self.assertEqual(result.record.describe(), "Tiger moved A1 → A2")
        self.assertIs(self.engine.state.current_side, Side.COW)
        self.assertIsNone(self.engine.state.selected)

    def test_reselect_deselect_and_cancel(self) -> None:
        select(self.engine, TIGER_PLAYER, 0, 0)
        self.assertIs(select(self.engine, TIGER_PLAYER, 0, 3).outcome, Outcome.SELECTED)
        self.assertEqual(self.engine.state.selected, C(0, 3))
        self.assertIs(select(self.engine, TIGER_PLAYER, 0, 3).outcome, Outcome.DESELECTED)
        select(self.engine, TIGER_PLAYER, 0, 0)
        cancel = self.engine.handle_event(GameEvent(TIGER_PLAYER, Action.CANCEL))
        self.assertIs(cancel.outcome, Outcome.DESELECTED)
        self.assertIsNone(self.engine.state.selected)

    def test_invalid_move_keeps_turn_and_selection(self) -> None:
        select(self.engine, TIGER_PLAYER, 0, 0)
        result = select(self.engine, TIGER_PLAYER, 1, 1)  # Diagonal onto a Cow.
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "Tiger cannot move diagonally")
        self.assertEqual(self.engine.state.selected, C(0, 0))
        self.assertIs(self.engine.state.current_side, Side.TIGER)

    def test_cannot_select_opponent_or_empty(self) -> None:
        self.assertEqual(select(self.engine, TIGER_PLAYER, 1, 1).validation.code,
                         "opponent_piece")
        self.assertEqual(select(self.engine, TIGER_PLAYER, 2, 2).validation.code, "empty_cell")

    def test_cannot_move_opponent_piece_directly(self) -> None:
        self.assertEqual(self.engine.move_piece(C(1, 1), C(1, 2)).validation.code,
                         "opponent_piece")

    def test_cow_moves_in_movement_phase(self) -> None:
        select(self.engine, TIGER_PLAYER, 0, 0)
        select(self.engine, TIGER_PLAYER, 1, 0)  # Tiger A1 -> A2, now Cow's turn.
        self.assertIs(select(self.engine, COW_PLAYER, 1, 1).outcome, Outcome.SELECTED)
        jump = select(self.engine, COW_PLAYER, 1, 3)
        self.assertEqual(jump.reason, "Cow cannot jump")
        onto_tiger = select(self.engine, COW_PLAYER, 1, 0)
        self.assertEqual(onto_tiger.reason, "Cow cannot capture a Tiger")
        result = select(self.engine, COW_PLAYER, 2, 1)
        self.assertIs(result.outcome, Outcome.MOVED)
        self.assertEqual(result.record.describe(), "Cow moved B2 → B3")

    def test_piece_with_no_moves_cannot_be_selected(self) -> None:
        engine = engine_from(["TCC.", "CC..", "C...", "...T"])  # A1 boxed in.
        self.assertEqual(select(engine, TIGER_PLAYER, 0, 0).validation.code, "no_moves")

    def test_tiger_cannot_jump_tiger_or_land_occupied_via_engine(self) -> None:
        engine = engine_from(["....",
                              "TT..",
                              "C...",
                              "C..T"])
        self.assertIs(select(engine, TIGER_PLAYER, 1, 0).outcome, Outcome.SELECTED)
        self.assertEqual(select(engine, TIGER_PLAYER, 1, 2).validation.code, "jump_tiger")
        self.assertEqual(select(engine, TIGER_PLAYER, 3, 0).validation.code, "occupied")
        self.assertIs(engine.state.current_side, Side.TIGER)

    def test_off_board_and_missing_cell(self) -> None:
        self.assertEqual(select(self.engine, TIGER_PLAYER, 4, 0).validation.code, "off_board")
        result = self.engine.handle_event(GameEvent(TIGER_PLAYER, Action.SELECT, None))
        self.assertEqual(result.validation.code, "no_cell")


class PassTurnTests(unittest.TestCase):
    def test_blocked_cows_pass(self) -> None:
        # After Tiger D4 -> D3, the only Cow (A1) is boxed in by Tigers.
        engine = engine_from(["CT..", "T...", "....", "...T"])
        select(engine, TIGER_PLAYER, 3, 3)
        select(engine, TIGER_PLAYER, 2, 3)
        self.assertIs(engine.state.current_side, Side.TIGER)
        kinds = [record.kind for record in engine.state.move_history]
        self.assertEqual(kinds, [MoveKind.MOVE, MoveKind.PASS])
        self.assertFalse(engine.state.game_over)


class GameOverAndRestartTests(unittest.TestCase):
    def finished_engine(self) -> GameEngine:
        engine = engine_from(["TC..", "....", "....", "...T"],
                             cows_captured=config.COW_COUNT - 1)
        select(engine, TIGER_PLAYER, 0, 0)
        select(engine, TIGER_PLAYER, 0, 2)
        return engine

    def test_events_rejected_after_game_over(self) -> None:
        engine = self.finished_engine()
        for player in (TIGER_PLAYER, COW_PLAYER):
            self.assertEqual(select(engine, player, 1, 1).validation.code, "game_over")
        self.assertEqual(engine.get_legal_moves(TIGER_PLAYER), [])

    def test_restart(self) -> None:
        engine = self.finished_engine()
        engine.reset_game()
        state = engine.state
        self.assertEqual(state.board.to_strings(), ["T..T", "....", "....", "T..T"])
        self.assertIs(state.phase, Phase.COW_PLACEMENT)
        self.assertIs(state.current_side, Side.COW)
        self.assertIsNone(state.winner)
        self.assertEqual((state.cows_captured, state.cows_placed), (0, 0))
        self.assertEqual(state.move_history, [])

    def test_stats(self) -> None:
        clock = FakeClock(100.0)
        engine = GameEngine(clock=clock)
        select(engine, COW_PLAYER, 0, 1)
        select(engine, TIGER_PLAYER, 0, 0)
        select(engine, TIGER_PLAYER, 0, 2)  # Capture.
        select(engine, COW_PLAYER, 2, 2)
        clock.now = 100.0 + 8 * 60 + 32
        stats = engine.stats()
        self.assertEqual(stats.duration_text, "08:32")
        self.assertEqual((stats.total_moves, stats.tiger_moves, stats.cow_placements,
                          stats.cow_moves, stats.cows_captured), (3, 1, 2, 0, 1))


class EventFormatTests(unittest.TestCase):
    def test_dict_round_trip(self) -> None:
        data = {"player": 1, "action": "SELECT", "cell": [2, 3]}
        event = GameEvent.from_dict(data)
        self.assertEqual(event, GameEvent(1, Action.SELECT, C(2, 3)))
        self.assertEqual(event.to_dict(), data)

    def test_legal_moves_for_placement(self) -> None:
        engine = GameEngine()
        self.assertEqual(len(engine.get_legal_moves(COW_PLAYER)), 12)
        self.assertEqual(engine.get_legal_moves(TIGER_PLAYER), [])  # Not their turn.


class RandomPlayoutTests(unittest.TestCase):
    """Play many random legal games and check invariants after every action."""

    GAMES = 200
    MAX_ACTIONS = 300

    def test_invariants_hold(self) -> None:
        finished = 0
        for seed in range(self.GAMES):
            rng = random.Random(seed)
            engine = GameEngine()
            for _ in range(self.MAX_ACTIONS):
                if engine.state.game_over:
                    finished += 1
                    break
                player = engine.current_player
                moves = engine.get_legal_moves(player)
                self.assertTrue(moves, f"seed {seed}: side to move has no legal move")
                move = rng.choice(moves)
                if move.from_cell == move.to_cell:
                    result = select(engine, player, *move.to_cell)
                else:
                    select(engine, player, *move.from_cell)
                    result = select(engine, player, *move.to_cell)
                self.assertTrue(result.valid, f"seed {seed}: {result.reason}")
                self._check_invariants(engine, seed)
        self.assertGreater(finished, 0, "no random game ever finished")

    def _check_invariants(self, engine: GameEngine, seed: int) -> None:
        state = engine.state
        self.assertEqual(state.tigers_on_board, config.TIGER_COUNT, f"seed {seed}")
        self.assertEqual(state.cows_on_board + state.cows_captured + state.cows_to_place,
                         config.COW_COUNT, f"seed {seed}")
        if state.phase is Phase.MOVEMENT:
            self.assertEqual(state.cows_to_place, 0)
        if state.game_over:
            self.assertIsNotNone(state.winner)


if __name__ == "__main__":
    unittest.main()
