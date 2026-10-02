"""Computer opponent: chooses a move for either side by looking a few turns ahead.

The search uses its own compact copy of the rules (a position is a tuple of
cell symbols) because it visits thousands of positions per move and the
engine's validated, record-keeping actions are far too slow for that. The
test suite plays random games through both and checks they always agree.

    move = ComputerPlayer("NORMAL").choose_move(engine.state)
    # move.from_cell == move.to_cell for a Cow placement
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import config
from game.cell import Cell
from game.movement import Move
from game.piece import Piece
from game.state import GameState, Phase, Side

TIGER, COW, EMPTY = Piece.TIGER.value, Piece.COW.value, Piece.EMPTY.value
DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))

# Level -> (search depth in turns, chance of playing a random legal move instead).
LEVELS: dict[str, tuple[int, float]] = {
    "EASY": (1, 0.35),
    "NORMAL": (2, 0.0),
    "HARD": (4, 0.0),
}

WIN_SCORE = 100_000
CAPTURE_WEIGHT = 1_000  # Captured Cows dominate everything else.
THREAT_WEIGHT = 60  # Cows that can be captured right now.
MOBILITY_WEIGHT = 8  # Tiger moves available.
TRAPPED_TIGER_WEIGHT = 40  # Each Tiger that cannot move.


@dataclass(frozen=True)
class Position:
    """Everything the search needs; ``winner`` is TIGER/COW once the game ends."""

    cells: tuple[str, ...]  # Row by row, BOARD_ROWS × BOARD_COLS symbols.
    to_move: str  # TIGER or COW
    placed: int
    captured: int
    winner: str | None = None


# A move as indices: (from, to, captured or -1). Placement: from == to.
IndexMove = tuple[int, int, int]


def position_from_state(state: GameState) -> Position:
    board = state.board
    cells = tuple(board.get(cell).value for cell in board.cells())
    winner = state.winner.piece.value if state.winner is not None else None
    return Position(cells, state.current_side.piece.value, state.cows_placed,
                    state.cows_captured, winner)


def _neighbours(index: int, distance: int) -> list[tuple[int, int]]:
    """(target, jumped-over) index pairs ``distance`` cells away in each direction."""
    row, col = divmod(index, config.BOARD_COLS)
    result = []
    for d_row, d_col in DIRECTIONS:
        r, c = row + d_row * distance, col + d_col * distance
        if 0 <= r < config.BOARD_ROWS and 0 <= c < config.BOARD_COLS:
            over = (row + d_row) * config.BOARD_COLS + col + d_col
            result.append((r * config.BOARD_COLS + c, over))
    return result


_CELL_COUNT = config.BOARD_ROWS * config.BOARD_COLS
_STEPS = [[target for target, _ in _neighbours(i, 1)] for i in range(_CELL_COUNT)]
_JUMPS = [_neighbours(i, 2) for i in range(_CELL_COUNT)]


def _tiger_moves(cells: tuple[str, ...]) -> list[IndexMove]:
    moves = []
    for index, symbol in enumerate(cells):
        if symbol != TIGER:
            continue
        for target, over in _JUMPS[index]:  # Captures first: better pruning.
            if cells[over] == COW and cells[target] == EMPTY:
                moves.append((index, target, over))
        moves.extend((index, target, -1) for target in _STEPS[index] if cells[target] == EMPTY)
    return moves


def _cow_moves(cells: tuple[str, ...]) -> list[IndexMove]:
    return [(index, target, -1) for index, symbol in enumerate(cells) if symbol == COW
            for target in _STEPS[index] if cells[target] == EMPTY]


def legal_moves(position: Position) -> list[IndexMove]:
    if position.winner is not None:
        return []
    if position.to_move == TIGER:
        return _tiger_moves(position.cells)
    if position.placed < config.COW_COUNT:
        return [(i, i, -1) for i, symbol in enumerate(position.cells) if symbol == EMPTY]
    return _cow_moves(position.cells)


def apply_move(position: Position, move: IndexMove) -> Position:
    """The position after ``move``, following the same turn logic as the engine."""
    frm, to, over = move
    cells = list(position.cells)
    placed, captured = position.placed, position.captured
    if frm == to:
        cells[to] = COW
        placed += 1
    else:
        cells[to], cells[frm] = cells[frm], EMPTY
        if over >= 0:
            cells[over] = EMPTY
            captured += 1
    board = tuple(cells)
    if captured >= config.COW_COUNT:
        return Position(board, position.to_move, placed, captured, TIGER)
    to_move = COW if position.to_move == TIGER else TIGER
    if to_move == COW and placed >= config.COW_COUNT and not _cow_moves(board):
        to_move = TIGER  # The Cows cannot move: they pass.
    if to_move == TIGER and not _tiger_moves(board):
        return Position(board, to_move, placed, captured, COW)
    return Position(board, to_move, placed, captured)


def evaluate(position: Position) -> float:
    """Score from the Tigers' point of view (positive = good for Tigers)."""
    if position.winner is not None:
        return WIN_SCORE if position.winner == TIGER else -WIN_SCORE
    cells = position.cells
    moves = _tiger_moves(cells)
    threatened = len({over for _, _, over in moves if over >= 0})
    movable = {frm for frm, _, _ in moves}
    trapped = sum(1 for i, symbol in enumerate(cells) if symbol == TIGER and i not in movable)
    return (position.captured * CAPTURE_WEIGHT + threatened * THREAT_WEIGHT
            + len(moves) * MOBILITY_WEIGHT - trapped * TRAPPED_TIGER_WEIGHT)


def _search(position: Position, depth: int, alpha: float, beta: float) -> float:
    """Alpha-beta minimax; Tigers maximise. Sooner wins score higher."""
    if position.winner is not None:
        score = evaluate(position)
        return score + depth if score > 0 else score - depth
    if depth == 0:
        return evaluate(position)
    maximising = position.to_move == TIGER
    best = -math.inf if maximising else math.inf
    for move in legal_moves(position):
        score = _search(apply_move(position, move), depth - 1, alpha, beta)
        if maximising:
            best = max(best, score)
            alpha = max(alpha, score)
        else:
            best = min(best, score)
            beta = min(beta, score)
        if alpha >= beta:
            break
    return best


def to_move_object(move: IndexMove) -> Move:
    frm, to, over = move
    cell = lambda index: Cell(*divmod(index, config.BOARD_COLS))  # noqa: E731
    return Move(cell(frm), cell(to), cell(over) if over >= 0 else None)


class ComputerPlayer:
    """Picks moves at one of the :data:`LEVELS`."""

    def __init__(self, level: str = "NORMAL", rng: random.Random | None = None) -> None:
        if level not in LEVELS:
            raise ValueError(f"Unknown computer level {level!r}")
        self.level = level
        self._depth, self._blunder = LEVELS[level]
        self._rng = rng or random.Random()

    def choose_move(self, state: GameState) -> Move | None:
        """The move to play for the side on turn, or None if there is none."""
        if state.phase is Phase.GAME_OVER:
            return None
        position = position_from_state(state)
        moves = legal_moves(position)
        if not moves:
            return None
        if self._rng.random() < self._blunder:
            return to_move_object(self._rng.choice(moves))
        sign = 1 if state.current_side is Side.TIGER else -1
        scored = [(sign * _search(apply_move(position, move), self._depth - 1,
                                  -math.inf, math.inf), move) for move in moves]
        best = max(score for score, _ in scored)
        # Several equally good moves: vary the game instead of always playing the first.
        return to_move_object(self._rng.choice([m for s, m in scored if s == best]))
