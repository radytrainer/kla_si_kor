"""Win conditions.

* Tigers win when every Cow (COW_COUNT) has been captured.
* Cows win when it is the Tigers' turn and no Tiger has a legal move.
"""

from __future__ import annotations

import config
from game.board import Board
from game.cow import get_cow_moves
from game.piece import Piece
from game.tiger import get_tiger_moves


def tigers_have_legal_move(board: Board) -> bool:
    return any(get_tiger_moves(board, cell) for cell in board.cells_with(Piece.TIGER))


def cows_have_legal_move(board: Board) -> bool:
    return any(get_cow_moves(board, cell) for cell in board.cells_with(Piece.COW))


def check_tiger_win(cows_captured: int) -> bool:
    """True once all Cows have been captured."""
    return cows_captured >= config.COW_COUNT


def check_cow_win(board: Board) -> bool:
    """True when the Tigers are completely trapped."""
    return not tigers_have_legal_move(board)
