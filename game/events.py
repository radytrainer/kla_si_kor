"""Input events consumed by the game engine.

Every input source (mouse, hand gestures, tests) produces the same
:class:`GameEvent`, so the engine never knows where input came from::

    {"player": 1, "action": "SELECT", "cell": [2, 3]}
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from game.cell import Cell


class Action(Enum):
    SELECT = "SELECT"  # Point + pinch / click on a cell: select, place, move or confirm.
    CANCEL = "CANCEL"  # Fist: clear the current selection.


@dataclass(frozen=True)
class GameEvent:
    player: int
    action: Action
    cell: Cell | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameEvent:
        """Build an event from the dictionary format shown in the module docstring."""
        raw_cell = data.get("cell")
        cell = Cell(int(raw_cell[0]), int(raw_cell[1])) if raw_cell is not None else None
        return cls(int(data["player"]), Action(data["action"]), cell)

    def to_dict(self) -> dict[str, Any]:
        return {
            "player": self.player,
            "action": self.action.value,
            "cell": [self.cell.row, self.cell.col] if self.cell is not None else None,
        }
