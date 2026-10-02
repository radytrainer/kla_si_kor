"""The 4×4 board: a grid of :class:`Piece` values with query helpers."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import config
from game.cell import Cell
from game.piece import Piece


class Board:
    """Mutable grid of pieces. Knows geometry only, not the rules."""

    def __init__(self, rows: int = config.BOARD_ROWS, cols: int = config.BOARD_COLS) -> None:
        self.rows = rows
        self.cols = cols
        self._grid: list[list[Piece]] = [[Piece.EMPTY] * cols for _ in range(rows)]

    # -- construction ------------------------------------------------------------
    @classmethod
    def initial(cls) -> Board:
        """The starting position: Tigers on TIGER_START_POSITIONS, no Cows."""
        board = cls()
        for row, col in config.TIGER_START_POSITIONS:
            board.set(Cell(row, col), Piece.TIGER)
        return board

    @classmethod
    def from_strings(cls, lines: Sequence[str]) -> Board:
        """Build a board from text rows, e.g. ["T..T", ".C..", "....", "T..T"]."""
        symbols = {piece.value: piece for piece in Piece}
        board = cls(len(lines), len(lines[0]))
        for row, line in enumerate(lines):
            if len(line) != board.cols:
                raise ValueError(f"Row {row} has {len(line)} cells, expected {board.cols}")
            for col, symbol in enumerate(line):
                if symbol not in symbols:
                    raise ValueError(f"Unknown board symbol {symbol!r}")
                board.set(Cell(row, col), symbols[symbol])
        return board

    def to_strings(self) -> list[str]:
        return ["".join(piece.value for piece in row) for row in self._grid]

    def copy(self) -> Board:
        clone = Board(self.rows, self.cols)
        clone._grid = [row[:] for row in self._grid]
        return clone

    # -- queries -----------------------------------------------------------------
    def is_on_board(self, cell: Cell) -> bool:
        return 0 <= cell.row < self.rows and 0 <= cell.col < self.cols

    def get(self, cell: Cell) -> Piece:
        if not self.is_on_board(cell):
            raise IndexError(f"{cell} is off the board")
        return self._grid[cell.row][cell.col]

    def is_empty(self, cell: Cell) -> bool:
        return self.is_on_board(cell) and self.get(cell) is Piece.EMPTY

    def cells(self) -> Iterator[Cell]:
        for row in range(self.rows):
            for col in range(self.cols):
                yield Cell(row, col)

    def cells_with(self, piece: Piece) -> list[Cell]:
        return [cell for cell in self.cells() if self.get(cell) is piece]

    def count(self, piece: Piece) -> int:
        return sum(row.count(piece) for row in self._grid)

    def rows_view(self) -> tuple[tuple[Piece, ...], ...]:
        """Read-only snapshot for renderers."""
        return tuple(tuple(row) for row in self._grid)

    # -- mutation ----------------------------------------------------------------
    def set(self, cell: Cell, piece: Piece) -> None:
        if not self.is_on_board(cell):
            raise IndexError(f"{cell} is off the board")
        self._grid[cell.row][cell.col] = piece

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Board) and self._grid == other._grid

    def __repr__(self) -> str:
        return f"Board({self.to_strings()!r})"
