"""Draws detected hands (skeleton, fingertips, bounding box, label) over the camera image."""

from __future__ import annotations

import pygame

import config
from ui.fonts import FontManager
from vision import landmarks as lm
from vision.hand_detector import Hand

HAND_COLORS: tuple[config.Color, ...] = (config.COLOR_PLAYER_1_CURSOR,
                                         config.COLOR_PLAYER_2_CURSOR)
SKELETON_WIDTH = 3
JOINT_RADIUS = 4
FINGERTIP_RADIUS = 7
INDEX_TIP_RADIUS = 11
BOX_WIDTH = 2
BOX_MARGIN = 10
LABEL_GAP = 4
WHITE = (255, 255, 255)


def to_screen(x: float, y: float, image_rect: pygame.Rect) -> tuple[int, int]:
    """Map normalised image coordinates to a pixel inside ``image_rect``."""
    return (image_rect.left + round(x * image_rect.width),
            image_rect.top + round(y * image_rect.height))


class HandOverlay:
    """Renders hands on top of a camera image drawn at ``image_rect``."""

    def __init__(self, fonts: FontManager) -> None:
        self._fonts = fonts

    def draw(self, surface: pygame.Surface, image_rect: pygame.Rect,
             hands: tuple[Hand, ...],
             styles: tuple[tuple[config.Color, str], ...] | None = None,
             show_labels: bool = True) -> None:
        """Draw hands; ``styles`` gives (colour, label) per hand, default by order."""
        previous_clip = surface.get_clip()
        surface.set_clip(image_rect)
        for number, hand in enumerate(hands):
            if styles is not None:
                color, label = styles[number]
            else:
                color = HAND_COLORS[number % len(HAND_COLORS)]
                label = f"{number + 1}: {hand.handedness}"
            self._draw_hand(surface, image_rect, hand, color, label if show_labels else None)
        surface.set_clip(previous_clip)

    def _draw_hand(self, surface: pygame.Surface, image_rect: pygame.Rect, hand: Hand,
                   color: config.Color, label: str | None) -> None:
        points = [to_screen(p.x, p.y, image_rect) for p in hand.landmarks]
        for start, end in lm.HAND_CONNECTIONS:
            pygame.draw.line(surface, color, points[start], points[end], SKELETON_WIDTH)
        for index, point in enumerate(points):
            radius = FINGERTIP_RADIUS if index in lm.FINGERTIPS else JOINT_RADIUS
            pygame.draw.circle(surface, WHITE, point, radius)
            pygame.draw.circle(surface, color, point, radius, 2)
        # The index fingertip becomes the cursor later, so make it stand out.
        pygame.draw.circle(surface, color, points[lm.INDEX_TIP], INDEX_TIP_RADIUS, 3)

        box = hand.bounding_box
        top_left = to_screen(box.left, box.top, image_rect)
        bottom_right = to_screen(box.right, box.bottom, image_rect)
        size = (bottom_right[0] - top_left[0], bottom_right[1] - top_left[1])
        rect = pygame.Rect(top_left, size).inflate(BOX_MARGIN * 2, BOX_MARGIN * 2)
        pygame.draw.rect(surface, color, rect, BOX_WIDTH)
        if label is None:
            return
        text = self._fonts.render(f"{label} {hand.confidence:.0%}", config.FONT_SIZE_SMALL,
                                  WHITE, bold=True)
        background = text.get_rect(bottomleft=(rect.left, rect.top - LABEL_GAP)).inflate(8, 2)
        pygame.draw.rect(surface, color, background)
        surface.blit(text, text.get_rect(center=background.center))
