"""Camera-preview decorations shared by screens that show players: zones and hand colours."""

from __future__ import annotations

import pygame

import config
from ui.fonts import FontManager
from ui.player_style import PLAYER_COLORS, UNASSIGNED_COLOR, side_key
from ui.text import Translator
from vision.pipeline import VisionResult
from vision.player_tracker import MIDLINE

DASH_LENGTH = 12
MIDLINE_WIDTH = 2
ZONE_LABEL_MARGIN = 8
ZONE_LABEL_ALPHA = 170
ZONE_LABEL_PADDING = (12, 4)


def hand_styles(result: VisionResult, tr: Translator) -> tuple[tuple[config.Color, str], ...]:
    """Colour and label for every detected hand, based on its player."""
    styles = [(UNASSIGNED_COLOR, tr("players.extra_hand"))] * len(result.hands)
    for player in result.players:
        if player.hand_index is not None:
            label = tr("players.tag", number=player.player_id,
                       side=tr(side_key(player.player_id)))
            styles[player.hand_index] = (PLAYER_COLORS[player.player_id], label)
    return tuple(styles)


def draw_player_zones(surface: pygame.Surface, image_rect: pygame.Rect, fonts: FontManager,
                      tr: Translator) -> None:
    """Dashed midline plus a label naming the player on each half (screen-side mode only)."""
    if config.PLAYER_ASSIGNMENT_MODE != config.PLAYER_ASSIGNMENT_SCREEN_SIDE:
        return
    mid_x = image_rect.left + round(image_rect.width * MIDLINE)
    for y in range(image_rect.top, image_rect.bottom, DASH_LENGTH * 2):
        pygame.draw.line(surface, config.COLOR_TEXT, (mid_x, y),
                         (mid_x, min(y + DASH_LENGTH, image_rect.bottom)), MIDLINE_WIDTH)
    left_player = 1 if config.PLAYER_1_CAMERA_SIDE == "LEFT" else 2
    for player_id, center_x in ((left_player, (image_rect.left + mid_x) // 2),
                                (3 - left_player, (mid_x + image_rect.right) // 2)):
        label = tr("players.zone", number=player_id, side=tr(side_key(player_id)))
        text = fonts.render(label, config.FONT_SIZE_SMALL, config.COLOR_TEXT, bold=True)
        box = text.get_rect(midtop=(center_x, image_rect.top + ZONE_LABEL_MARGIN))
        backdrop = box.inflate(*ZONE_LABEL_PADDING)
        background = pygame.Surface(backdrop.size, pygame.SRCALPHA)
        background.fill((*PLAYER_COLORS[player_id], ZONE_LABEL_ALPHA))
        surface.blit(background, backdrop)
        surface.blit(text, box)
