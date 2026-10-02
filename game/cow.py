"""Cow movement: exactly one orthogonal step to an empty cell. No captures, no jumps."""

from __future__ import annotations

from game.board import Board
from game.cell import Cell
from game.movement import (STEP_DISTANCE, Move, Validation, adjacent_empty_cells, invalid,
                           orthogonal_distance, validate_geometry)
from game.piece import Piece


def get_cow_moves(board: Board, cell: Cell) -> list[Move]:
    """All legal moves for the Cow on ``cell``."""
    return [Move(cell, target) for target in adjacent_empty_cells(board, cell)]


def validate_cow_move(board: Board, from_cell: Cell, to_cell: Cell) -> tuple[Validation,
                                                                             Move | None]:
    """Validate a Cow move; on success also return the resulting Move."""
    if (board.is_on_board(from_cell) and board.is_on_board(to_cell)
            and (orthogonal_distance(from_cell, to_cell) or 0) > STEP_DISTANCE):
        return invalid("cow_jump", "Cow cannot jump"), None
    geometry = validate_geometry(board, from_cell, to_cell, "Cow", STEP_DISTANCE)
    if not geometry.valid:
        return geometry, None
    target = board.get(to_cell)
    if target is Piece.TIGER:
        return invalid("cow_capture", "Cow cannot capture a Tiger"), None
    if target is not Piece.EMPTY:
        return invalid("occupied", "Destination cell is occupied"), None
    return geometry, Move(from_cell, to_cell)
