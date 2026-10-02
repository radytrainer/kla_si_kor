"""On-screen player cursors: 🔵 Player 1, 🟢 Player 2.

The player whose turn it is gets a bright cursor (with the pinch-progress
ring); the other player's cursor is grey with a padlock, so everyone can see
whose hand is being tracked and who may act.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

import config
from ui.fonts import FontManager
from ui.gesture_overlay import CURSOR_RADIUS, draw_cursor
from ui.player_style import PLAYER_COLORS
from vision.gesture_detector import GestureState

LOCKED_ALPHA = 150
LOST_RING_WIDTH = 3
LABEL_OFFSET = (CURSOR_RADIUS + 6, -CURSOR_RADIUS - 26)
LABEL_PADDING = (8, 2)
LOCK_BODY = (14, 11)
LOCK_SHACKLE_RADIUS = 5
WHITE = (255, 255, 255)


@dataclass(frozen=True)
class PlayerCursor:
    """Everything needed to draw one player's cursor this frame."""

    player_id: int
    position: tuple[int, int]  # Screen pixels.
    cell: tuple[int, int] | None  # (row, col) under the fingertip, None when off the board.
    cell_name: str | None  # e.g. "B3".
    active: bool  # It is this player's turn.
    tracked: bool  # False while the hand is briefly lost.
    gesture: GestureState


def draw_padlock(surface: pygame.Surface, center: tuple[int, int], color: config.Color) -> None:
    body = pygame.Rect(0, 0, *LOCK_BODY)
    body.midtop = (center[0], center[1] - 1)
    shackle = pygame.Rect(0, 0, LOCK_SHACKLE_RADIUS * 2, LOCK_SHACKLE_RADIUS * 2)
    shackle.midbottom = (center[0], body.top + LOCK_SHACKLE_RADIUS)
    pygame.draw.arc(surface, color, shackle, 0, 3.1416, 2)
    pygame.draw.rect(surface, color, body, border_radius=2)


class CursorRenderer:
    def __init__(self, fonts: FontManager) -> None:
        self._fonts = fonts

    def draw(self, surface: pygame.Surface, cursor: PlayerCursor, label: str) -> None:
        color = PLAYER_COLORS[cursor.player_id]
        if not cursor.tracked:
            pygame.draw.circle(surface, config.COLOR_LOCKED, cursor.position, CURSOR_RADIUS,
                               LOST_RING_WIDTH)
        elif cursor.active:
            draw_cursor(surface, cursor.position, cursor.gesture, color)
        else:
            self._draw_locked(surface, cursor.position)
        self._draw_label(surface, cursor, label, color if cursor.active else config.COLOR_LOCKED)

    def _draw_locked(self, surface: pygame.Surface, position: tuple[int, int]) -> None:
        size = CURSOR_RADIUS * 2 + 4
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        center = (size // 2, size // 2)
        pygame.draw.circle(layer, WHITE, center, CURSOR_RADIUS + 2)
        pygame.draw.circle(layer, config.COLOR_LOCKED, center, CURSOR_RADIUS)
        draw_padlock(layer, center, config.COLOR_BACKGROUND)
        layer.set_alpha(LOCKED_ALPHA)
        surface.blit(layer, layer.get_rect(center=position))

    def _draw_label(self, surface: pygame.Surface, cursor: PlayerCursor, text: str,
                    color: config.Color) -> None:
        rendered = self._fonts.render(text, config.FONT_SIZE_SMALL, WHITE, bold=True)
        box = rendered.get_rect(topleft=(cursor.position[0] + LABEL_OFFSET[0],
                                         cursor.position[1] + LABEL_OFFSET[1]))
        box = box.inflate(LABEL_PADDING[0] * 2, LABEL_PADDING[1] * 2)
        box.clamp_ip(surface.get_rect())
        pygame.draw.rect(surface, color, box, border_radius=box.height // 2)
        surface.blit(rendered, rendered.get_rect(center=box.center))
