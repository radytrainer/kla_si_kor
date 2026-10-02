"""Main menu screen."""

from __future__ import annotations

import pygame

import config
from ui.screen import ScreenId, UiContext, game_entry_screen
from ui.touchless_screen import TouchlessScreen
from ui.widgets import Button, draw_background, vertical_button_stack

MENU_TOP = 36
SUBTITLE_GAP = 6
BUTTONS_GAP = 30

# ScreenId.GAME stands for "start a game": the ready check (gesture) or the game (mouse).
MENU_ITEMS: tuple[tuple[str, ScreenId], ...] = (
    ("menu.start", ScreenId.GAME),
    ("menu.how_to_play", ScreenId.HOW_TO_PLAY),
    ("menu.calibrate", ScreenId.CALIBRATION),
    ("menu.settings", ScreenId.SETTINGS),
    ("menu.exit", ScreenId.EXIT),
)


class MainMenu(TouchlessScreen):
    """Title plus the START / HOW TO PLAY / CALIBRATE / SETTINGS / EXIT buttons."""

    def __init__(self, ctx: UiContext, pipeline) -> None:
        super().__init__(ctx, pipeline)
        self._buttons: list[Button] = []

    def _layout_buttons(self, surface: pygame.Surface, top: int) -> None:
        rects = vertical_button_stack(surface.get_width() // 2, top, len(MENU_ITEMS))
        self._buttons = [
            Button(rect, lambda key=key: self.ctx.tr(key),
                   lambda target=target: self.ctx.navigate(
                       game_entry_screen(self.ctx) if target is ScreenId.GAME else target))
            for rect, (key, target) in zip(rects, MENU_ITEMS)
        ]

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            button.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            if button.try_click(pos):
                return

    def on_back(self) -> None:
        self.ctx.navigate(ScreenId.EXIT)  # ESC key: the only shortcut that quits.

    def on_gesture_cancel(self) -> None:
        """A fist must never quit the game (a resting hand is often a fist)."""

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        y = self.draw_title_header(surface, MENU_TOP)
        subtitle = self.ctx.fonts.render(config.APP_SUBTITLE, config.FONT_SIZE_SMALL,
                                         config.COLOR_TEXT_MUTED)
        subtitle_rect = subtitle.get_rect(midtop=(surface.get_width() // 2, y + SUBTITLE_GAP))
        surface.blit(subtitle, subtitle_rect)
        if not self._buttons:
            self._layout_buttons(surface, subtitle_rect.bottom + BUTTONS_GAP)
        for button in self._buttons:
            button.draw(surface, self.ctx.fonts)
        self.draw_touch_cursor(surface)
