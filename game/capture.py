"""Tiger capture rules.

A Tiger captures a Cow by jumping over it when:
1. the Cow is orthogonally adjacent to the Tiger,
2. the landing cell is exactly one cell beyond the Cow in the same line,
3. the landing cell is empty.
Tigers can never jump over Tigers; nothing can jump over an empty cell.
"""

from __future__ import annotations

from game.board import Board
from game.cell import Cell
from game.movement import (JUMP_DISTANCE, ORTHOGONAL_DIRECTIONS, VALID, Move, Validation,
                           invalid, midpoint, validate_geometry)
from game.piece import Piece


def can_tiger_capture(board: Board, from_cell: Cell, to_cell: Cell) -> Validation:
    """Check whether the Tiger on from_cell may capture by jumping to to_cell."""
    geometry = validate_geometry(board, from_cell, to_cell, "Tiger", JUMP_DISTANCE)
    if not geometry.valid:
        return geometry
    if board.get(from_cell) is not Piece.TIGER:
        return invalid("not_tiger", "Only a Tiger can capture")
    jumped = midpoint(from_cell, to_cell)
    if jumped == from_cell or jumped == to_cell:
        return invalid("not_a_jump", "A capture must jump over a Cow")
    over = board.get(jumped)
    if over is Piece.TIGER:
        return invalid("jump_tiger", "Tiger cannot jump over another Tiger")
    if over is not Piece.COW:
        return invalid("jump_empty", "Tiger can only jump over a Cow")
    if not board.is_empty(to_cell):
        return invalid("occupied", "Tiger must land on an empty cell")
    return VALID


def get_tiger_captures(board: Board, cell: Cell) -> list[Move]:
    """All captures available to the Tiger on ``cell``."""
    captures: list[Move] = []
    for d_row, d_col in ORTHOGONAL_DIRECTIONS:
        target = cell.offset(d_row * JUMP_DISTANCE, d_col * JUMP_DISTANCE)
        if board.is_on_board(target) and can_tiger_capture(board, cell, target).valid:
            captures.append(Move(cell, target, captured=midpoint(cell, target)))
    return captures


def capture_cow(board: Board, cell: Cell) -> None:
    """Remove the Cow on ``cell`` from the board."""
    if board.get(cell) is not Piece.COW:
        raise ValueError(f"No Cow to capture at {cell.name}")
    board.set(cell, Piece.EMPTY)
