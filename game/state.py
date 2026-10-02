"""Game state model: sides, phases, move history and statistics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import config
from game.board import Board
from game.cell import Cell
from game.piece import Piece


class Side(Enum):
    """The two sides (the spec's "Player: TIGER / COW")."""

    TIGER = "TIGER"
    COW = "COW"

    @property
    def piece(self) -> Piece:
        return Piece.TIGER if self is Side.TIGER else Piece.COW

    @property
    def opponent(self) -> Side:
        return Side.COW if self is Side.TIGER else Side.TIGER

    @property
    def title(self) -> str:
        return self.value.capitalize()


class Phase(Enum):
    COW_PLACEMENT = "COW_PLACEMENT"
    MOVEMENT = "MOVEMENT"
    GAME_OVER = "GAME_OVER"


class MoveKind(Enum):
    PLACE = "PLACE"
    MOVE = "MOVE"
    CAPTURE = "CAPTURE"
    PASS = "PASS"  # The side to move had no legal move.


@dataclass(frozen=True)
class MoveRecord:
    """One entry of the move history."""

    number: int
    side: Side
    kind: MoveKind
    from_cell: Cell | None = None
    to_cell: Cell | None = None
    captured: Cell | None = None

    def describe(self) -> str:
        """Human-readable text, e.g. "Tiger moved A1 → A2"."""
        name = self.side.title
        if self.kind is MoveKind.PLACE:
            return f"{name} placed at {self.to_cell.name}"
        if self.kind is MoveKind.MOVE:
            return f"{name} moved {self.from_cell.name} → {self.to_cell.name}"
        if self.kind is MoveKind.CAPTURE:
            return (f"{name} captured Cow at {self.captured.name} "
                    f"({self.from_cell.name} → {self.to_cell.name})")
        return f"{name} has no legal move - turn passed"


def player_number_to_side() -> dict[int, Side]:
    """Map physical player numbers (1, 2) to sides, from config."""
    return {1: Side[config.PLAYER_1_SIDE], 2: Side[config.PLAYER_2_SIDE]}


@dataclass
class GameState:
    """Complete, serialisable state of one game."""

    board: Board = field(default_factory=Board.initial)
    current_side: Side = Side.COW  # Cows go first.
    phase: Phase = Phase.COW_PLACEMENT
    selected: Cell | None = None
    cows_placed: int = 0
    cows_captured: int = 0
    winner: Side | None = None
    win_reason: str = ""
    move_history: list[MoveRecord] = field(default_factory=list)
    started_at: float = 0.0
    ended_at: float | None = None

    @property
    def cows_to_place(self) -> int:
        return config.COW_COUNT - self.cows_placed

    @property
    def cows_on_board(self) -> int:
        return self.board.count(Piece.COW)

    @property
    def tigers_on_board(self) -> int:
        return self.board.count(Piece.TIGER)

    @property
    def game_over(self) -> bool:
        return self.phase is Phase.GAME_OVER


@dataclass(frozen=True)
class GameStats:
    """End-of-game statistics."""

    duration_seconds: float
    total_moves: int
    cows_captured: int
    tiger_moves: int
    cow_moves: int
    cow_placements: int

    @property
    def duration_text(self) -> str:
        minutes, seconds = divmod(int(self.duration_seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"
