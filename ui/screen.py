"""Base class and shared context for all screens.

Screens receive *pointer* callbacks rather than raw mouse events, so the same
screen works with the mouse (development) and with the gesture cursor (game).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

import pygame

import config
from audio.sound_manager import SoundEffect, SoundManager
from game.piece import Piece
from ui.fonts import FontManager
from ui.piece_sprites import PieceSprites
from ui.text import Translator

HEADER_TITLE_GAP = 4


class ScreenId(Enum):
    """Identifiers used to navigate between screens."""

    SYSTEM_CHECK = auto()
    MENU = auto()
    GAME = auto()
    READY = auto()
    GAME_OVER = auto()
    HOW_TO_PLAY = auto()
    CAMERA_CHECK = auto()
    CALIBRATION = auto()
    SETTINGS = auto()
    EXIT = auto()


@dataclass
class UiContext:
    """Shared services every screen can use."""

    fonts: FontManager
    sprites: PieceSprites
    tr: Translator
    navigate: Callable[[ScreenId], None]
    debug: bool = config.DEBUG_MODE
    input_mode: str = config.INPUT_MODE_MOUSE
    one_hand: bool = config.ONE_HAND_MODE  # One player, one hand, both sides.
    computer_level: str = config.COMPUTER_LEVEL  # OFF = two people play.
    human_side: str = config.HUMAN_SIDE  # The person's side against the computer.
    sounds: SoundManager | None = None

    @property
    def vs_computer(self) -> bool:
        return self.computer_level != "OFF"

    @property
    def solo(self) -> bool:
        """One person plays: one-hand play or against the computer."""
        return self.one_hand or self.vs_computer

    def play(self, effect: SoundEffect) -> None:
        """Play a sound effect if sound is available (never fails)."""
        if self.sounds is not None:
            self.sounds.play(effect)


def game_entry_screen(ctx: UiContext) -> ScreenId:
    """Where START GAME / PLAY AGAIN lead: the ready check needs the camera, so
    mouse mode (no camera) goes straight to the game."""
    return ScreenId.READY if ctx.input_mode == config.INPUT_MODE_GESTURE else ScreenId.GAME


class Screen:
    """A full-window screen. Subclasses override the hooks they need."""

    def __init__(self, ctx: UiContext) -> None:
        self.ctx = ctx

    @property
    def uses_vision(self) -> bool:
        """True if the camera + hand tracking must run while this screen is shown."""
        return False

    def on_enter(self) -> None:
        """Called every time the screen becomes active."""

    def on_exit(self) -> None:
        """Called when another screen becomes active (release resources here)."""

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        """The pointer (mouse or gesture cursor) moved."""

    def on_select(self, pos: tuple[int, int]) -> None:
        """The pointer confirmed a selection (mouse click or pinch)."""

    def on_cancel(self) -> None:
        """Cancel the current selection (right-click, or fist gesture later)."""

    def on_back(self) -> None:
        """Leave the screen (ESC key by default returns to the menu)."""
        self.ctx.navigate(ScreenId.MENU)

    def update(self, dt: float) -> None:
        """Advance animations by ``dt`` seconds."""

    def draw(self, surface: pygame.Surface) -> None:
        raise NotImplementedError

    # -- shared drawing helpers ------------------------------------------------
    def draw_title_header(self, surface: pygame.Surface, top: int) -> int:
        """Draw the bilingual game title with piece icons; return next free y."""
        fonts = self.ctx.fonts
        title_km = fonts.render(config.APP_TITLE_KM, config.FONT_SIZE_TITLE, config.COLOR_TIGER,
                                bold=True)
        title_en = fonts.render(config.APP_TITLE_EN, config.FONT_SIZE_MEDIUM, config.COLOR_TEXT,
                                bold=True)
        center_x = surface.get_width() // 2
        km_rect = title_km.get_rect(midtop=(center_x, top))
        surface.blit(title_km, km_rect)
        icon_size = km_rect.height
        tiger = self.ctx.sprites.get(Piece.TIGER, icon_size)
        cow = self.ctx.sprites.get(Piece.COW, icon_size)
        surface.blit(tiger, tiger.get_rect(midright=(km_rect.left - config.UI_MARGIN,
                                                     km_rect.centery)))
        surface.blit(cow, cow.get_rect(midleft=(km_rect.right + config.UI_MARGIN,
                                                km_rect.centery)))
        en_rect = title_en.get_rect(midtop=(center_x, km_rect.bottom + HEADER_TITLE_GAP))
        surface.blit(title_en, en_rect)
        return en_rect.bottom

    def draw_compact_header(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw [tiger] ខ្លាស៊ីគោ  TIGERS VS COWS [cow] on one line inside rect."""
        fonts, gap = self.ctx.fonts, config.UI_MARGIN
        title_km = fonts.render(config.APP_TITLE_KM, config.FONT_SIZE_LARGE, config.COLOR_TIGER,
                                bold=True)
        title_en = fonts.render(config.APP_TITLE_EN, config.FONT_SIZE_LARGE, config.COLOR_TEXT,
                                bold=True)
        icon_size = min(title_km.get_height(), rect.height)
        tiger = self.ctx.sprites.get(Piece.TIGER, icon_size)
        cow = self.ctx.sprites.get(Piece.COW, icon_size)
        parts = (tiger, title_km, title_en, cow)
        x = rect.centerx - (sum(part.get_width() for part in parts) + gap * (len(parts) - 1)) // 2
        for part in parts:
            surface.blit(part, part.get_rect(midleft=(x, rect.centery)))
            x += part.get_width() + gap
