"""Gesture detection: ☝️ point, 🤏 pinch, ✊ fist, ✋ open palm.

Static pose analysis turns one :class:`Hand` into finger states and a pinch
distance. Per-player :class:`PlayerGestureTracker` objects add time: cursor
smoothing, pinch hysteresis, hold times, release debouncing and a shared
action cooldown, so that **one pinch produces exactly one SELECT event**.

Pinch life cycle (see :class:`PinchPhase`)::

    IDLE -> START -> HOLD --(PINCH_HOLD_TIME)--> TRIGGERED -> RELEASING -> IDLE
                        \\--(in cooldown)------> BLOCKED ---/
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace
from enum import Enum

import config
from vision import landmarks as lm
from vision.hand_detector import Hand
from vision.player_tracker import PlayerSnapshot, TrackStatus
from vision.smoothing import CursorSmoother, Point

# (tip, PIP joint) for index, middle, ring, pinky.
FINGERS: tuple[tuple[int, int], ...] = (
    (lm.INDEX_TIP, lm.INDEX_PIP),
    (lm.MIDDLE_TIP, lm.MIDDLE_PIP),
    (lm.RING_TIP, lm.RING_PIP),
    (lm.PINKY_TIP, lm.PINKY_PIP),
)
INDEX, MIDDLE, RING, PINKY = range(4)
MIN_HAND_SIZE = 1e-6


class Pose(Enum):
    NONE = "NONE"
    POINT = "POINT"  # ☝️
    PINCH = "PINCH"  # 🤏
    OPEN_PALM = "OPEN_PALM"  # ✋
    FIST = "FIST"  # ✊


class PinchPhase(Enum):
    IDLE = "IDLE"
    START = "START"  # First frame the fingers are closed.
    HOLD = "HOLD"  # Closed, waiting for PINCH_HOLD_TIME.
    TRIGGERED = "TRIGGERED"  # SELECT fired; nothing more until release.
    BLOCKED = "BLOCKED"  # Hold time reached during cooldown; ignored until release.
    RELEASING = "RELEASING"  # Opened, waiting GESTURE_RELEASE_TIME to confirm.


class GestureAction(Enum):
    SELECT = "SELECT"  # 🤏 pinch
    CANCEL = "CANCEL"  # ✊ fist
    MENU = "MENU"  # ✋ open palm


@dataclass(frozen=True)
class GestureEvent:
    """A confirmed gesture, in normalised camera coordinates."""

    player_id: int
    action: GestureAction
    position: Point | None
    timestamp: float


@dataclass(frozen=True)
class HandPose:
    """Static analysis of one hand."""

    extended: tuple[bool, bool, bool, bool]  # index, middle, ring, pinky
    curled: tuple[bool, bool, bool, bool]
    pinch_distance: float  # thumb-index distance / hand size
    palm_open: bool = False  # Deliberate ✋: straight fingers, thumb spread out.

    @property
    def is_fist(self) -> bool:
        return all(self.curled)

    @property
    def is_open_palm(self) -> bool:
        return self.palm_open and all(self.extended)

    @property
    def is_pointing(self) -> bool:
        return self.extended[INDEX] and not any(self.extended[MIDDLE:])


def _dist(a, b) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def finger_ratio(hand: Hand, tip: int, pip: int) -> float:
    """Tip-to-wrist distance divided by PIP-to-wrist distance (>1 = straight)."""
    wrist = hand.wrist
    return _dist(hand.point(tip), wrist) / max(_dist(hand.point(pip), wrist), MIN_HAND_SIZE)


def pinch_distance(hand: Hand) -> float:
    """Thumb-tip to index-tip distance, normalised by hand size."""
    return _dist(hand.thumb_tip, hand.index_tip) / max(hand.size, MIN_HAND_SIZE)


def thumb_spread(hand: Hand) -> float:
    """Thumb-tip to index-knuckle distance, normalised by hand size."""
    return (_dist(hand.thumb_tip, hand.point(lm.INDEX_MCP))
            / max(hand.size, MIN_HAND_SIZE))


def analyse_hand(hand: Hand) -> HandPose:
    ratios = [finger_ratio(hand, tip, pip) for tip, pip in FINGERS]
    return HandPose(
        extended=tuple(r > config.FINGER_EXTENDED_RATIO for r in ratios),
        curled=tuple(r < config.FINGER_CURLED_RATIO for r in ratios),
        pinch_distance=pinch_distance(hand),
        palm_open=(all(r > config.PALM_EXTENDED_RATIO for r in ratios)
                   and thumb_spread(hand) > config.PALM_THUMB_SPREAD),
    )


class HoldTrigger:
    """Fires once when a condition has been held for ``hold_time``.

    It re-arms only after the condition has been false for ``release_time``,
    so single-frame flicker neither fires early nor causes a second firing.
    """

    def __init__(self, hold_time: float,
                 release_time: float = config.GESTURE_RELEASE_TIME) -> None:
        self.hold_time = hold_time
        self.release_time = release_time
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.started_at = 0.0
        self.fired = False
        self.blocked = False
        self.open_since: float | None = None
        self.just_started = False

    def update(self, condition: bool, now: float, allowed: bool = True) -> bool:
        """Advance with this frame's condition; True means "fire now"."""
        self.just_started = False
        if condition:
            self.open_since = None
            if not self.active:
                self.active, self.started_at = True, now
                self.fired = self.blocked = False
                self.just_started = True
            if not self.fired and now - self.started_at >= self.hold_time:
                self.fired = True
                self.blocked = not allowed
                return allowed
            return False
        if self.active:
            if self.open_since is None:
                self.open_since = now
            if now - self.open_since >= self.release_time:
                self.reset()
        return False

    def progress(self, now: float) -> float:
        """0..1 towards firing (1 once fired)."""
        if not self.active:
            return 0.0
        if self.fired or self.hold_time <= 0:
            return 1.0
        return min(1.0, (now - self.started_at) / self.hold_time)

    @property
    def releasing(self) -> bool:
        return self.active and self.open_since is not None


@dataclass(frozen=True)
class GestureTuning:
    """Values the Settings screen can change while the game runs."""

    pinch_threshold: float = config.PINCH_THRESHOLD
    pinch_release_threshold: float = config.PINCH_RELEASE_THRESHOLD
    cursor_smoothing: float = config.CURSOR_SMOOTHING


@dataclass(frozen=True)
class GestureState:
    """Everything the UI needs to show one player's gesture status."""

    player_id: int
    tracked: bool
    pose: Pose = Pose.NONE
    cursor: Point | None = None  # Smoothed index fingertip.
    raw_tip: Point | None = None
    pinch_distance: float | None = None
    pinch_phase: PinchPhase = PinchPhase.IDLE
    pinch_progress: float = 0.0
    cooldown_remaining: float = 0.0


class PlayerGestureTracker:
    """Turns one player's stream of hands into a cursor and gesture events."""

    def __init__(self, player_id: int, tuning: GestureTuning | None = None) -> None:
        self.player_id = player_id
        self.tuning = tuning or GestureTuning()
        self.reset()

    def set_tuning(self, tuning: GestureTuning) -> None:
        self.tuning = tuning
        self._smoother.smoothing = tuning.cursor_smoothing

    def reset(self) -> None:
        self._smoother = CursorSmoother(smoothing=self.tuning.cursor_smoothing)
        self._pinch = HoldTrigger(config.PINCH_HOLD_TIME)
        self._fist = HoldTrigger(config.FIST_HOLD_TIME)
        self._palm = HoldTrigger(config.OPEN_PALM_HOLD_TIME)
        self._palm_origin: Point | None = None
        self._history: deque[tuple[float, Point]] = deque()
        self._pinch_closed = False
        self._anchor: Point | None = None
        self._last_action = -math.inf
        self._state = GestureState(self.player_id, tracked=False)

    def update(self, player: PlayerSnapshot,
               now: float) -> tuple[GestureState, list[GestureEvent]]:
        if player.status is TrackStatus.ABSENT or player.hand is None:
            self.reset()
            return self._state, []
        if player.status is TrackStatus.LOST:
            # Freeze everything (cursor, timers) until the hand returns or is gone.
            return replace(self._state, tracked=False), []
        return self._update_tracked(player.hand, now)

    def _update_tracked(self, hand: Hand,
                        now: float) -> tuple[GestureState, list[GestureEvent]]:
        raw = (hand.index_tip.x, hand.index_tip.y)
        cursor = self._smoother.update(raw, now)
        self._remember(now, cursor)
        pose = analyse_hand(hand)
        tuning = self.tuning  # One read: the UI thread may swap it at any time.
        threshold = (tuning.pinch_release_threshold if self._pinch_closed
                     else tuning.pinch_threshold)
        self._pinch_closed = pose.pinch_distance < threshold and not pose.is_fist

        allowed = now - self._last_action >= config.ACTION_COOLDOWN
        events: list[GestureEvent] = []
        if self._pinch.update(self._pinch_closed, now, allowed):
            events.append(GestureEvent(self.player_id, GestureAction.SELECT,
                                       self._anchor or cursor, now))
        elif self._pinch.just_started:
            self._anchor = self._pinch_anchor(now, cursor)
        fist = pose.is_fist and not self._pinch_closed
        if self._fist.update(fist, now, allowed and not events):
            events.append(GestureEvent(self.player_id, GestureAction.CANCEL, cursor, now))
        palm = self._palm_held_still(pose.is_open_palm and not self._pinch_closed, raw)
        if self._palm.update(palm, now, allowed and not events):
            events.append(GestureEvent(self.player_id, GestureAction.MENU, cursor, now))
        if events:
            self._last_action = now

        self._state = GestureState(
            player_id=self.player_id,
            tracked=True,
            pose=self._display_pose(pose),
            cursor=cursor,
            raw_tip=raw,
            pinch_distance=pose.pinch_distance,
            pinch_phase=self._pinch_phase(),
            pinch_progress=self._pinch.progress(now),
            cooldown_remaining=max(0.0, config.ACTION_COOLDOWN - (now - self._last_action)),
        )
        return self._state, events

    def _palm_held_still(self, palm: bool, tip: Point) -> bool:
        """✋ counts only while the hand stays put; moving restarts the hold."""
        if not palm:
            self._palm_origin = None
            return False
        if self._palm_origin is None or math.dist(tip, self._palm_origin) > config.PALM_MAX_MOVEMENT:
            if self._palm_origin is not None:
                self._palm.reset()
            self._palm_origin = tip
        return True

    def _display_pose(self, pose: HandPose) -> Pose:
        if self._pinch_closed:
            return Pose.PINCH
        if pose.is_fist:
            return Pose.FIST
        if pose.is_open_palm:
            return Pose.OPEN_PALM
        if pose.is_pointing:
            return Pose.POINT
        return Pose.NONE

    def _pinch_phase(self) -> PinchPhase:
        trigger = self._pinch
        if not trigger.active:
            return PinchPhase.IDLE
        if trigger.releasing:
            return PinchPhase.RELEASING
        if trigger.fired:
            return PinchPhase.BLOCKED if trigger.blocked else PinchPhase.TRIGGERED
        return PinchPhase.START if trigger.just_started else PinchPhase.HOLD

    def _remember(self, now: float, cursor: Point) -> None:
        self._history.append((now, cursor))
        horizon = now - 2 * max(config.PINCH_POSITION_LOOKBACK, config.GESTURE_RELEASE_TIME)
        while len(self._history) > 1 and self._history[0][0] < horizon:
            self._history.popleft()

    def _pinch_anchor(self, now: float, cursor: Point) -> Point:
        """Where the player aimed: undo the small drag of closing the fingers, but
        not a deliberate move onto a new target just before pinching."""
        earlier = self._position_before(now - config.PINCH_POSITION_LOOKBACK)
        return earlier if math.dist(earlier, cursor) <= config.PINCH_MAX_DRIFT else cursor

    def _position_before(self, when: float) -> Point:
        """Latest remembered cursor position at or before ``when`` (else the oldest)."""
        best = self._history[0][1]
        for timestamp, position in self._history:
            if timestamp > when:
                break
            best = position
        return best


class GestureRecognizer:
    """One :class:`PlayerGestureTracker` per player."""

    def __init__(self, player_ids: tuple[int, ...] = (1, 2)) -> None:
        self._trackers = {pid: PlayerGestureTracker(pid) for pid in player_ids}

    def set_tuning(self, tuning: GestureTuning) -> None:
        for tracker in self._trackers.values():
            tracker.set_tuning(tuning)

    def reset(self) -> None:
        for tracker in self._trackers.values():
            tracker.reset()

    def update(self, players: tuple[PlayerSnapshot, ...],
               now: float) -> tuple[tuple[GestureState, ...], list[GestureEvent]]:
        states: list[GestureState] = []
        events: list[GestureEvent] = []
        for player in players:
            tracker = self._trackers.get(player.player_id)
            if tracker is None:
                continue
            state, new_events = tracker.update(player, now)
            states.append(state)
            events.extend(new_events)
        return tuple(states), events
