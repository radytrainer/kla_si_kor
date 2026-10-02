"""Player settings: defaults from config.py, saved to data/settings.json.

Every field is validated on load; a missing or invalid value falls back to its
default individually, so a hand-edited or old file never stops the game.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any

import config

PRESET_LEVELS: tuple[str, ...] = ("LOW", "NORMAL", "HIGH")
LANGUAGES: tuple[str, ...] = (config.LANGUAGE_EN, config.LANGUAGE_KM)
INPUT_MODES: tuple[str, ...] = (config.INPUT_MODE_GESTURE, config.INPUT_MODE_MOUSE)
SIDES: tuple[str, ...] = ("COW", "TIGER")
SETTINGS_VERSION = 1


@dataclass(frozen=True)
class Settings:
    sound: bool = config.SOUND_ENABLED
    volume: float = config.SOUND_VOLUME
    language: str = config.LANGUAGE
    input_mode: str = config.INPUT_MODE
    one_hand: bool = config.ONE_HAND_MODE
    computer: str = config.COMPUTER_LEVEL
    human_side: str = config.HUMAN_SIDE
    pinch_sensitivity: str = "NORMAL"
    cursor_smoothing: str = "NORMAL"
    fullscreen: bool = config.FULLSCREEN
    debug: bool = config.DEBUG_MODE
    camera_index: int = config.CAMERA_INDEX

    @property
    def pinch_thresholds(self) -> tuple[float, float]:
        return config.PINCH_SENSITIVITY_PRESETS[self.pinch_sensitivity]

    @property
    def smoothing_value(self) -> float:
        return config.CURSOR_SMOOTHING_PRESETS[self.cursor_smoothing]

    def with_changes(self, **changes: Any) -> Settings:
        return replace(self, **changes)


def _valid(name: str, value: Any) -> bool:
    """Is ``value`` acceptable for the field ``name``?"""
    if name in ("sound", "fullscreen", "debug", "one_hand"):
        return isinstance(value, bool)
    if name == "volume":
        return isinstance(value, (int, float)) and not isinstance(value, bool) \
            and 0.0 <= value <= 1.0
    if name == "language":
        return value in LANGUAGES
    if name == "input_mode":
        return value in INPUT_MODES
    if name == "computer":
        return value in config.COMPUTER_LEVELS
    if name == "human_side":
        return value in SIDES
    if name in ("pinch_sensitivity", "cursor_smoothing"):
        return value in PRESET_LEVELS
    if name == "camera_index":
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9
    return False


def load_settings(path: Path = config.SETTINGS_FILE) -> Settings:
    """Read settings; anything missing or invalid keeps its default."""
    defaults = Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaults
    if not isinstance(data, dict):
        return defaults
    values = {field.name: data[field.name] for field in fields(Settings)
              if field.name in data and _valid(field.name, data[field.name])}
    return replace(defaults, **values)


def save_settings(settings: Settings, path: Path = config.SETTINGS_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": SETTINGS_VERSION, **asdict(settings)}
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)  # Atomic: a crash never leaves a half-written file.
