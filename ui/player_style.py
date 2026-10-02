"""How players are presented: colour and side (Tigers / Cows) per player number."""

from __future__ import annotations

import config

PLAYER_COLORS: dict[int, config.Color] = {
    1: config.COLOR_PLAYER_1_CURSOR,  # 🔵
    2: config.COLOR_PLAYER_2_CURSOR,  # 🟢
}
UNASSIGNED_COLOR: config.Color = config.COLOR_LOCKED

_SIDE_KEYS = {"TIGER": "side.tigers", "COW": "side.cows"}


def side_key(player_id: int) -> str:
    """Translation key of the side a player controls, from config."""
    side = config.PLAYER_1_SIDE if player_id == 1 else config.PLAYER_2_SIDE
    return _SIDE_KEYS[side]
