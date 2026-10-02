"""Board animations for placing, moving and capturing pieces.

The game engine changes the state instantly; these animations only change how
the transition *looks*. While an animation runs, the destination cell is
hidden from the normal board drawing and the animated sprite is drawn instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import config
from game.cell import Cell
from game.piece import Piece
from game.state import MoveKind, MoveRecord
from ui.easing import clamp01, ease_in_out_cubic, ease_out_back, ease_out_cubic, lerp

CAPTURE_FADE_PORTION = 0.6  # The captured Cow disappears during this part of the jump.
PLACE_START_SCALE = 0.2
JUMP_EXTRA_SCALE = 0.15  # Tiger grows slightly at the top of its jump.


@dataclass(frozen=True)
class SpriteFrame:
    """One sprite to draw this frame, positioned in board cells (fractional)."""

    piece: Piece
    row: float
    col: float
    scale: float = 1.0
    alpha: int = 255
    lift: float = 0.0  # Upward offset in cells (jump arc).


class BoardAnimation:
    duration: float = 0.0

    def __init__(self) -> None:
        self.elapsed = 0.0

    @property
    def progress(self) -> float:
        return clamp01(self.elapsed / self.duration) if self.duration > 0 else 1.0

    @property
    def finished(self) -> bool:
        return self.elapsed >= self.duration

    def update(self, dt: float) -> None:
        self.elapsed += dt

    def hidden_cells(self) -> frozenset[Cell]:
        raise NotImplementedError

    def frames(self) -> list[SpriteFrame]:
        raise NotImplementedError


class PlaceAnimation(BoardAnimation):
    """A Cow drops onto its cell with a small bounce."""

    duration = config.PLACE_ANIMATION_TIME

    def __init__(self, cell: Cell, piece: Piece = Piece.COW) -> None:
        super().__init__()
        self.cell, self.piece = cell, piece

    def hidden_cells(self) -> frozenset[Cell]:
        return frozenset({self.cell})

    def frames(self) -> list[SpriteFrame]:
        t = self.progress
        return [SpriteFrame(self.piece, self.cell.row, self.cell.col,
                            scale=lerp(PLACE_START_SCALE, 1.0, ease_out_back(t)),
                            alpha=round(255 * ease_out_cubic(t)))]


class MoveAnimation(BoardAnimation):
    """A piece slides one cell."""

    duration = config.MOVE_ANIMATION_TIME

    def __init__(self, start: Cell, end: Cell, piece: Piece) -> None:
        super().__init__()
        self.start, self.end, self.piece = start, end, piece

    def hidden_cells(self) -> frozenset[Cell]:
        return frozenset({self.end})

    def frames(self) -> list[SpriteFrame]:
        t = ease_in_out_cubic(self.progress)
        return [SpriteFrame(self.piece, lerp(self.start.row, self.end.row, t),
                            lerp(self.start.col, self.end.col, t))]


class CaptureAnimation(BoardAnimation):
    """The Tiger jumps in an arc over the Cow, which shrinks and fades away."""

    duration = config.CAPTURE_ANIMATION_TIME

    def __init__(self, start: Cell, end: Cell, captured: Cell) -> None:
        super().__init__()
        self.start, self.end, self.captured = start, end, captured

    def hidden_cells(self) -> frozenset[Cell]:
        return frozenset({self.end, self.captured})

    def frames(self) -> list[SpriteFrame]:
        t = self.progress
        frames = []
        fade = clamp01(t / CAPTURE_FADE_PORTION)
        if fade < 1.0:
            frames.append(SpriteFrame(Piece.COW, self.captured.row, self.captured.col,
                                      scale=1.0 - 0.6 * fade, alpha=round(255 * (1 - fade))))
        eased = ease_in_out_cubic(t)
        arc = math.sin(math.pi * t)
        frames.append(SpriteFrame(Piece.TIGER, lerp(self.start.row, self.end.row, eased),
                                  lerp(self.start.col, self.end.col, eased),
                                  scale=1.0 + JUMP_EXTRA_SCALE * arc,
                                  lift=config.CAPTURE_JUMP_HEIGHT * arc))
        return frames  # Tiger last, so it is drawn above the Cow.


def animation_for(record: MoveRecord, piece: Piece) -> BoardAnimation | None:
    """The animation matching a move-history entry (None for PASS)."""
    if record.kind is MoveKind.PLACE:
        return PlaceAnimation(record.to_cell, piece)
    if record.kind is MoveKind.MOVE:
        return MoveAnimation(record.from_cell, record.to_cell, piece)
    if record.kind is MoveKind.CAPTURE:
        return CaptureAnimation(record.from_cell, record.to_cell, record.captured)
    return None


class BoardAnimator:
    """Runs board animations (normally one at a time; a new one replaces the old)."""

    def __init__(self, enabled: bool = config.ANIMATIONS_ENABLED) -> None:
        self.enabled = enabled
        self._animations: list[BoardAnimation] = []

    @property
    def busy(self) -> bool:
        return bool(self._animations)

    def start(self, animation: BoardAnimation | None) -> None:
        if animation is None or not self.enabled:
            return
        self._animations = [animation]  # The previous one is already reflected in the state.

    def clear(self) -> None:
        self._animations = []

    def update(self, dt: float) -> bool:
        """Advance; return True if an animation finished this frame."""
        finished = False
        for animation in self._animations:
            animation.update(dt)
            finished |= animation.finished
        self._animations = [a for a in self._animations if not a.finished]
        return finished

    def hidden_cells(self) -> frozenset[Cell]:
        cells: frozenset[Cell] = frozenset()
        for animation in self._animations:
            cells |= animation.hidden_cells()
        return cells

    def frames(self) -> list[SpriteFrame]:
        return [frame for animation in self._animations for frame in animation.frames()]
