"""Human-readable move-history text in the current language.

The game engine's ``MoveRecord.describe()`` is English-only (for logs and
tests); the UI uses these translated templates instead. The English templates
produce exactly the same text as ``describe()``.
"""

from __future__ import annotations

from game.state import MoveRecord
from ui.text import Translator


def describe_record(record: MoveRecord, tr: Translator) -> str:
    def name(cell) -> str:
        return cell.name if cell is not None else ""

    return tr(f"move.{record.kind.value}", side=tr(f"piece.{record.side.value}"),
              src=name(record.from_cell), to=name(record.to_cell),
              captured=name(record.captured))
