"""Tiger and Cow sprites.

If ``assets/tiger.png`` / ``assets/cow.png`` exist they are used; otherwise the
pieces are drawn procedurally (so the game never depends on image files).
Procedural sprites are drawn at SUPERSAMPLE× size and scaled down for smooth
anti-aliased edges. All shape coordinates are fractions of the sprite size.
"""

from __future__ import annotations

from pathlib import Path

import pygame

import config
from game.piece import Piece

SUPERSAMPLE = 3
OUTLINE = (40, 26, 16)
TIGER_STRIPE = (30, 20, 12)
WHITE = (250, 248, 240)
PINK = (240, 160, 170)
HORN = (236, 222, 180)
COW_PATCH = (38, 38, 44)
COW_EAR = (214, 196, 190)
SHADOW = (0, 0, 0, 70)

Box = tuple[float, float, float, float]  # x, y, w, h as fractions of size


def _load_image(path: Path, size: int) -> pygame.Surface | None:
    """Load and scale an optional image; return None if missing or broken."""
    if not path.is_file():
        return None
    try:
        image = pygame.image.load(str(path)).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return None
    return pygame.transform.smoothscale(image, (size, size))


class _Canvas:
    """Helper for drawing shapes with fractional coordinates."""

    def __init__(self, size: int) -> None:
        self.size = size
        self.surface = pygame.Surface((size, size), pygame.SRCALPHA)

    def _px(self, value: float) -> int:
        return round(value * self.size)

    def _point(self, point: tuple[float, float]) -> tuple[int, int]:
        return self._px(point[0]), self._px(point[1])

    def _rect(self, box: Box) -> pygame.Rect:
        return pygame.Rect(*(self._px(value) for value in box))

    def circle(self, color, center: tuple[float, float], radius: float,
               width: float = 0) -> None:
        pygame.draw.circle(self.surface, color, self._point(center), self._px(radius),
                           self._px(width))

    def ellipse(self, color, box: Box, width: float = 0) -> None:
        pygame.draw.ellipse(self.surface, color, self._rect(box), self._px(width))

    def polygon(self, color, points: list[tuple[float, float]], width: float = 0) -> None:
        pygame.draw.polygon(self.surface, color, [self._point(p) for p in points],
                            self._px(width))

    def line(self, color, start: tuple[float, float], end: tuple[float, float],
             width: float) -> None:
        pygame.draw.line(self.surface, color, self._point(start), self._point(end),
                         max(1, self._px(width)))

    def finish(self, size: int) -> pygame.Surface:
        return pygame.transform.smoothscale(self.surface, (size, size))


def _mirror_x(point: tuple[float, float]) -> tuple[float, float]:
    return 1.0 - point[0], point[1]


def _draw_tiger(size: int) -> pygame.Surface:
    c = _Canvas(size * SUPERSAMPLE)
    orange, outline = config.COLOR_TIGER, 0.02
    c.ellipse(SHADOW, (0.16, 0.82, 0.68, 0.12))
    for x in (0.24, 0.76):  # Ears.
        c.circle(orange, (x, 0.24), 0.12)
        c.circle(OUTLINE, (x, 0.24), 0.12, outline)
        c.circle(OUTLINE, (x, 0.25), 0.055)
    c.circle(orange, (0.5, 0.53), 0.35)
    c.circle(OUTLINE, (0.5, 0.53), 0.35, outline)
    for start, end in (((0.5, 0.2), (0.5, 0.33)), ((0.41, 0.22), (0.44, 0.32)),
                       ((0.59, 0.22), (0.56, 0.32))):  # Forehead stripes.
        c.line(TIGER_STRIPE, start, end, 0.03)
    for start, end in (((0.16, 0.48), (0.29, 0.52)), ((0.16, 0.6), (0.29, 0.6)),
                       ((0.19, 0.71), (0.3, 0.67))):  # Cheek stripes, both sides.
        c.line(TIGER_STRIPE, start, end, 0.03)
        c.line(TIGER_STRIPE, _mirror_x(start), _mirror_x(end), 0.03)
    c.ellipse(WHITE, (0.3, 0.56, 0.4, 0.26))
    for x in (0.38, 0.62):  # Eyes.
        c.circle(OUTLINE, (x, 0.45), 0.045)
        c.circle(WHITE, (x + 0.015, 0.435), 0.014)
    c.polygon(PINK, [(0.45, 0.6), (0.55, 0.6), (0.5, 0.66)])
    c.polygon(OUTLINE, [(0.45, 0.6), (0.55, 0.6), (0.5, 0.66)], 0.01)
    c.line(OUTLINE, (0.5, 0.66), (0.5, 0.71), 0.015)
    c.line(OUTLINE, (0.5, 0.71), (0.43, 0.74), 0.015)
    c.line(OUTLINE, (0.5, 0.71), (0.57, 0.74), 0.015)
    return c.finish(size)


def _draw_cow(size: int) -> pygame.Surface:
    c = _Canvas(size * SUPERSAMPLE)
    outline = 0.02
    c.ellipse(SHADOW, (0.16, 0.84, 0.68, 0.11))
    left_horn = [(0.3, 0.26), (0.2, 0.08), (0.12, 0.1), (0.24, 0.3)]
    for horn in (left_horn, [_mirror_x(p) for p in left_horn]):
        c.polygon(HORN, horn)
        c.polygon(OUTLINE, horn, 0.012)
    for box in ((0.04, 0.3, 0.24, 0.13), (0.72, 0.3, 0.24, 0.13)):  # Ears.
        c.ellipse(COW_EAR, box)
        c.ellipse(OUTLINE, box, 0.012)
    head = (0.2, 0.18, 0.6, 0.68)
    c.ellipse(WHITE, head)
    c.ellipse(COW_PATCH, (0.48, 0.2, 0.26, 0.2))
    c.ellipse(COW_PATCH, (0.25, 0.32, 0.2, 0.2))
    c.ellipse(OUTLINE, head, outline)
    for x in (0.37, 0.63):  # Eyes.
        c.circle(OUTLINE, (x, 0.44), 0.045)
        c.circle(WHITE, (x + 0.015, 0.425), 0.014)
    muzzle = (0.27, 0.58, 0.46, 0.27)
    c.ellipse(PINK, muzzle)
    c.ellipse(OUTLINE, muzzle, 0.012)
    for x in (0.38, 0.56):  # Nostrils.
        c.ellipse(OUTLINE, (x, 0.67, 0.06, 0.08))
    return c.finish(size)


class PieceSprites:
    """Creates and caches piece images for a given size."""

    def __init__(self) -> None:
        self._cache: dict[tuple[Piece, int], pygame.Surface] = {}

    def get(self, piece: Piece, size: int) -> pygame.Surface | None:
        """Return the sprite for a piece (None for an empty cell)."""
        if piece is Piece.EMPTY:
            return None
        key = (piece, size)
        if key not in self._cache:
            self._cache[key] = self._create(piece, size)
        return self._cache[key]

    @staticmethod
    def _create(piece: Piece, size: int) -> pygame.Surface:
        if piece is Piece.TIGER:
            return _load_image(config.TIGER_IMAGE_FILE, size) or _draw_tiger(size)
        return _load_image(config.COW_IMAGE_FILE, size) or _draw_cow(size)
