"""SETTINGS screen: large buttons that cycle through values (pinch or click).

Every change is applied immediately and saved to data/settings.json.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pygame

import config
from app.settings import INPUT_MODES, LANGUAGES, PRESET_LEVELS, SIDES, Settings
from ui.screen import ScreenId, UiContext
from ui.text import Translator
from ui.touchless_screen import TouchlessScreen
from ui.widgets import Button, draw_background
from vision.pipeline import VisionPipeline

TITLE_TOP = 16
GRID_TOP = 110
COLUMN_WIDTH = 540
COLUMN_GAP = 40
ROW_HEIGHT = 56
ROW_GAP = 12
NOTE_GAP = 20
BOOLEAN_VALUES = (True, False)


@dataclass(frozen=True)
class Option:
    """One setting: which field, its possible values, and how to show a value."""

    label_key: str
    field: str
    values: tuple[Any, ...]
    describe: Callable[[Any, Translator], str]


def on_off(value: bool, tr: Translator) -> str:
    return tr("common.on" if value else "common.off")


OPTIONS: tuple[Option, ...] = (
    Option("settings.language", "language", LANGUAGES,
           lambda v, tr: tr(f"settings.language.{v}")),
    Option("settings.input", "input_mode", INPUT_MODES,
           lambda v, tr: tr(f"settings.input.{v}")),
    Option("settings.one_hand", "one_hand", BOOLEAN_VALUES, on_off),
    Option("settings.computer", "computer", config.COMPUTER_LEVELS,
           lambda v, tr: tr("common.off") if v == "OFF" else tr(f"settings.computer.{v}")),
    Option("settings.human_side", "human_side", SIDES,
           lambda v, tr: tr("side.tigers" if v == "TIGER" else "side.cows")),
    Option("settings.sound", "sound", BOOLEAN_VALUES, on_off),
    Option("settings.volume", "volume", config.VOLUME_STEPS,
           lambda v, tr: f"{round(v * 100)}%"),
    Option("settings.pinch", "pinch_sensitivity", PRESET_LEVELS,
           lambda v, tr: tr(f"settings.level.{v}")),
    Option("settings.smoothing", "cursor_smoothing", PRESET_LEVELS,
           lambda v, tr: tr(f"settings.level.{v}")),
    Option("settings.fullscreen", "fullscreen", BOOLEAN_VALUES, on_off),
    Option("settings.debug", "debug", BOOLEAN_VALUES, on_off),
    Option("settings.camera", "camera_index", config.CAMERA_INDEX_CHOICES,
           lambda v, tr: str(v)),
)


def next_value(values: tuple[Any, ...], current: Any) -> Any:
    """The value after ``current`` (wrapping). Numbers not in the list (e.g. a
    volume set in config.py) jump to the next listed value above them."""
    if current in values:
        return values[(values.index(current) + 1) % len(values)]
    if isinstance(current, (int, float)) and not isinstance(current, bool):
        higher = [value for value in values if value > current]
        return higher[0] if higher else values[0]
    return values[0]


class SettingsScreen(TouchlessScreen):
    def __init__(self, ctx: UiContext, pipeline: VisionPipeline,
                 get_settings: Callable[[], Settings],
                 apply_settings: Callable[[Settings], None]) -> None:
        super().__init__(ctx, pipeline)
        self._get = get_settings
        self._apply = apply_settings
        self._buttons: list[Button] = []
        rows = (len(OPTIONS) + 1) // 2
        left_x = (config.WINDOW_WIDTH - 2 * COLUMN_WIDTH - COLUMN_GAP) // 2
        for index, option in enumerate(OPTIONS):
            column, row = index // rows, index % rows
            rect = pygame.Rect(left_x + column * (COLUMN_WIDTH + COLUMN_GAP),
                               GRID_TOP + row * (ROW_HEIGHT + ROW_GAP), COLUMN_WIDTH, ROW_HEIGHT)
            self._buttons.append(Button(rect, lambda option=option: self._label(option),
                                        lambda option=option: self.cycle(option)))
        back = pygame.Rect(0, 0, config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        back.midbottom = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT - config.UI_MARGIN)
        self._buttons.append(Button(back, lambda: ctx.tr("common.back"),
                                    lambda: ctx.navigate(ScreenId.MENU)))

    def _label(self, option: Option) -> str:
        value = getattr(self._get(), option.field)
        return f"{self.ctx.tr(option.label_key)}: {option.describe(value, self.ctx.tr)}"

    def cycle(self, option: Option) -> None:
        """Advance one setting to its next value and apply it."""
        current = self._get()
        value = next_value(option.values, getattr(current, option.field))
        self._apply(current.with_changes(**{option.field: value}))

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            button.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            if button.try_click(pos):
                return

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        fonts, tr = self.ctx.fonts, self.ctx.tr
        center_x = surface.get_width() // 2
        title = fonts.render(tr("menu.settings"), config.FONT_SIZE_TITLE, config.COLOR_TIGER,
                             bold=True)
        surface.blit(title, title.get_rect(midtop=(center_x, TITLE_TOP)))
        for button in self._buttons:
            button.draw(surface, fonts)
        grid_bottom = max(button.rect.bottom for button in self._buttons[:-1])
        note = fonts.render(tr("settings.saved_note"), config.FONT_SIZE_SMALL,
                            config.COLOR_TEXT_MUTED)
        surface.blit(note, note.get_rect(midtop=(center_x, grid_bottom + NOTE_GAP)))
        self.draw_touch_cursor(surface)
