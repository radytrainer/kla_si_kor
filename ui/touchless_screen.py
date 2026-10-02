"""Shared point-and-pinch controls for non-game screens (menus, ready, game over).

In gesture mode either tracked player can point at a button and pinch to press
it, so no mouse is needed. The whole (mirrored) camera image maps onto the
whole window. A fist means "back" (except on the main menu, where it is
ignored so a resting fist can never quit the game).
"""

from __future__ import annotations

import pygame

import config
from ui.player_style import PLAYER_COLORS
from ui.screen import Screen, UiContext
from vision.gesture_detector import GestureAction, GestureEvent
from vision.pipeline import VisionPipeline

TOUCH_CURSOR_RADIUS = 13
TOUCH_CURSOR_RING = 3
TOUCH_CURSOR_DOT = 3


def camera_to_window(point: tuple[float, float]) -> tuple[int, int]:
    """Map a normalised camera point onto the window, clamped to its edges."""
    x = min(max(round(point[0] * config.WINDOW_WIDTH), 0), config.WINDOW_WIDTH - 1)
    y = min(max(round(point[1] * config.WINDOW_HEIGHT), 0), config.WINDOW_HEIGHT - 1)
    return x, y


def draw_pointers(surface: pygame.Surface, pointers: dict[int, tuple[int, int]]) -> None:
    """Draw each visible player's window pointer as a ring in their colour."""
    for player_id, position in pointers.items():
        pygame.draw.circle(surface, PLAYER_COLORS[player_id], position,
                           TOUCH_CURSOR_RADIUS, TOUCH_CURSOR_RING)
        pygame.draw.circle(surface, config.COLOR_TEXT, position, TOUCH_CURSOR_DOT)


class TouchlessScreen(Screen):
    """Let either tracked player point at UI controls and pinch to activate them."""

    def __init__(self, ctx: UiContext, pipeline: VisionPipeline) -> None:
        super().__init__(ctx)
        self._pipeline = pipeline
        self._touch_cursors: dict[int, tuple[int, int]] = {}
        # Most screens act on the first pinch of a frame; the ready check needs all.
        self.accept_multiple_gestures = False
        # Whether a player's pointer hovers buttons (off where pinches mean something else).
        self.gesture_hover = True

    @property
    def uses_vision(self) -> bool:
        return self.ctx.input_mode == config.INPUT_MODE_GESTURE

    def on_enter(self) -> None:
        self._touch_cursors = {}
        self._pipeline.drain_events()  # Pinches made on the previous screen are void.

    def update(self, dt: float) -> None:
        result = self._pipeline.latest_result()
        self._touch_cursors = {}
        if result is not None:
            for gesture in result.gestures:
                if gesture.tracked and gesture.cursor is not None:
                    self._touch_cursors[gesture.player_id] = camera_to_window(gesture.cursor)
            if self._touch_cursors and self.gesture_hover:
                # Hover follows the lowest-numbered visible player.
                self.on_pointer_move(self._touch_cursors[min(self._touch_cursors)])
        for event in self._pipeline.drain_events():
            self.on_any_gesture(event)
            if event.action is GestureAction.CANCEL:
                self.on_gesture_cancel()
                break
            if event.action is GestureAction.SELECT and event.position is not None:
                pos = camera_to_window(event.position)
                if self.gesture_hover:
                    self.on_pointer_move(pos)
                self.on_gesture_event(event, pos)
                if not self.accept_multiple_gestures:
                    break

    def on_any_gesture(self, event: GestureEvent) -> None:
        """Called for every gesture before it is handled (e.g. to log it)."""

    def on_gesture_cancel(self) -> None:
        """✊ Fist: go back by default."""
        self.on_back()

    def on_gesture_event(self, event: GestureEvent, pos: tuple[int, int]) -> None:
        self.on_gesture_select(event.player_id, pos)

    def on_gesture_select(self, player_id: int, pos: tuple[int, int]) -> None:
        self.on_select(pos)

    def draw_touch_cursor(self, surface: pygame.Surface) -> None:
        """Draw every visible player's pointer in their colour."""
        draw_pointers(surface, self._touch_cursors)
