"""Assigns detected hands to Player 1 and Player 2 with stable identities.

Two rules, applied in order every frame:

1. **Continuity.** Hands are matched to the players they were closest to in
   the previous frames (minimum total distance, so two hands passing each other
   do not swap). A player keeps their identity wherever the hand moves, so a
   player may reach across the middle of the camera to point at the board.
2. **Assignment of new hands.** A hand that matches no tracked player is given
   to a free player by an :class:`AssignmentRule` (default: camera side).
3. **Recovery.** A hand still unassigned goes to a player who *just* lost
   theirs (within the grace time), even across the midline: each player has one
   hand, so an orphan hand reappearing after a dropout or a very fast move while
   reaching across the board must be theirs.

A player whose hand vanishes is LOST for up to HAND_LOST_GRACE_TIME seconds
(identity and last position kept), then ABSENT.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import config
from vision.hand_detector import Hand

PLAYER_IDS: tuple[int, ...] = (1, 2)
MIDLINE = 0.5


class TrackStatus(Enum):
    TRACKED = "TRACKED"  # Hand visible this frame.
    LOST = "LOST"  # Hand missing for less than the grace time.
    ABSENT = "ABSENT"  # No hand for this player.


@dataclass(frozen=True)
class PlayerSnapshot:
    """What the tracker knows about one player after an update."""

    player_id: int
    status: TrackStatus
    hand: Hand | None  # Current hand, or the last seen hand while LOST.
    hand_index: int | None  # Index in this frame's detection list (None unless TRACKED).
    lost_for: float = 0.0  # Seconds since the hand was last seen.

    @property
    def present(self) -> bool:
        return self.status is not TrackStatus.ABSENT


class AssignmentRule(Protocol):
    def player_for(self, hand: Hand) -> int | None:
        """Which player a *new* hand belongs to (None = nobody)."""


class ScreenSideRule:
    """Player 1 on one half of the (mirrored) camera image, Player 2 on the other."""

    def __init__(self, player_1_side: str = config.PLAYER_1_CAMERA_SIDE) -> None:
        if player_1_side not in ("LEFT", "RIGHT"):
            raise ValueError("player_1_side must be LEFT or RIGHT")
        self._player_1_left = player_1_side == "LEFT"

    def player_for(self, hand: Hand) -> int | None:
        on_left = hand.center[0] < MIDLINE
        return 1 if on_left == self._player_1_left else 2


class HandednessRule:
    """Player 1 uses their left hand, Player 2 their right hand (as MediaPipe reports)."""

    def player_for(self, hand: Hand) -> int | None:
        return {"Left": 1, "Right": 2}.get(hand.handedness)


def rule_from_config() -> AssignmentRule:
    if config.PLAYER_ASSIGNMENT_MODE == config.PLAYER_ASSIGNMENT_HANDEDNESS:
        return HandednessRule()
    return ScreenSideRule()


def distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def best_matching(costs: list[list[float]], max_cost: float) -> dict[int, int]:
    """Minimum-total-cost matching of rows to columns, ignoring pairs above max_cost.

    Maximises the number of matched pairs first, then minimises total cost.
    Brute force is fine: there are at most a few hands and two players.
    """
    rows = len(costs)
    cols = len(costs[0]) if costs else 0
    best: dict[int, int] = {}
    best_key = (0, 0.0)
    for size in range(min(rows, cols), 0, -1):
        for chosen_rows in itertools.combinations(range(rows), size):
            for chosen_cols in itertools.permutations(range(cols), size):
                pairs = list(zip(chosen_rows, chosen_cols))
                if any(costs[r][c] > max_cost for r, c in pairs):
                    continue
                total = sum(costs[r][c] for r, c in pairs)
                key = (size, -total)
                if not best or key > best_key:
                    best, best_key = dict(pairs), key
        if best:  # Larger matchings always win; no need to try smaller sizes.
            return best
    return best


@dataclass
class _Track:
    hand: Hand | None = None
    last_seen: float | None = None

    def is_active(self, now: float) -> bool:
        return (self.last_seen is not None
                and now - self.last_seen <= config.HAND_LOST_GRACE_TIME)


class PlayerTracker:
    """Keeps a stable hand -> player mapping across frames."""

    def __init__(self, rule: AssignmentRule | None = None) -> None:
        self._rule = rule if rule is not None else rule_from_config()
        self._tracks: dict[int, _Track] = {player: _Track() for player in PLAYER_IDS}
        self._last: tuple[PlayerSnapshot, ...] = self._snapshots({}, 0.0)

    def reset(self) -> None:
        self._tracks = {player: _Track() for player in PLAYER_IDS}
        self._last = self._snapshots({}, 0.0)

    @property
    def players(self) -> tuple[PlayerSnapshot, ...]:
        return self._last

    def update(self, hands: tuple[Hand, ...], now: float) -> tuple[PlayerSnapshot, ...]:
        """Process one detection result taken at time ``now`` (seconds)."""
        assigned = self._match_by_continuity(hands, now)
        self._assign_new_hands(hands, assigned)
        self._recover_lost_players(hands, assigned, now)
        for hand_index, player in assigned.items():
            self._tracks[player] = _Track(hands[hand_index], now)
        self._last = self._snapshots(assigned, now)
        return self._last

    def _match_by_continuity(self, hands: tuple[Hand, ...], now: float) -> dict[int, int]:
        """Return {hand_index: player} for hands near an active track."""
        active = [p for p in PLAYER_IDS if self._tracks[p].is_active(now)]
        if not hands or not active:
            return {}
        costs = [[distance(hand.center, self._tracks[p].hand.center) for p in active]
                 for hand in hands]
        matching = best_matching(costs, config.TRACK_MAX_DISTANCE)
        return {hand_index: active[col] for hand_index, col in matching.items()}

    def _assign_new_hands(self, hands: tuple[Hand, ...], assigned: dict[int, int]) -> None:
        taken = set(assigned.values())
        for hand_index, hand in enumerate(hands):
            if hand_index in assigned:
                continue
            player = self._rule.player_for(hand)
            if player is not None and player not in taken:
                assigned[hand_index] = player
                taken.add(player)

    def _recover_lost_players(self, hands: tuple[Hand, ...], assigned: dict[int, int],
                              now: float) -> None:
        taken = set(assigned.values())
        lost = [p for p in PLAYER_IDS if p not in taken and self._tracks[p].is_active(now)]
        for player in lost:
            free = [i for i in range(len(hands)) if i not in assigned]
            if not free:
                return
            last = self._tracks[player].hand.center
            nearest = min(free, key=lambda i: distance(hands[i].center, last))
            assigned[nearest] = player

    def _snapshots(self, assigned: dict[int, int], now: float) -> tuple[PlayerSnapshot, ...]:
        index_of = {player: hand_index for hand_index, player in assigned.items()}
        result = []
        for player in PLAYER_IDS:
            track = self._tracks[player]
            if player in index_of:
                result.append(PlayerSnapshot(player, TrackStatus.TRACKED, track.hand,
                                             index_of[player]))
            elif track.is_active(now):
                result.append(PlayerSnapshot(player, TrackStatus.LOST, track.hand, None,
                                             now - track.last_seen))
            else:
                result.append(PlayerSnapshot(player, TrackStatus.ABSENT, None, None))
        return tuple(result)
