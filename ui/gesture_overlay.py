"""Gesture visuals: smoothed cursor with pinch-progress ring, and a pinch meter."""

from __future__ import annotations

import math

import pygame

import config
from vision.gesture_detector import GestureState, PinchPhase

CURSOR_RADIUS = 14
RING_RADIUS = 22
RING_WIDTH = 5
TRIGGER_FLASH_RADIUS = 30
METER_MAX = 0.8  # Pinch distance shown at the right end of the meter.
METER_HEIGHT = 14
MARKER_OVERHANG = 4
WHITE = (255, 255, 255)
START_ANGLE = math.pi / 2  # Progress ring starts at 12 o'clock.


def draw_cursor(surface: pygame.Surface, center: tuple[int, int], state: GestureState,
                color: config.Color) -> None:
    """Filled cursor dot; a ring fills up while a pinch is held, flashes when it fires."""
    pygame.draw.circle(surface, WHITE, center, CURSOR_RADIUS + 2)
    pygame.draw.circle(surface, color, center, CURSOR_RADIUS)
    phase = state.pinch_phase
    if phase in (PinchPhase.START, PinchPhase.HOLD) and state.pinch_progress > 0:
        ring = pygame.Rect(0, 0, RING_RADIUS * 2, RING_RADIUS * 2)
        ring.center = center
        # pygame arcs run counter-clockwise from 3 o'clock; ending at 12 o'clock and
        # starting further back makes the ring grow clockwise from the top.
        sweep = 2 * math.pi * state.pinch_progress
        pygame.draw.arc(surface, config.COLOR_SELECTED, ring, START_ANGLE - sweep, START_ANGLE,
                        RING_WIDTH)
    elif phase is PinchPhase.TRIGGERED:
        pygame.draw.circle(surface, config.COLOR_SELECTED, center, TRIGGER_FLASH_RADIUS, RING_WIDTH)
    elif phase is PinchPhase.BLOCKED:
        pygame.draw.circle(surface, config.COLOR_LOCKED, center, TRIGGER_FLASH_RADIUS, RING_WIDTH)


def draw_pinch_meter(surface: pygame.Surface, rect: pygame.Rect, distance: float | None) -> None:
    """Bar showing the live pinch distance against both thresholds."""
    pygame.draw.rect(surface, config.COLOR_BACKGROUND, rect, border_radius=METER_HEIGHT // 2)
    if distance is not None:
        if distance < config.PINCH_THRESHOLD:
            color = config.COLOR_OK
        elif distance < config.PINCH_RELEASE_THRESHOLD:
            color = config.COLOR_WARNING
        else:
            color = config.COLOR_LOCKED
        fill = rect.copy()
        fill.width = max(METER_HEIGHT, round(rect.width * min(distance, METER_MAX) / METER_MAX))
        pygame.draw.rect(surface, color, fill, border_radius=METER_HEIGHT // 2)
    for threshold in (config.PINCH_THRESHOLD, config.PINCH_RELEASE_THRESHOLD):
        x = rect.left + round(rect.width * threshold / METER_MAX)
        pygame.draw.line(surface, WHITE, (x, rect.top - MARKER_OVERHANG),
                         (x, rect.bottom + MARKER_OVERHANG), 2)
