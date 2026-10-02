"""Draws camera frames (NumPy BGR images) into a Pygame rectangle."""

from __future__ import annotations

import numpy as np
import pygame

import config
from camera.camera import Frame
from ui.fonts import FontManager

BORDER_WIDTH = 3
PLACEHOLDER_COLOR = (8, 12, 20)


def frame_to_surface(image: np.ndarray) -> pygame.Surface:
    """Convert an OpenCV BGR image to a Pygame surface (no OpenCV needed)."""
    height, width = image.shape[:2]
    rgb = np.ascontiguousarray(image[:, :, ::-1])
    return pygame.image.frombuffer(rgb.tobytes(), (width, height), "RGB")


def fit_rect(size: tuple[int, int], area: pygame.Rect) -> pygame.Rect:
    """Largest rect with the aspect ratio of ``size`` centred inside ``area``."""
    width, height = size
    scale = min(area.width / width, area.height / height)
    rect = pygame.Rect(0, 0, round(width * scale), round(height * scale))
    rect.center = area.center
    return rect


class CameraView:
    """Renders the latest frame, or a placeholder message when there is none."""

    def __init__(self, fonts: FontManager) -> None:
        self._fonts = fonts
        self.last_image_rect: pygame.Rect | None = None  # Where the image was drawn.

    def draw(self, surface: pygame.Surface, area: pygame.Rect, frame: Frame | None,
             placeholder_text: str, border_color: config.Color) -> None:
        if frame is None:
            self.last_image_rect = None
            pygame.draw.rect(surface, PLACEHOLDER_COLOR, area, border_radius=config.PANEL_RADIUS)
            pygame.draw.rect(surface, border_color, area, width=BORDER_WIDTH,
                             border_radius=config.PANEL_RADIUS)
            text = self._fonts.render(placeholder_text, config.FONT_SIZE_MEDIUM,
                                      config.COLOR_TEXT_MUTED)
            surface.blit(text, text.get_rect(center=area.center))
            return
        image_rect = fit_rect(frame.size, area)
        image = frame_to_surface(frame.image)
        if image_rect.size != frame.size:
            image = pygame.transform.smoothscale(image, image_rect.size)
        surface.blit(image, image_rect)
        pygame.draw.rect(surface, border_color, image_rect, width=BORDER_WIDTH)
        self.last_image_rect = image_rect
