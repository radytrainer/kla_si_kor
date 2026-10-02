"""Reusable UI widgets."""

from __future__ import annotations

from collections.abc import Callable
from functools import lru_cache

import pygame

import config
from ui.fonts import FontManager

BUTTON_BORDER_WIDTH = 2
BUTTON_HOVER_BORDER_WIDTH = 4


class Button:
    """A large rounded button that reacts to the pointer (mouse or gesture)."""

    # Called on every button press (the application plays the menu-click sound).
    on_any_click: Callable[[], None] | None = None

    def __init__(self, rect: pygame.Rect, label: Callable[[], str],
                 on_click: Callable[[], None]) -> None:
        # ``label`` is a callable so the text follows language changes.
        self.rect = rect
        self._label = label
        self._on_click = on_click
        self.hovered = False

    def update_hover(self, pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(pos)

    def try_click(self, pos: tuple[int, int]) -> bool:
        """Invoke the action if ``pos`` is inside; return whether it was."""
        if self.rect.collidepoint(pos):
            if Button.on_any_click is not None:
                Button.on_any_click()
            self._on_click()
            return True
        return False

    def draw(self, surface: pygame.Surface, fonts: FontManager) -> None:
        fill = config.COLOR_BUTTON_HOVER if self.hovered else config.COLOR_BUTTON
        border_color = config.COLOR_TIGER if self.hovered else config.COLOR_BUTTON_BORDER
        border = BUTTON_HOVER_BORDER_WIDTH if self.hovered else BUTTON_BORDER_WIDTH
        pygame.draw.rect(surface, fill, self.rect, border_radius=config.PANEL_RADIUS)
        pygame.draw.rect(surface, border_color, self.rect, width=border,
                         border_radius=config.PANEL_RADIUS)
        text = fonts.render(self._label(), config.FONT_SIZE_MEDIUM, config.COLOR_TEXT,
                            bold=True)
        surface.blit(text, text.get_rect(center=self.rect.center))


def vertical_button_stack(center_x: int, top: int, count: int) -> list[pygame.Rect]:
    """Return ``count`` button rects stacked vertically, centred on center_x."""
    step = config.BUTTON_HEIGHT + config.BUTTON_SPACING
    return [
        pygame.Rect(center_x - config.BUTTON_WIDTH // 2, top + index * step,
                    config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        for index in range(count)
    ]


def draw_panel(surface: pygame.Surface, rect: pygame.Rect) -> None:
    """Draw the standard rounded information panel."""
    pygame.draw.rect(surface, config.COLOR_PANEL, rect, border_radius=config.PANEL_RADIUS)
    pygame.draw.rect(surface, config.COLOR_PANEL_BORDER, rect, width=BUTTON_BORDER_WIDTH,
                     border_radius=config.PANEL_RADIUS)


@lru_cache(maxsize=2)
def _gradient(size: tuple[int, int]) -> pygame.Surface:
    width, height = size
    gradient = pygame.Surface(size)
    top, bottom = config.COLOR_BACKGROUND, config.COLOR_BACKGROUND_ACCENT
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
        pygame.draw.line(gradient, color, (0, y), (width, y))
    return gradient


def draw_background(surface: pygame.Surface) -> None:
    """Fill the screen with a subtle vertical gradient (cached per size)."""
    surface.blit(_gradient(surface.get_size()), (0, 0))
