"""Piece types that can occupy a board cell."""

from __future__ import annotations

from enum import Enum


class Piece(Enum):
    """Content of a board cell."""

    EMPTY = "."
    TIGER = "T"
    COW = "C"
