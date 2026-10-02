"""Easing curves: map linear progress t (0..1) to animated progress."""

from __future__ import annotations

BACK_OVERSHOOT = 1.70158


def clamp01(t: float) -> float:
    return min(1.0, max(0.0, t))


def ease_in_out_cubic(t: float) -> float:
    t = clamp01(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_cubic(t: float) -> float:
    return 1 - (1 - clamp01(t)) ** 3


def ease_out_back(t: float) -> float:
    """Overshoots slightly past 1 then settles: a small "bounce" on arrival."""
    t = clamp01(t)
    c3 = BACK_OVERSHOOT + 1
    return 1 + c3 * (t - 1) ** 3 + BACK_OVERSHOOT * (t - 1) ** 2


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
