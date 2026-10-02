"""The game engine: applies events to the state and enforces every rule.

The engine is pure Python (no OpenCV / MediaPipe / Pygame) so it can be
tested and played headless::

    engine = GameEngine()
    result = engine.handle_event({"player": 2, "action": "SELECT", "cell": [1, 1]})

Interpretation of SELECT on a cell for the player whose turn it is:

* Cow placement phase, Cows' turn: place a Cow on the (empty) cell.
* Otherwise, nothing selected: select one of your own pieces.
* Same cell as the selection: deselect.
* Another of your own pieces: switch the selection to it.
* Any other cell: try to move the selected piece there (step or capture).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from game.board import Board
from game.capture import can_tiger_capture as _can_tiger_capture
from game.capture import capture_cow as _remove_cow
from game.capture import get_tiger_captures as _get_tiger_captures
from game.cell import Cell
from game.cow import get_cow_moves as _get_cow_moves
from game.cow import validate_cow_move
from game.events import Action, GameEvent
from game.movement import VALID, Move, Validation, invalid
from game.piece import Piece
from game.state import (GameState, GameStats, MoveKind, MoveRecord, Phase, Side,
                        player_number_to_side)
from game.tiger import get_tiger_moves as _get_tiger_moves
from game.tiger import validate_tiger_move
from game.win_condition import (check_cow_win as _check_cow_win,
                                check_tiger_win as _check_tiger_win,
                                cows_have_legal_move)


class Outcome(Enum):
    """What an accepted (or rejected) event did — used by UI for feedback/sound."""

    PLACED = "PLACED"
    SELECTED = "SELECTED"
    DESELECTED = "DESELECTED"
    MOVED = "MOVED"
    CAPTURED = "CAPTURED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class ActionResult:
    """Result of :meth:`GameEngine.handle_event` and the action methods."""

    outcome: Outcome
    validation: Validation = VALID
    record: MoveRecord | None = None

    @property
    def valid(self) -> bool:
        return self.validation.valid

    @property
    def reason(self) -> str:
        return self.validation.reason

    def to_dict(self) -> dict[str, Any]:
        return {**self.validation.to_dict(), "outcome": self.outcome.value}


def _rejected(validation: Validation) -> ActionResult:
    return ActionResult(Outcome.REJECTED, validation)


class GameEngine:
    """Owns a :class:`GameState` and changes it only through validated actions."""

    def __init__(self, state: GameState | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._sides = player_number_to_side()
        self.state = state if state is not None else self._new_state()

    # ------------------------------------------------------------------ setup
    def _new_state(self) -> GameState:
        return GameState(board=Board.initial(), started_at=self._clock())

    def initialize_game(self) -> None:
        """Start a fresh game (Tigers in the corners, Cows to move first)."""
        self.state = self._new_state()

    def reset_game(self) -> None:
        """Alias for :meth:`initialize_game` used by "Play again"."""
        self.initialize_game()

    def side_of_player(self, player: int) -> Side:
        if player not in self._sides:
            raise ValueError(f"Unknown player number {player}")
        return self._sides[player]

    def player_of_side(self, side: Side) -> int:
        return next(number for number, s in self._sides.items() if s is side)

    @property
    def current_player(self) -> int:
        """Physical player number (1 or 2) whose turn it is."""
        return self.player_of_side(self.state.current_side)

    # ------------------------------------------------------------ event entry
    def handle_event(self, event: GameEvent | dict[str, Any]) -> ActionResult:
        """Apply one input event and report what happened."""
        if isinstance(event, dict):
            event = GameEvent.from_dict(event)
        side = self.side_of_player(event.player)
        common = self._check_can_act(side)
        if not common.valid:
            return _rejected(common)
        if event.action is Action.CANCEL:
            return self.deselect()
        if event.cell is None:
            return _rejected(invalid("no_cell", "Point at a board cell"))
        return self._handle_select(side, event.cell)

    def _handle_select(self, side: Side, cell: Cell) -> ActionResult:
        state = self.state
        if not state.board.is_on_board(cell):
            return _rejected(invalid("off_board", "Point at a board cell"))
        if side is Side.COW and state.phase is Phase.COW_PLACEMENT:
            return self.place_cow(cell)
        if state.selected is None:
            return self.select_piece(cell, self.player_of_side(side))
        if cell == state.selected:
            return self.deselect()
        if state.board.get(cell) is side.piece:
            return self.select_piece(cell, self.player_of_side(side))
        return self.move_piece(state.selected, cell)

    def _check_can_act(self, side: Side) -> Validation:
        if self.state.game_over:
            return invalid("game_over", "The game is over")
        if side is not self.state.current_side:
            return invalid("not_your_turn", "It is not your turn")
        return VALID

    # ---------------------------------------------------------------- actions
    def place_cow(self, cell: Cell) -> ActionResult:
        """Place a Cow on an empty cell (Cow placement phase, Cows' turn)."""
        state = self.state
        check = self._check_can_act(Side.COW)
        if not check.valid:
            return _rejected(check)
        if state.phase is not Phase.COW_PLACEMENT or state.cows_to_place <= 0:
            return _rejected(invalid("placement_over", "All Cows have already been placed"))
        if not state.board.is_on_board(cell):
            return _rejected(invalid("off_board", "Point at a board cell"))
        if not state.board.is_empty(cell):
            return _rejected(invalid("occupied", "Cows can only be placed on an empty cell"))
        state.board.set(cell, Piece.COW)
        state.cows_placed += 1
        record = self.add_move_history(Side.COW, MoveKind.PLACE, to_cell=cell)
        self._end_turn()
        return ActionResult(Outcome.PLACED, VALID, record)

    def select_piece(self, cell: Cell, player: int) -> ActionResult:
        """Select one of ``player``'s pieces so it can be moved."""
        side = self.side_of_player(player)
        check = self._check_can_act(side)
        if not check.valid:
            return _rejected(check)
        board = self.state.board
        if not board.is_on_board(cell):
            return _rejected(invalid("off_board", "Point at a board cell"))
        piece = board.get(cell)
        if piece is Piece.EMPTY:
            return _rejected(invalid("empty_cell", f"Select one of your {side.title}s"))
        if piece is not side.piece:
            return _rejected(invalid("opponent_piece", "You cannot select your opponent's piece"))
        if side is Side.COW and self.state.phase is Phase.COW_PLACEMENT:
            return _rejected(invalid("cows_locked",
                                     "Cows cannot move until all Cows are placed"))
        if not self.get_valid_moves(cell):
            return _rejected(invalid("no_moves", f"This {side.title} has no legal moves"))
        self.state.selected = cell
        return ActionResult(Outcome.SELECTED)

    def deselect(self) -> ActionResult:
        self.state.selected = None
        return ActionResult(Outcome.DESELECTED)

    def validate_move(self, from_cell: Cell, to_cell: Cell) -> tuple[Validation, Move | None]:
        """Full validation of moving the piece on from_cell, including turn/phase."""
        state = self.state
        if state.game_over:
            return invalid("game_over", "The game is over"), None
        board = state.board
        if not board.is_on_board(from_cell) or not board.is_on_board(to_cell):
            return invalid("off_board", "Move must stay on the board"), None
        piece = board.get(from_cell)
        if piece is Piece.EMPTY:
            return invalid("empty_cell", "There is no piece to move"), None
        if piece is not state.current_side.piece:
            return invalid("opponent_piece", "You cannot move your opponent's piece"), None
        if piece is Piece.COW:
            if state.phase is Phase.COW_PLACEMENT:
                return invalid("cows_locked", "Cows cannot move until all Cows are placed"), None
            return validate_cow_move(board, from_cell, to_cell)
        return validate_tiger_move(board, from_cell, to_cell)

    def move_piece(self, from_cell: Cell, to_cell: Cell) -> ActionResult:
        """Move (or capture with) the current side's piece."""
        validation, move = self.validate_move(from_cell, to_cell)
        if not validation.valid or move is None:
            return _rejected(validation)
        side = self.state.current_side
        board = self.state.board
        board.set(move.to_cell, board.get(move.from_cell))
        board.set(move.from_cell, Piece.EMPTY)
        kind = MoveKind.MOVE
        if move.captured is not None:
            self.capture_cow(move.captured)
            kind = MoveKind.CAPTURE
        record = self.add_move_history(side, kind, move.from_cell, move.to_cell, move.captured)
        self._end_turn()
        outcome = Outcome.CAPTURED if move.is_capture else Outcome.MOVED
        return ActionResult(outcome, VALID, record)

    def capture_cow(self, cell: Cell) -> None:
        """Remove a captured Cow and count it."""
        _remove_cow(self.state.board, cell)
        self.state.cows_captured += 1

    # ----------------------------------------------------------- turn logic
    def switch_turn(self) -> None:
        self.state.current_side = self.state.current_side.opponent
        self.state.selected = None

    def _end_turn(self) -> None:
        """Advance phase and turn after a successful action; detect game over."""
        state = self.state
        state.selected = None
        if state.phase is Phase.COW_PLACEMENT and state.cows_to_place == 0:
            state.phase = Phase.MOVEMENT
        # Only the capture win is checked before switching: "Tigers trapped"
        # is judged when it is actually the Tigers' turn to move.
        if self.check_tiger_win():
            self.check_game_over()
            return
        self.switch_turn()
        if self.check_game_over():
            return
        # Cows that cannot move (movement phase only) pass their turn.
        if (state.current_side is Side.COW and state.phase is Phase.MOVEMENT
                and not cows_have_legal_move(state.board)):
            self.add_move_history(Side.COW, MoveKind.PASS)
            self.switch_turn()
            self.check_game_over()

    def check_tiger_win(self) -> bool:
        return _check_tiger_win(self.state.cows_captured)

    def check_cow_win(self) -> bool:
        """Cows win if it is the Tigers' turn and they cannot move."""
        return self.state.current_side is Side.TIGER and _check_cow_win(self.state.board)

    def check_game_over(self) -> bool:
        """Detect a win; if found, end the game and record the winner."""
        state = self.state
        if state.game_over:
            return True
        if self.check_tiger_win():
            self._finish(Side.TIGER, "All Cows have been captured")
        elif self.check_cow_win():
            self._finish(Side.COW, "The Tigers have no legal moves")
        return state.game_over

    def _finish(self, winner: Side, reason: str) -> None:
        state = self.state
        state.phase = Phase.GAME_OVER
        state.winner = winner
        state.win_reason = reason
        state.selected = None
        state.ended_at = self._clock()

    # --------------------------------------------------------------- queries
    def get_valid_moves(self, cell: Cell) -> list[Move]:
        """Legal moves for the piece on ``cell``, respecting the current phase."""
        board = self.state.board
        if self.state.game_over or not board.is_on_board(cell):
            return []
        piece = board.get(cell)
        if piece is Piece.TIGER:
            return self.get_tiger_moves(cell)
        if piece is Piece.COW and self.state.phase is Phase.MOVEMENT:
            return self.get_cow_moves(cell)
        return []

    def get_tiger_moves(self, cell: Cell) -> list[Move]:
        return _get_tiger_moves(self.state.board, cell)

    def get_cow_moves(self, cell: Cell) -> list[Move]:
        return _get_cow_moves(self.state.board, cell)

    def get_tiger_captures(self, cell: Cell) -> list[Move]:
        return _get_tiger_captures(self.state.board, cell)

    def can_tiger_capture(self, from_cell: Cell, to_cell: Cell) -> Validation:
        return _can_tiger_capture(self.state.board, from_cell, to_cell)

    def get_legal_moves(self, player: int) -> list[Move]:
        """Every legal move for a player right now (placements use from_cell == to_cell)."""
        side = self.side_of_player(player)
        state = self.state
        if state.game_over or side is not state.current_side:
            return []
        if side is Side.COW and state.phase is Phase.COW_PLACEMENT:
            return [Move(cell, cell) for cell in state.board.cells_with(Piece.EMPTY)]
        return [move for cell in state.board.cells_with(side.piece)
                for move in self.get_valid_moves(cell)]

    def legal_targets(self) -> frozenset[Cell]:
        """Destination cells for the selected piece (for highlighting)."""
        if self.state.selected is None:
            return frozenset()
        return frozenset(move.to_cell for move in self.get_valid_moves(self.state.selected))

    def add_move_history(self, side: Side, kind: MoveKind, from_cell: Cell | None = None,
                         to_cell: Cell | None = None, captured: Cell | None = None) -> MoveRecord:
        record = MoveRecord(len(self.state.move_history) + 1, side, kind, from_cell, to_cell,
                            captured)
        self.state.move_history.append(record)
        return record

    def stats(self) -> GameStats:
        state = self.state
        history = state.move_history
        end = state.ended_at if state.ended_at is not None else self._clock()

        def count(side: Side, *kinds: MoveKind) -> int:
            return sum(1 for r in history if r.side is side and r.kind in kinds)

        return GameStats(
            duration_seconds=max(0.0, end - state.started_at),
            total_moves=sum(1 for r in history if r.kind is not MoveKind.PASS),
            cows_captured=state.cows_captured,
            tiger_moves=count(Side.TIGER, MoveKind.MOVE, MoveKind.CAPTURE),
            cow_moves=count(Side.COW, MoveKind.MOVE),
            cow_placements=count(Side.COW, MoveKind.PLACE),
        )
