"""Draws the 4×4 board from a read-only view model (no game rules here)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pygame

import config
from game.cell import Cell, column_letter
from game.piece import Piece
from ui.fonts import FontManager
from ui.animations import SpriteFrame
from ui.piece_sprites import PieceSprites

PIECE_SCALE = 0.84  # Sprite size relative to the cell.
GRID_LINE_WIDTH = 2
SELECTED_BORDER_WIDTH = 6
LEGAL_DOT_RATIO = 0.14  # Legal-move dot radius relative to the cell.
LEGAL_RING_WIDTH = 5
LEGAL_DOT_ALPHA = 150
FRAME_RADIUS = 18


@dataclass(frozen=True)
class BoardView:
    """Everything the renderer needs to draw one frame of the board."""

    pieces: Sequence[Sequence[Piece]]
    hover: Cell | None = None
    selected: Cell | None = None
    legal_targets: frozenset[Cell] = field(default_factory=frozenset)
    hidden: frozenset[Cell] = field(default_factory=frozenset)  # Drawn by an animation.
    selected_scale: float = 1.0  # Pulse applied to the selected piece.


class BoardRenderer:
    """Renders the board inside a square rect and hit-tests pointer positions."""

    def __init__(self, fonts: FontManager, sprites: PieceSprites) -> None:
        self._fonts = fonts
        self._sprites = sprites

    # -- geometry ----------------------------------------------------------
    @staticmethod
    def grid_rect(board_rect: pygame.Rect) -> pygame.Rect:
        """The playable grid inside the frame (the frame holds the labels)."""
        return board_rect.inflate(-2 * config.BOARD_FRAME_WIDTH, -2 * config.BOARD_FRAME_WIDTH)

    @classmethod
    def cell_size(cls, board_rect: pygame.Rect) -> int:
        return cls.grid_rect(board_rect).width // config.BOARD_COLS

    @classmethod
    def cell_rect(cls, board_rect: pygame.Rect, cell: Cell) -> pygame.Rect:
        grid = cls.grid_rect(board_rect)
        size = cls.cell_size(board_rect)
        return pygame.Rect(grid.left + cell.col * size, grid.top + cell.row * size, size, size)

    @classmethod
    def cell_at(cls, board_rect: pygame.Rect, pos: tuple[int, int]) -> Cell | None:
        """Return the cell under a screen position, or None if outside the grid."""
        grid = cls.grid_rect(board_rect)
        size = cls.cell_size(board_rect)
        col = (pos[0] - grid.left) // size
        row = (pos[1] - grid.top) // size
        if 0 <= row < config.BOARD_ROWS and 0 <= col < config.BOARD_COLS:
            return Cell(row, col)
        return None

    # -- drawing -----------------------------------------------------------
    def draw(self, surface: pygame.Surface, board_rect: pygame.Rect, view: BoardView) -> None:
        pygame.draw.rect(surface, config.COLOR_BOARD_FRAME, board_rect,
                         border_radius=FRAME_RADIUS)
        self._draw_labels(surface, board_rect)
        for row in range(config.BOARD_ROWS):
            for col in range(config.BOARD_COLS):
                self._draw_cell(surface, board_rect, Cell(row, col), view)
        pygame.draw.rect(surface, config.COLOR_BOARD_FRAME, self.grid_rect(board_rect),
                         width=GRID_LINE_WIDTH)

    def _draw_labels(self, surface: pygame.Surface, board_rect: pygame.Rect) -> None:
        half_frame = config.BOARD_FRAME_WIDTH // 2
        for col in range(config.BOARD_COLS):
            rect = self.cell_rect(board_rect, Cell(0, col))
            text = self._fonts.render(column_letter(col), config.FONT_SIZE_SMALL,
                                      config.COLOR_BOARD_LABEL, bold=True)
            surface.blit(text, text.get_rect(center=(rect.centerx, board_rect.top + half_frame)))
        for row in range(config.BOARD_ROWS):
            rect = self.cell_rect(board_rect, Cell(row, 0))
            text = self._fonts.render(str(row + 1), config.FONT_SIZE_SMALL,
                                      config.COLOR_BOARD_LABEL, bold=True)
            surface.blit(text, text.get_rect(center=(board_rect.left + half_frame, rect.centery)))

    def _draw_cell(self, surface: pygame.Surface, board_rect: pygame.Rect, cell: Cell,
                   view: BoardView) -> None:
        rect = self.cell_rect(board_rect, cell)
        is_light = (cell.row + cell.col) % 2 == 0
        pygame.draw.rect(surface, config.COLOR_CELL_LIGHT if is_light else config.COLOR_CELL_DARK,
                         rect)
        pygame.draw.rect(surface, config.COLOR_BOARD_FRAME, rect, width=GRID_LINE_WIDTH)

        if cell == view.hover:
            overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
            overlay.fill((*config.COLOR_HOVER, config.HOVER_ALPHA))
            surface.blit(overlay, rect)

        piece = view.pieces[cell.row][cell.col]
        scale = view.selected_scale if cell == view.selected else 1.0
        if cell not in view.hidden:
            self._blit_piece(surface, piece, rect.width, rect.center, scale)

        if cell in view.legal_targets:
            self._draw_legal_marker(surface, rect, occupied=piece is not Piece.EMPTY)
        if cell == view.selected:
            pygame.draw.rect(surface, config.COLOR_SELECTED, rect.inflate(-4, -4),
                             width=SELECTED_BORDER_WIDTH, border_radius=FRAME_RADIUS // 2)

    def draw_sprite_frame(self, surface: pygame.Surface, board_rect: pygame.Rect,
                          frame: SpriteFrame) -> None:
        """Draw an animated piece at a fractional cell position."""
        size = self.cell_size(board_rect)
        grid = self.grid_rect(board_rect)
        center = (round(grid.left + (frame.col + 0.5) * size),
                  round(grid.top + (frame.row + 0.5 - frame.lift) * size))
        self._blit_piece(surface, frame.piece, size, center, frame.scale, frame.alpha)

    def _blit_piece(self, surface: pygame.Surface, piece: Piece, cell_size: int,
                    center: tuple[int, int], scale: float = 1.0, alpha: int = 255) -> None:
        """Draw a piece; animated sizes scale the cached full-size sprite (cheap)
        instead of rendering a new procedural sprite for every size."""
        sprite = self._sprites.get(piece, round(cell_size * PIECE_SCALE))
        if sprite is None:
            return
        if scale != 1.0:
            side = max(1, round(sprite.get_width() * scale))
            sprite = pygame.transform.smoothscale(sprite, (side, side))
        if alpha < 255:
            sprite = sprite.copy() if scale == 1.0 else sprite
            sprite.set_alpha(alpha)
        surface.blit(sprite, sprite.get_rect(center=center))

    @classmethod
    def draw_cell_flash(cls, surface: pygame.Surface, board_rect: pygame.Rect, cell: Cell,
                        color: config.Color, alpha: int) -> None:
        """Tint one cell (used to confirm or reject a gesture on that cell)."""
        rect = cls.cell_rect(board_rect, cell)
        overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
        overlay.fill((*color, alpha))
        surface.blit(overlay, rect)

    @staticmethod
    def _draw_legal_marker(surface: pygame.Surface, rect: pygame.Rect, occupied: bool) -> None:
        marker = pygame.Surface(rect.size, pygame.SRCALPHA)
        center = (rect.width // 2, rect.height // 2)
        color = (*config.COLOR_LEGAL_MOVE, LEGAL_DOT_ALPHA)
        if occupied:  # Ring around a piece (e.g. a cow that can be captured).
            pygame.draw.circle(marker, color, center, rect.width // 2 - LEGAL_RING_WIDTH,
                               LEGAL_RING_WIDTH)
        else:
            pygame.draw.circle(marker, color, center, round(rect.width * LEGAL_DOT_RATIO))
        surface.blit(marker, rect)
