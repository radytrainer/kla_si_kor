"""HOW TO PLAY screen: controls and rules summary."""

from __future__ import annotations

import pygame

import config
from ui.screen import ScreenId, UiContext
from ui.touchless_screen import TouchlessScreen
from ui.widgets import Button, draw_background, draw_panel

PANEL_TOP = 110
PANEL_WIDTH = 1040
PANEL_BOTTOM_GAP = 110
PADDING = 28
HEADING_GAP = 10
BULLET_INDENT = 28
BULLET = "•"

SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("howto.controls", ("howto.control_point", "howto.control_pinch", "howto.control_fist",
                        "howto.control_palm", "howto.control_one_hand")),
    ("howto.rules", ("howto.rule_setup", "howto.rule_turns", "howto.rule_move",
                     "howto.rule_capture", "howto.rule_win")),
)


class HowToPlayScreen(TouchlessScreen):
    """Static instructions with a BACK button."""

    def __init__(self, ctx: UiContext, pipeline) -> None:
        super().__init__(ctx, pipeline)
        back_rect = pygame.Rect(0, 0, config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        back_rect.midbottom = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT - config.UI_MARGIN)
        self._back = Button(back_rect, lambda: ctx.tr("common.back"),
                            lambda: ctx.navigate(ScreenId.MENU))

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        self._back.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        self._back.try_click(pos)

    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        fonts, tr = self.ctx.fonts, self.ctx.tr
        title = fonts.render(tr("howto.title"), config.FONT_SIZE_TITLE, config.COLOR_TIGER,
                             bold=True)
        surface.blit(title, title.get_rect(midtop=(surface.get_width() // 2, config.UI_MARGIN)))

        panel = pygame.Rect(0, PANEL_TOP, PANEL_WIDTH,
                            surface.get_height() - PANEL_TOP - PANEL_BOTTOM_GAP)
        panel.centerx = surface.get_width() // 2
        draw_panel(surface, panel)
        x, y = panel.left + PADDING, panel.top + PADDING
        text_width = panel.width - 2 * PADDING - BULLET_INDENT
        for heading_key, item_keys in SECTIONS:
            heading = fonts.render(tr(heading_key), config.FONT_SIZE_LARGE, config.COLOR_COW,
                                   bold=True)
            surface.blit(heading, (x, y))
            y += heading.get_height() + HEADING_GAP
            for key in item_keys:
                bullet = fonts.render(BULLET, config.FONT_SIZE_MEDIUM, config.COLOR_TIGER)
                surface.blit(bullet, (x, y))
                for line in fonts.render_wrapped(tr(key), config.FONT_SIZE_MEDIUM,
                                                 config.COLOR_TEXT, text_width):
                    surface.blit(line, (x + BULLET_INDENT, y))
                    y += line.get_height()
            y += HEADING_GAP
        self._back.draw(surface, fonts)
        self.draw_touch_cursor(surface)
