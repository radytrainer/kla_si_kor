"""Board cell coordinates and their human-readable names (A1 … D4)."""

from __future__ import annotations

from string import ascii_uppercase
from typing import NamedTuple


class Cell(NamedTuple):
    """A (row, col) position; row 0 is the top row, col 0 the left column."""

    row: int
    col: int

    @property
    def name(self) -> str:
        """Chess-style name: column letter + row number, e.g. (1, 1) -> "B2"."""
        return f"{column_letter(self.col)}{self.row + 1}"

    def offset(self, d_row: int, d_col: int) -> Cell:
        """Return the cell shifted by the given amounts (may be off-board)."""
        return Cell(self.row + d_row, self.col + d_col)


def column_letter(col: int) -> str:
    """Return the letter used to label a column (0 -> "A")."""
    return ascii_uppercase[col]
