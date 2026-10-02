"""Screen layout for the game screen, computed from the window size."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

import config


@dataclass(frozen=True)
class GameLayout:
    """Rectangles for the header, the square board, the camera column and the side panel."""

    header: pygame.Rect
    board: pygame.Rect
    side_panel: pygame.Rect
    camera_column: pygame.Rect  # Between board and side panel: camera preview + players.

    @classmethod
    def for_size(cls, width: int, height: int) -> GameLayout:
        margin = config.UI_MARGIN
        header = pygame.Rect(0, 0, width, config.HEADER_HEIGHT)
        side_panel = pygame.Rect(width - margin - config.SIDE_PANEL_WIDTH, header.bottom,
                                 config.SIDE_PANEL_WIDTH, height - header.bottom - margin)
        free_width = side_panel.left - 2 * margin
        free_height = height - header.bottom - margin
        board_frame = 2 * config.BOARD_FRAME_WIDTH
        # Grid side must divide evenly into cells so the lines stay crisp.
        grid_side = (min(free_width, free_height) - board_frame) // config.BOARD_COLS
        side = grid_side * config.BOARD_COLS + board_frame
        board = pygame.Rect(0, 0, side, side)
        board.midleft = (margin, header.bottom + free_height // 2)
        column_left = board.right + margin
        camera_column = pygame.Rect(column_left, board.top,
                                    side_panel.left - margin - column_left, board.height)
        return cls(header, board, side_panel, camera_column)
