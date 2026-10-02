"""Short-lived feedback message ("Cow placed at B2", "Tiger cannot move diagonally")."""

from __future__ import annotations

import pygame

import config
from ui.fonts import FontManager

PADDING_X = 20
PADDING_Y = 8
MAX_ALPHA = 255


class Toast:
    """One message at a time, shown for TOAST_DURATION then faded out."""

    def __init__(self) -> None:
        self.text = ""
        self.color: config.Color = config.COLOR_TEXT
        self._remaining = 0.0

    @property
    def visible(self) -> bool:
        return self._remaining > 0.0 and bool(self.text)

    def show(self, text: str, color: config.Color) -> None:
        self.text = text
        self.color = color
        self._remaining = config.TOAST_DURATION

    def clear(self) -> None:
        self._remaining = 0.0

    def update(self, dt: float) -> None:
        self._remaining = max(0.0, self._remaining - dt)

    def draw(self, surface: pygame.Surface, fonts: FontManager,
             center: tuple[int, int]) -> None:
        """Draw as a pill centred on ``center``."""
        if not self.visible:
            return
        text = fonts.render(self.text, config.FONT_SIZE_SMALL, config.COLOR_TEXT, bold=True)
        pill = text.get_rect().inflate(2 * PADDING_X, 2 * PADDING_Y)
        pill.center = center
        layer = pygame.Surface(pill.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, (*config.COLOR_BACKGROUND, 230), layer.get_rect(),
                         border_radius=pill.height // 2)
        pygame.draw.rect(layer, self.color, layer.get_rect(), width=3,
                         border_radius=pill.height // 2)
        layer.blit(text, text.get_rect(center=layer.get_rect().center))
        fade = min(1.0, self._remaining / config.TOAST_FADE_TIME)
        layer.set_alpha(round(MAX_ALPHA * fade))
        surface.blit(layer, pill)
