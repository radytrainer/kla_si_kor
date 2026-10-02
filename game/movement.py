"""Shared movement primitives: moves, validation results and geometry checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from game.board import Board
from game.cell import Cell

# Up, down, left, right. No diagonals in this game.
ORTHOGONAL_DIRECTIONS: tuple[tuple[int, int], ...] = ((-1, 0), (1, 0), (0, -1), (0, 1))
STEP_DISTANCE = 1
JUMP_DISTANCE = 2


@dataclass(frozen=True)
class Move:
    """A piece moving from one cell to another, optionally capturing a Cow."""

    from_cell: Cell
    to_cell: Cell
    captured: Cell | None = None

    @property
    def is_capture(self) -> bool:
        return self.captured is not None


@dataclass(frozen=True)
class Validation:
    """Outcome of a rule check. ``code`` is a stable id the UI can translate."""

    valid: bool
    reason: str = ""
    code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "reason": self.reason}


VALID = Validation(True)


def invalid(code: str, reason: str) -> Validation:
    return Validation(False, reason, code)


def orthogonal_distance(from_cell: Cell, to_cell: Cell) -> int | None:
    """Distance along a straight row/column, or None if not in a straight line."""
    d_row, d_col = to_cell.row - from_cell.row, to_cell.col - from_cell.col
    if d_row != 0 and d_col != 0:
        return None
    return abs(d_row) + abs(d_col)


def midpoint(from_cell: Cell, to_cell: Cell) -> Cell:
    """The cell halfway between two cells two apart in a straight line."""
    return Cell((from_cell.row + to_cell.row) // 2, (from_cell.col + to_cell.col) // 2)


def validate_geometry(board: Board, from_cell: Cell, to_cell: Cell, piece_name: str,
                      max_distance: int) -> Validation:
    """Checks common to every piece: on board, not diagonal, not too far."""
    if not board.is_on_board(from_cell) or not board.is_on_board(to_cell):
        return invalid("off_board", "Move must stay on the board")
    distance = orthogonal_distance(from_cell, to_cell)
    if distance is None:
        return invalid("diagonal", f"{piece_name} cannot move diagonally")
    if distance == 0:
        return invalid("same_cell", "Choose a different cell")
    if distance > max_distance:
        return invalid("too_far", f"{piece_name} can only move one cell"
                       if max_distance == STEP_DISTANCE
                       else f"{piece_name} cannot move that far")
    return VALID


def adjacent_empty_cells(board: Board, cell: Cell) -> list[Cell]:
    """Orthogonal neighbours of ``cell`` that are empty."""
    return [cell.offset(d_row, d_col) for d_row, d_col in ORTHOGONAL_DIRECTIONS
            if board.is_empty(cell.offset(d_row, d_col))]
