"""Two-player ready check before a gesture-controlled game (spec §24).

Both players see themselves in the camera preview with their zones. Each
player pinches once to confirm READY; when both are ready a 3-2-1 countdown
and "GAME START!" lead into the game. A fist returns to the menu. A mouse
click (fallback) marks both players ready, and so does one pinch in one-hand
play, where a single player controls both sides.
"""

from __future__ import annotations

import math

import pygame

import config
from game.piece import Piece
from ui.camera_view import CameraView
from ui.hand_overlay import HandOverlay
from ui.player_style import PLAYER_COLORS, side_key
from ui.player_view import draw_player_zones, hand_styles
from ui.screen import ScreenId, UiContext
from ui.touchless_screen import TouchlessScreen
from ui.widgets import draw_background, draw_panel
from vision.pipeline import VisionPipeline, VisionResult
from vision.player_tracker import TrackStatus

TITLE_TOP = 16
PREVIEW = pygame.Rect(config.UI_MARGIN, 90, 640, 480)
CARD_WIDTH = 520
CARD_HEIGHT = 200
CARD_GAP = 24
CARD_PADDING = 18
ICON_SIZE = 96
HINT_BOTTOM_GAP = 30
OVERLAY_ALPHA = 170
PLAYER_IDS = (1, 2)


class ReadyScreen(TouchlessScreen):
    def __init__(self, ctx: UiContext, pipeline: VisionPipeline) -> None:
        super().__init__(ctx, pipeline)
        self.accept_multiple_gestures = True  # Both players may pinch in the same frame.
        self.ready: set[int] = set()
        self._countdown: float | None = None  # Seconds left once both are ready.
        self._view = CameraView(ctx.fonts)
        self._overlay = HandOverlay(ctx.fonts)

    @property
    def counting_down(self) -> bool:
        return self._countdown is not None

    def on_enter(self) -> None:
        super().on_enter()
        self.ready.clear()
        self._countdown = None

    def on_gesture_select(self, player_id: int, pos: tuple[int, int]) -> None:
        self._mark_ready(set(PLAYER_IDS) if self.ctx.solo else {player_id})

    def on_select(self, pos: tuple[int, int]) -> None:
        self._mark_ready(set(PLAYER_IDS))  # Mouse fallback: one click starts.

    def _mark_ready(self, players: set[int]) -> None:
        if self.counting_down:
            return
        self.ready |= players
        if self.ready >= set(PLAYER_IDS):
            self._countdown = config.READY_COUNTDOWN_SECONDS + config.GAME_START_BANNER_TIME

    def update(self, dt: float) -> None:
        super().update(dt)
        if self._countdown is not None:
            self._countdown -= dt
            if self._countdown <= 0:
                self.ctx.navigate(ScreenId.GAME)

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        tr, fonts = self.ctx.tr, self.ctx.fonts
        title = fonts.render(tr("ready.title"), config.FONT_SIZE_TITLE, config.COLOR_TIGER,
                             bold=True)
        surface.blit(title, title.get_rect(midtop=(surface.get_width() // 2, TITLE_TOP)))
        result = self._pipeline.latest_result()
        camera = self._pipeline.camera
        frame = result.frame if result is not None else camera.latest_frame()
        self._view.draw(surface, PREVIEW, frame, tr(f"camera.status.{camera.status.value}"),
                        config.COLOR_PANEL_BORDER)
        image = self._view.last_image_rect
        if image is not None:
            if not self.ctx.solo:  # One person may stand anywhere in the picture.
                draw_player_zones(surface, image, fonts, tr)
            if result is not None:
                self._overlay.draw(surface, image, result.hands, hand_styles(result, tr))
        cards_left = PREVIEW.right + config.UI_MARGIN
        y = PREVIEW.top
        for player_id in PLAYER_IDS:
            status = self._status(result, player_id)
            self._draw_card(surface, pygame.Rect(cards_left, y, CARD_WIDTH, CARD_HEIGHT),
                            player_id, status)
            y += CARD_HEIGHT + CARD_GAP
        hint_key = "ready.hint_one_hand" if self.ctx.solo else "ready.hint"
        hint = fonts.render(tr(hint_key), config.FONT_SIZE_MEDIUM, config.COLOR_TEXT)
        surface.blit(hint, hint.get_rect(midbottom=(surface.get_width() // 2,
                                                    surface.get_height() - HINT_BOTTOM_GAP)))
        self.draw_touch_cursor(surface)
        if self._countdown is not None:
            self._draw_countdown(surface)

    def _status(self, result: VisionResult | None, player_id: int) -> TrackStatus | None:
        """A player's hand status; when one person plays, their hand counts for both."""
        if result is None:
            return None
        if self.ctx.solo:
            tracked = any(p.status is TrackStatus.TRACKED for p in result.players)
            return TrackStatus.TRACKED if tracked else TrackStatus.ABSENT
        return result.player(player_id).status

    def _is_computer(self, player_id: int) -> bool:
        if not self.ctx.vs_computer:
            return False
        human = 1 if config.PLAYER_1_SIDE == self.ctx.human_side else 2
        return player_id != human

    def _draw_card(self, surface: pygame.Surface, card: pygame.Rect, player_id: int,
                   status: TrackStatus | None) -> None:
        tr, fonts = self.ctx.tr, self.ctx.fonts
        draw_panel(surface, card)
        is_ready = player_id in self.ready
        color = PLAYER_COLORS[player_id]
        if is_ready:
            pygame.draw.rect(surface, config.COLOR_OK, card, width=4,
                             border_radius=config.PANEL_RADIUS)
        piece = Piece.TIGER if side_key(player_id) == "side.tigers" else Piece.COW
        icon = self.ctx.sprites.get(piece, ICON_SIZE)
        surface.blit(icon, (card.left + CARD_PADDING, card.top + CARD_PADDING))
        x = card.left + CARD_PADDING * 2 + ICON_SIZE
        y = card.top + CARD_PADDING
        for text, size, text_color in (
            (tr("player.label", number=player_id), config.FONT_SIZE_LARGE, color),
            (tr(side_key(player_id)), config.FONT_SIZE_MEDIUM, config.COLOR_TEXT),
        ):
            rendered = fonts.render(text, size, text_color, bold=True)
            surface.blit(rendered, (x, y))
            y += rendered.get_height()
        detected = status is TrackStatus.TRACKED
        show_key = "ready.show_one_hand" if self.ctx.solo else "ready.show_hand"
        hand_text = tr("ready.hand_detected" if detected else show_key)
        if self._is_computer(player_id):
            detected, hand_text = True, tr("computer.name")
        hand = fonts.render(hand_text, config.FONT_SIZE_SMALL,
                            config.COLOR_OK if detected else config.COLOR_WARNING)
        surface.blit(hand, (x, y))
        state_key = "ready.ready" if is_ready else "ready.pinch_when_ready"
        state = fonts.render(tr(state_key), config.FONT_SIZE_LARGE,
                             config.COLOR_OK if is_ready else config.COLOR_TEXT_MUTED, bold=True)
        surface.blit(state, state.get_rect(bottomleft=(card.left + CARD_PADDING,
                                                       card.bottom - CARD_PADDING)))

    def _draw_countdown(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((*config.COLOR_BACKGROUND, OVERLAY_ALPHA))
        surface.blit(shade, (0, 0))
        remaining = self._countdown - config.GAME_START_BANNER_TIME
        if remaining > 0:
            text, size = str(math.ceil(remaining)), config.FONT_SIZE_HUGE * 2
        else:
            text, size = self.ctx.tr("ready.game_start"), config.FONT_SIZE_HUGE
        rendered = self.ctx.fonts.render(text, size, config.COLOR_TIGER, bold=True)
        surface.blit(rendered, rendered.get_rect(center=surface.get_rect().center))
