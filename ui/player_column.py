"""Camera column next to the board: live thumbnail + one card per player.

The thumbnail outlines the board region, so players see where to point. Hand
landmarks are only drawn in DEBUG mode (spec §20).
"""

from __future__ import annotations

import pygame

import config
from camera.camera import CameraStatus
from game.piece import Piece
from ui.camera_view import CameraView
from ui.cursor_renderer import PlayerCursor
from ui.fonts import FontManager
from ui.hand_overlay import HandOverlay, to_screen
from ui.piece_sprites import PieceSprites
from ui.player_style import PLAYER_COLORS, side_key
from ui.text import Translator
from ui.widgets import draw_panel
from vision.coordinate_mapper import BoardCoordinateMapper
from vision.pipeline import VisionResult

THUMB_ASPECT = 3 / 4
GAP = 12
CARD_PADDING = 8
ICON_SIZE = 40
REGION_LINE_WIDTH = 2
LINE_GAP = 2


class PlayerColumn:
    def __init__(self, fonts: FontManager, sprites: PieceSprites, tr: Translator) -> None:
        self._fonts = fonts
        self._sprites = sprites
        self._tr = tr
        self._view = CameraView(fonts)
        self._overlay = HandOverlay(fonts)

    def draw(self, surface: pygame.Surface, rect: pygame.Rect, result: VisionResult | None,
             camera_status: CameraStatus, cursors: dict[int, PlayerCursor],
             active_player: int, mapper: BoardCoordinateMapper, debug: bool,
             tracking_error: bool = False, computer_player: int | None = None) -> None:
        thumb = pygame.Rect(rect.left, rect.top, rect.width, round(rect.width * THUMB_ASPECT))
        frame = result.frame if result is not None else None
        border = config.COLOR_OK if camera_status is CameraStatus.RUNNING else config.COLOR_ERROR
        self._view.draw(surface, thumb, frame, self._tr(f"camera.status.{camera_status.value}"),
                        border)
        image = self._view.last_image_rect
        if image is not None:
            corners = [to_screen(x, y, image) for x, y in mapper.corners]
            pygame.draw.polygon(surface, config.COLOR_SELECTED, corners, REGION_LINE_WIDTH)
            if debug and result is not None:
                self._overlay.draw(surface, image, result.hands, show_labels=False)
        y = thumb.bottom + GAP
        warnings = []
        if tracking_error:  # MediaPipe failed: say so and point to the mouse fallback.
            warnings.append(self._tr("hands.error_use_mouse"))
        if frame is not None and frame.too_dark:
            warnings.append(self._tr("camera.too_dark"))
        for warning in warnings:
            for line in self._fonts.render_wrapped(warning, config.FONT_SIZE_SMALL,
                                                   config.COLOR_ERROR, rect.width):
                surface.blit(line, (rect.left, y))
                y += line.get_height()
            y += GAP
        card_height = (rect.bottom - y - GAP) // 2
        for player_id in (1, 2):
            card = pygame.Rect(rect.left, y, rect.width, card_height)
            self._draw_card(surface, card, player_id, cursors.get(player_id),
                            player_id == active_player, player_id == computer_player)
            y = card.bottom + GAP

    def _draw_card(self, surface: pygame.Surface, card: pygame.Rect, player_id: int,
                   cursor: PlayerCursor | None, active: bool, computer: bool = False) -> None:
        draw_panel(surface, card)
        color = PLAYER_COLORS[player_id]
        if active:
            pygame.draw.rect(surface, color, card, width=3, border_radius=config.PANEL_RADIUS)
        side = side_key(player_id)
        piece = Piece.TIGER if side == "side.tigers" else Piece.COW
        x, y = card.left + CARD_PADDING, card.top + CARD_PADDING
        surface.blit(self._sprites.get(piece, ICON_SIZE), (x, y))
        text_x = x + ICON_SIZE + CARD_PADDING
        y = self._line(surface, text_x, y, f"P{player_id}", color, bold=True)
        self._line(surface, text_x, y, self._tr(side), config.COLOR_TEXT_MUTED)
        y = card.top + CARD_PADDING + ICON_SIZE + CARD_PADDING
        state_key = "player.active" if active else "player.locked"
        y = self._line(surface, x, y, self._tr(state_key),
                       config.COLOR_OK if active else config.COLOR_LOCKED, bold=True)
        if computer:
            detail = self._tr("computer.thinking" if active else "computer.name")
            detail_color = config.COLOR_TEXT
        elif cursor is None:
            detail, detail_color = self._tr("players.status.ABSENT"), config.COLOR_WARNING
        elif not cursor.tracked:
            detail, detail_color = self._tr("cursor.lost"), config.COLOR_WARNING
        elif cursor.cell_name:
            detail, detail_color = self._tr("cursor.cell", cell=cursor.cell_name), config.COLOR_TEXT
        else:
            detail, detail_color = self._tr("cursor.off_board"), config.COLOR_TEXT_MUTED
        self._line(surface, x, y, detail, detail_color)

    def _line(self, surface: pygame.Surface, x: int, y: int, text: str, color: config.Color,
              bold: bool = False) -> int:
        rendered = self._fonts.render(text, config.FONT_SIZE_SMALL, color, bold=bold)
        surface.blit(rendered, (x, y))
        return y + rendered.get_height() + LINE_GAP
