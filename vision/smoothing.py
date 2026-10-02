"""Cursor smoothing: a speed-adaptive exponential moving average.

When the hand is still, positions are averaged strongly (weight
CURSOR_SMOOTHING on the previous value) to remove jitter. As the hand speeds
up the smoothing fades out, so the cursor never feels slow or laggy.
"""

from __future__ import annotations

import math

import config

Point = tuple[float, float]


class CursorSmoother:
    def __init__(self, smoothing: float = config.CURSOR_SMOOTHING,
                 fast_speed: float = config.CURSOR_FAST_SPEED) -> None:
        self._smoothing = smoothing
        self._fast_speed = fast_speed
        self._value: Point | None = None
        self._time: float | None = None

    @property
    def smoothing(self) -> float:
        return self._smoothing

    @smoothing.setter
    def smoothing(self, value: float) -> None:
        self._smoothing = value

    @property
    def value(self) -> Point | None:
        return self._value

    def reset(self) -> None:
        self._value = None
        self._time = None

    def update(self, point: Point, now: float) -> Point:
        """Feed a raw position at time ``now``; return the smoothed position."""
        if self._value is None or self._time is None or now <= self._time:
            self._value, self._time = point, now
            return point
        speed = math.dist(point, self._value) / (now - self._time)
        weight = self._smoothing * max(0.0, 1.0 - speed / self._fast_speed)
        self._value = (weight * self._value[0] + (1 - weight) * point[0],
                       weight * self._value[1] + (1 - weight) * point[1])
        self._time = now
        return self._value
