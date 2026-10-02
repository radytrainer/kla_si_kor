"""Tiger movement: one orthogonal step to an empty cell, or a capture jump."""

from __future__ import annotations

from game.board import Board
from game.capture import can_tiger_capture, get_tiger_captures
from game.cell import Cell
from game.movement import (JUMP_DISTANCE, Move, Validation,
                           adjacent_empty_cells, invalid, midpoint, orthogonal_distance,
                           validate_geometry)
from game.piece import Piece


def get_tiger_moves(board: Board, cell: Cell) -> list[Move]:
    """All legal moves (steps and captures) for the Tiger on ``cell``."""
    steps = [Move(cell, target) for target in adjacent_empty_cells(board, cell)]
    return steps + get_tiger_captures(board, cell)


def validate_tiger_move(board: Board, from_cell: Cell, to_cell: Cell) -> tuple[Validation,
                                                                               Move | None]:
    """Validate a Tiger move; on success also return the resulting Move."""
    geometry = validate_geometry(board, from_cell, to_cell, "Tiger", JUMP_DISTANCE)
    if not geometry.valid:
        return geometry, None
    if orthogonal_distance(from_cell, to_cell) == JUMP_DISTANCE:
        capture = can_tiger_capture(board, from_cell, to_cell)
        if not capture.valid:
            return capture, None
        return capture, Move(from_cell, to_cell, captured=midpoint(from_cell, to_cell))
    # Geometry passed and it is not a jump, so this is a single step.
    if board.get(to_cell) is not Piece.EMPTY:
        return invalid("occupied", "Destination cell is occupied"), None
    return geometry, Move(from_cell, to_cell)
