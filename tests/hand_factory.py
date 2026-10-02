"""Builds anatomically plausible synthetic hands for gesture tests.

Coordinates below are in "palm units" (wrist at 0,0; fingers point up = -y)
and are scaled/placed into normalised image coordinates.
"""

from __future__ import annotations

from vision import landmarks as lm
from vision.hand_detector import Hand, Landmark

MCP = {lm.INDEX_MCP: (-0.3, -1.0), lm.MIDDLE_MCP: (-0.1, -1.05),
       lm.RING_MCP: (0.1, -1.0), lm.PINKY_MCP: (0.3, -0.9)}
EXTENDED = ((0.0, -0.45), (0.0, -0.75), (0.0, -1.0))  # PIP, DIP, TIP offsets from MCP
CURLED = ((0.0, -0.35), (0.0, -0.2), (0.0, 0.1))  # tip folds back towards the palm
THUMB_OUT = {lm.THUMB_CMC: (-0.35, -0.25), lm.THUMB_MCP: (-0.6, -0.45),
             lm.THUMB_IP: (-0.8, -0.6), lm.THUMB_TIP: (-1.0, -0.75)}
FINGER_MCPS = (lm.INDEX_MCP, lm.MIDDLE_MCP, lm.RING_MCP, lm.PINKY_MCP)


def make_hand(x: float = 0.5, y: float = 0.7, scale: float = 0.12,
              fingers: str = "EEEE", pinch_gap: float | None = None,
              handedness: str = "Right", thumb_tucked: bool = False) -> Hand:
    """``fingers``: E (extended) / C (curled) for index, middle, ring, pinky.

    ``pinch_gap``: if given, the thumb tip is placed this far (in hand-size
    units) from the index tip; otherwise the thumb sticks out sideways, or
    rests against the index knuckle if ``thumb_tucked`` (a relaxed hand).
    """
    points: dict[int, tuple[float, float]] = {lm.WRIST: (0.0, 0.0), **THUMB_OUT}
    for mcp, state in zip(FINGER_MCPS, fingers):
        points[mcp] = MCP[mcp]
        offsets = EXTENDED if state == "E" else CURLED
        for step, (dx, dy) in enumerate(offsets, start=1):
            points[mcp + step] = (MCP[mcp][0] + dx, MCP[mcp][1] + dy)
    if thumb_tucked:
        points[lm.THUMB_TIP] = (-0.25, -0.7)
    if pinch_gap is not None:
        hand_size = abs(MCP[lm.MIDDLE_MCP][1])  # ~ wrist to middle knuckle
        tip_x, tip_y = points[lm.INDEX_TIP]
        points[lm.THUMB_TIP] = (tip_x - pinch_gap * hand_size, tip_y)
    ordered = [points[i] for i in range(lm.LANDMARK_COUNT)]
    return Hand(tuple(Landmark(x + px * scale, y + py * scale) for px, py in ordered),
                handedness, 0.9)


# Index fingertip offset from the wrist, in palm units, for an extended index finger.
INDEX_TIP_OFFSET = (MCP[lm.INDEX_MCP][0] + EXTENDED[2][0], MCP[lm.INDEX_MCP][1] + EXTENDED[2][1])


def hand_pointing_at(x: float, y: float, scale: float = 0.08, pinch_gap: float | None = None,
                     fingers: str = "ECCC") -> Hand:
    """A hand whose index fingertip is exactly at image point (x, y)."""
    return make_hand(x - INDEX_TIP_OFFSET[0] * scale, y - INDEX_TIP_OFFSET[1] * scale, scale,
                     fingers=fingers, pinch_gap=pinch_gap)
