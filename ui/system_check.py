"""System check screen, shown at start-up only when a dependency is missing."""

from __future__ import annotations

import pygame

import config
from app.diagnostics import DependencyStatus
from ui.screen import Screen, ScreenId, UiContext
from ui.widgets import Button, draw_background, draw_panel

TITLE_TOP = 40
PANEL_WIDTH = 560
PANEL_TOP = 130
PADDING = 24
ROW_HEIGHT = 40
DOT_RADIUS = 8
MESSAGE_GAP = 20


class SystemCheckScreen(Screen):
    """Lists every dependency with a green/red dot and a CONTINUE button."""

    def __init__(self, ctx: UiContext, statuses: list[DependencyStatus]) -> None:
        super().__init__(ctx)
        khmer = (DependencyStatus("Khmer font", True, "found") if ctx.fonts.khmer_available
                 else DependencyStatus("Khmer font", False, "add a Khmer .ttf to assets/fonts/"))
        self._rows = [*statuses, khmer]
        rect = pygame.Rect(0, 0, config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        rect.midbottom = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT - config.UI_MARGIN)
        self._continue = Button(rect, lambda: ctx.tr("common.continue"),
                                lambda: ctx.navigate(ScreenId.MENU))

    @property
    def all_ok(self) -> bool:
        return all(row.ok for row in self._rows)

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        self._continue.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        self._continue.try_click(pos)

    def on_back(self) -> None:
        self.ctx.navigate(ScreenId.EXIT)

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        fonts, tr = self.ctx.fonts, self.ctx.tr
        center_x = surface.get_width() // 2
        title = fonts.render(tr("system.title"), config.FONT_SIZE_TITLE, config.COLOR_TEXT,
                             bold=True)
        surface.blit(title, title.get_rect(midtop=(center_x, TITLE_TOP)))

        panel = pygame.Rect(0, PANEL_TOP, PANEL_WIDTH, 2 * PADDING + ROW_HEIGHT * len(self._rows))
        panel.centerx = center_x
        draw_panel(surface, panel)
        for index, row in enumerate(self._rows):
            y = panel.top + PADDING + ROW_HEIGHT * index + ROW_HEIGHT // 2
            dot_x = panel.left + PADDING + DOT_RADIUS
            pygame.draw.circle(surface, config.COLOR_OK if row.ok else config.COLOR_ERROR,
                               (dot_x, y), DOT_RADIUS)
            label = fonts.render(row.label, config.FONT_SIZE_MEDIUM, config.COLOR_TEXT)
            surface.blit(label, label.get_rect(midleft=(dot_x + 3 * DOT_RADIUS, y)))
            detail = fonts.render(row.detail, config.FONT_SIZE_SMALL,
                                  config.COLOR_TEXT_MUTED if row.ok else config.COLOR_ERROR)
            surface.blit(detail, detail.get_rect(midright=(panel.right - PADDING, y)))

        ok = self.all_ok
        message = fonts.render(tr("system.ok" if ok else "system.problem"),
                               config.FONT_SIZE_MEDIUM,
                               config.COLOR_OK if ok else config.COLOR_WARNING)
        surface.blit(message, message.get_rect(midtop=(center_x, panel.bottom + MESSAGE_GAP)))
        self._continue.draw(surface, fonts)
