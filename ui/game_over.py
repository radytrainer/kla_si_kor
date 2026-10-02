"""Game Over screen: winner, reason, statistics, PLAY AGAIN / MAIN MENU."""

from __future__ import annotations

import math

import pygame

import config
from audio.sound_manager import SoundEffect
from game.game_engine import GameEngine
from game.state import GameStats, Side
from ui.screen import ScreenId, UiContext, game_entry_screen
from ui.confetti import Confetti
from ui.touchless_screen import TouchlessScreen
from ui.widgets import Button, draw_background, draw_panel

TOP = 24
WINNER_ICON_SIZE = 150
TEXT_GAP = 6
STATS_WIDTH = 520
STATS_ROW_HEIGHT = 34
STATS_PADDING = 18
BUTTON_GAP = 24
BOUNCE_SPEED = 4.0  # radians per second
BOUNCE_HEIGHT = 18  # pixels


class GameOverScreen(TouchlessScreen):
    """Shows the result of the engine's finished game."""

    def __init__(self, ctx: UiContext, engine: GameEngine, pipeline) -> None:
        super().__init__(ctx, pipeline)
        self._engine = engine
        self._celebration_time = 0.0
        self._confetti = Confetti(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        bottom = config.WINDOW_HEIGHT - config.UI_MARGIN
        left = pygame.Rect(0, 0, config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        left.bottomright = (config.WINDOW_WIDTH // 2 - BUTTON_GAP // 2, bottom)
        right = left.copy()
        right.bottomleft = (config.WINDOW_WIDTH // 2 + BUTTON_GAP // 2, bottom)
        self._buttons = [
            Button(left, lambda: ctx.tr("gameover.play_again"),
                   lambda: ctx.navigate(game_entry_screen(ctx))),
            Button(right, lambda: ctx.tr("gameover.menu"),
                   lambda: ctx.navigate(ScreenId.MENU)),
        ]

    def on_enter(self) -> None:
        super().on_enter()
        self._celebration_time = 0.0
        self._confetti = Confetti(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self.ctx.play(SoundEffect.VICTORY if self._engine.state.winner is not None
                      else SoundEffect.GAME_OVER)

    def update(self, dt: float) -> None:
        super().update(dt)
        self._celebration_time += dt
        self._confetti.update(dt)

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            button.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            if button.try_click(pos):
                return

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        if self._engine.state.winner is not None:
            self._confetti.draw(surface)  # Behind the text so it stays readable.
        state = self._engine.state
        center_x = surface.get_width() // 2
        y = TOP
        winner = state.winner
        if winner is not None:
            icon = self.ctx.sprites.get(winner.piece, WINNER_ICON_SIZE)
            bounce = abs(math.sin(self._celebration_time * BOUNCE_SPEED)) * BOUNCE_HEIGHT
            surface.blit(icon, icon.get_rect(midtop=(center_x, y - round(bounce))))
            y += WINNER_ICON_SIZE
            title_key = "gameover.tiger_wins" if winner is Side.TIGER else "gameover.cow_wins"
            color = config.COLOR_TIGER if winner is Side.TIGER else config.COLOR_COW
            reason = self.ctx.tr(f"gameover.reason.{winner.value}")
            if self.ctx.vs_computer:  # Say who won: the person or the computer.
                you_won = winner.value == self.ctx.human_side
                who = self.ctx.tr("gameover.you_win" if you_won else "gameover.computer_wins")
                reason = f"{who} · {reason}"
        else:
            title_key, color, reason = "gameover.title", config.COLOR_TEXT, ""
        y = self._blit_centered(surface, self.ctx.tr(title_key), config.FONT_SIZE_TITLE,
                                color, y, bold=True)
        if reason:
            y = self._blit_centered(surface, reason, config.FONT_SIZE_MEDIUM,
                                    config.COLOR_TEXT_MUTED, y)
        self._draw_stats(surface, center_x, y + TEXT_GAP * 2, self._engine.stats())
        for button in self._buttons:
            button.draw(surface, self.ctx.fonts)
        self.draw_touch_cursor(surface)

    def _blit_centered(self, surface: pygame.Surface, text: str, size: int,
                       color: config.Color, y: int, bold: bool = False) -> int:
        rendered = self.ctx.fonts.render(text, size, color, bold=bold)
        surface.blit(rendered, rendered.get_rect(midtop=(surface.get_width() // 2, y)))
        return y + rendered.get_height() + TEXT_GAP

    def _draw_stats(self, surface: pygame.Surface, center_x: int, top: int,
                    stats: GameStats) -> None:
        rows = (
            ("stats.duration", stats.duration_text),
            ("stats.total_moves", str(stats.total_moves)),
            ("stats.cows_captured", str(stats.cows_captured)),
            ("stats.tiger_moves", str(stats.tiger_moves)),
            ("stats.cow_moves", str(stats.cow_moves)),
            ("stats.cow_placements", str(stats.cow_placements)),
        )
        panel = pygame.Rect(0, top, STATS_WIDTH, 2 * STATS_PADDING + STATS_ROW_HEIGHT * len(rows))
        panel.centerx = center_x
        draw_panel(surface, panel)
        for index, (key, value) in enumerate(rows):
            y = panel.top + STATS_PADDING + index * STATS_ROW_HEIGHT + STATS_ROW_HEIGHT // 2
            label = self.ctx.fonts.render(self.ctx.tr(key), config.FONT_SIZE_MEDIUM,
                                          config.COLOR_TEXT_MUTED)
            surface.blit(label, label.get_rect(midleft=(panel.left + STATS_PADDING, y)))
            number = self.ctx.fonts.render(value, config.FONT_SIZE_MEDIUM, config.COLOR_TEXT,
                                           bold=True)
            surface.blit(number, number.get_rect(midright=(panel.right - STATS_PADDING, y)))
