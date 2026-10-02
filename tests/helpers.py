"""Shared helpers for game-logic tests."""

from __future__ import annotations

from collections.abc import Sequence

import config
from game.board import Board
from game.game_engine import GameEngine
from game.piece import Piece
from game.state import GameState, Phase, Side

TIGER_PLAYER = 1
COW_PLAYER = 2


class FakeClock:
    """Deterministic clock for duration tests."""

    def __init__(self, start: float = 1000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def engine_from(lines: Sequence[str], side: Side = Side.TIGER, phase: Phase = Phase.MOVEMENT,
                cows_placed: int | None = None, cows_captured: int = 0,
                clock: FakeClock | None = None) -> GameEngine:
    """Build an engine from a text board, e.g. ["T..T", ".C..", "....", "T..T"]."""
    board = Board.from_strings(lines)
    if cows_placed is None:
        cows_placed = (config.COW_COUNT if phase is Phase.MOVEMENT
                       else board.count(Piece.COW) + cows_captured)
    clock = clock or FakeClock()
    state = GameState(board=board, current_side=side, phase=phase, cows_placed=cows_placed,
                      cows_captured=cows_captured, started_at=clock())
    return GameEngine(state, clock=clock)


def select(engine: GameEngine, player: int, row: int, col: int):
    return engine.handle_event({"player": player, "action": "SELECT", "cell": [row, col]})
