"""Side panel showing turn, phase, piece counts, player state and a hint."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

import config
from game.piece import Piece
from ui.fonts import FontManager
from ui.piece_sprites import PieceSprites
from ui.text import Translator
from ui.widgets import draw_panel

PADDING = 20
ICON_SIZE = 48
SECTION_GAP = 12
BANNER_HEIGHT = 64
PLAYER_ROW_HEIGHT = 36
LOCK_DOT_RADIUS = 9
FLASH_GROW = 6
FLASH_ALPHA = 220


@dataclass(frozen=True)
class StatusInfo:
    """Read-only data displayed by the status panel."""

    tiger_turn: bool
    phase_key: str  # Translation key, e.g. "phase.placement".
    tigers: int
    cows_on_board: int
    cows_to_place: int
    cows_captured: int
    hint_key: str
    recent_moves: tuple[str, ...] = ()  # Newest last.
    winner_is_tiger: bool | None = None  # Set once the game is over.
    turn_flash: float = 0.0  # 1 right after a turn change, fading to 0.
    computer_player: int | None = None  # Named "Computer" instead of "Player N".


class StatusPanel:
    """Renders :class:`StatusInfo` into the side-panel rectangle."""

    def __init__(self, fonts: FontManager, sprites: PieceSprites, tr: Translator) -> None:
        self._fonts = fonts
        self._sprites = sprites
        self._tr = tr

    def draw(self, surface: pygame.Surface, rect: pygame.Rect, info: StatusInfo) -> None:
        draw_panel(surface, rect)
        inner = rect.inflate(-2 * PADDING, -2 * PADDING)
        y = self._draw_turn_banner(surface, inner, info)
        y = self._draw_text(surface, inner.left, y,
                            f"{self._tr('phase.label')}: {self._tr(info.phase_key)}",
                            config.FONT_SIZE_MEDIUM, config.COLOR_TEXT)
        y = self._draw_side(surface, inner.left, y + SECTION_GAP, Piece.TIGER,
                            self._tr("side.tigers"),
                            f"{info.tigers} {self._tr('status.on_board')}", config.COLOR_TIGER)
        cow_detail = (f"{info.cows_on_board} {self._tr('status.on_board')} · "
                      f"{info.cows_to_place} {self._tr('status.to_place')} · "
                      f"{info.cows_captured} {self._tr('status.captured')}")
        y = self._draw_side(surface, inner.left, y, Piece.COW, self._tr("side.cows"),
                            cow_detail, config.COLOR_COW)
        y = self._draw_players(surface, inner.left, y + SECTION_GAP, info)
        y = self._draw_hint(surface, inner, y + SECTION_GAP, info.hint_key)
        self._draw_history(surface, inner, y + SECTION_GAP, info.recent_moves)

    def _draw_turn_banner(self, surface: pygame.Surface, inner: pygame.Rect,
                          info: StatusInfo) -> int:
        if info.winner_is_tiger is None:
            tiger = info.tiger_turn
            label = self._tr("turn.tiger" if tiger else "turn.cow")
        else:
            tiger = info.winner_is_tiger
            label = self._tr("gameover.tiger_wins" if tiger else "gameover.cow_wins")
        color = config.COLOR_TIGER if tiger else config.COLOR_COW
        banner = pygame.Rect(inner.left, inner.top, inner.width, BANNER_HEIGHT)
        pygame.draw.rect(surface, color, banner, border_radius=config.PANEL_RADIUS)
        if info.turn_flash > 0:  # New turn: a white glow that fades out.
            glow = banner.inflate(FLASH_GROW * 2, FLASH_GROW * 2)
            layer = pygame.Surface(glow.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, (255, 255, 255, round(FLASH_ALPHA * info.turn_flash)),
                             layer.get_rect(), width=FLASH_GROW + 2,
                             border_radius=config.PANEL_RADIUS + FLASH_GROW)
            surface.blit(layer, glow)
        icon = self._sprites.get(Piece.TIGER if tiger else Piece.COW, BANNER_HEIGHT - 8)
        surface.blit(icon, icon.get_rect(midleft=(banner.left + 8, banner.centery)))
        text = self._fonts.render(label, config.FONT_SIZE_LARGE, config.COLOR_BACKGROUND,
                                  bold=True)
        surface.blit(text, text.get_rect(center=banner.center))
        return banner.bottom + SECTION_GAP

    def _draw_text(self, surface: pygame.Surface, x: int, y: int, text: str, size: int,
                   color: config.Color, bold: bool = False) -> int:
        rendered = self._fonts.render(text, size, color, bold=bold)
        surface.blit(rendered, (x, y))
        return y + rendered.get_height()

    def _draw_side(self, surface: pygame.Surface, x: int, y: int, piece: Piece, name: str,
                   detail: str, color: config.Color) -> int:
        icon = self._sprites.get(piece, ICON_SIZE)
        surface.blit(icon, (x, y))
        text_x = x + ICON_SIZE + PADDING // 2
        name_bottom = self._draw_text(surface, text_x, y, name, config.FONT_SIZE_MEDIUM, color,
                                      bold=True)
        self._draw_text(surface, text_x, name_bottom, detail, config.FONT_SIZE_SMALL,
                        config.COLOR_TEXT_MUTED)
        return y + ICON_SIZE + SECTION_GAP // 2

    def _draw_players(self, surface: pygame.Surface, x: int, y: int, info: StatusInfo) -> int:
        playing = info.winner_is_tiger is None  # Both players are locked after game over.
        players = ((1, "side.tigers", playing and info.tiger_turn),
                   (2, "side.cows", playing and not info.tiger_turn))
        for number, side_key, active in players:
            center_y = y + PLAYER_ROW_HEIGHT // 2
            dot_color = config.COLOR_OK if active else config.COLOR_LOCKED
            pygame.draw.circle(surface, dot_color, (x + LOCK_DOT_RADIUS, center_y), LOCK_DOT_RADIUS)
            state = self._tr("player.active" if active else "player.locked")
            name = (self._tr("computer.name") if number == info.computer_player
                    else self._tr("player.label", number=number))
            label = f"{name} ({self._tr(side_key)}): {state}"
            text = self._fonts.render(label, config.FONT_SIZE_SMALL,
                                      config.COLOR_TEXT if active else config.COLOR_LOCKED,
                                      bold=active)
            surface.blit(text, text.get_rect(midleft=(x + LOCK_DOT_RADIUS * 3, center_y)))
            y += PLAYER_ROW_HEIGHT
        return y

    def _draw_history(self, surface: pygame.Surface, inner: pygame.Rect, top: int,
                      moves: tuple[str, ...]) -> None:
        """List recent moves at the bottom of the panel, as many as fit below ``top``."""
        line_height = self._fonts.get(config.FONT_SIZE_SMALL).get_linesize()
        title = self._fonts.render(self._tr("history.title"), config.FONT_SIZE_SMALL,
                                   config.COLOR_TEXT_MUTED, bold=True)
        fit = (inner.bottom - top - title.get_height()) // line_height
        moves = moves[-fit:] if fit > 0 else ()
        if not moves:
            return
        y = inner.bottom - line_height * len(moves)
        surface.blit(title, (inner.left, y - title.get_height()))
        for index, text in enumerate(moves):
            newest = index == len(moves) - 1
            self._draw_text(surface, inner.left, y, text, config.FONT_SIZE_SMALL,
                            config.COLOR_TEXT if newest else config.COLOR_TEXT_MUTED)
            y += line_height

    def _draw_hint(self, surface: pygame.Surface, inner: pygame.Rect, y: int,
                   hint_key: str) -> int:
        for line in self._fonts.render_wrapped(self._tr(hint_key), config.FONT_SIZE_MEDIUM,
                                               config.COLOR_WARNING, inner.width):
            surface.blit(line, (inner.left, y))
            y += line.get_height()
        return y
