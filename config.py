"""Central configuration for ខ្លាស៊ីគោ — Tigers vs Cows.

Every tunable value in the project lives here so that no module needs to
hard-code "magic numbers". Values are plain module-level constants; runtime
overrides (command-line flags, the in-game Settings screen) are applied on top
of these defaults and never mutate this module.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
# True when running as the packaged TigersVsCows.exe (PyInstaller).
FROZEN: Final[bool] = bool(getattr(sys, "frozen", False))
# Read-only files (assets). PyInstaller unpacks them into sys._MEIPASS.
PROJECT_ROOT: Final[Path] = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
ASSETS_DIR: Final[Path] = PROJECT_ROOT / "assets"
FONTS_DIR: Final[Path] = ASSETS_DIR / "fonts"
SOUNDS_DIR: Final[Path] = ASSETS_DIR / "sounds"
IMAGES_DIR: Final[Path] = ASSETS_DIR
# Runtime files (calibration, settings, crash log). TIGER_COW_DATA_DIR
# relocates them; the test suite uses it so tests never touch the player's
# files. The packaged game may live in a read-only folder (Program Files), so
# it keeps them in the user's own AppData folder instead.
_USER_DATA_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "TigersVsCows"
DATA_DIR: Final[Path] = Path(os.environ.get("TIGER_COW_DATA_DIR")
                             or (_USER_DATA_DIR if FROZEN else PROJECT_ROOT / "data"))
CRASH_LOG_FILE: Final[Path] = DATA_DIR / "crash.log"
CALIBRATION_FILE: Final[Path] = DATA_DIR / "calibration.json"
SETTINGS_FILE: Final[Path] = DATA_DIR / "settings.json"
# Optional images; pieces are drawn procedurally when these are absent.
TIGER_IMAGE_FILE: Final[Path] = IMAGES_DIR / "tiger.png"
COW_IMAGE_FILE: Final[Path] = IMAGES_DIR / "cow.png"

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
APP_TITLE_KM: Final[str] = "ខ្លាស៊ីគោ"
APP_TITLE_EN: Final[str] = "TIGERS VS COWS"
APP_SUBTITLE: Final[str] = "Computer Vision Edition"
APP_VERSION: Final[str] = "1.0.0"
MIN_PYTHON_VERSION: Final[tuple[int, int]] = (3, 11)

# ---------------------------------------------------------------------------
# Window / rendering
# ---------------------------------------------------------------------------
WINDOW_WIDTH: Final[int] = 1280
WINDOW_HEIGHT: Final[int] = 720
FULLSCREEN: Final[bool] = False
TARGET_FPS: Final[int] = 60  # UI frame rate; the camera pipeline targets >= 30.

# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
INPUT_MODE_GESTURE: Final[str] = "GESTURE"
INPUT_MODE_MOUSE: Final[str] = "MOUSE"
INPUT_MODE: Final[str] = INPUT_MODE_GESTURE
# One-hand play: a single player plays both sides with one hand (hot-seat).
# Whichever hand is visible acts for the side whose turn it is.
ONE_HAND_MODE: Final[bool] = False
# Computer opponent: OFF (two players) or a level from game.ai.LEVELS.
COMPUTER_LEVELS: Final[tuple[str, ...]] = ("OFF", "EASY", "NORMAL", "HARD")
COMPUTER_LEVEL: Final[str] = "OFF"
HUMAN_SIDE: Final[str] = "COW"  # The side the person plays against the computer.
COMPUTER_THINK_TIME: Final[float] = 0.9  # seconds before the computer acts
COMPUTER_STEP_TIME: Final[float] = 0.6  # seconds between picking up a piece and moving it

DEBUG_MODE: Final[bool] = True

LANGUAGE_EN: Final[str] = "en"
LANGUAGE_KM: Final[str] = "km"
LANGUAGE: Final[str] = LANGUAGE_EN

# ---------------------------------------------------------------------------
# Sound
# ---------------------------------------------------------------------------
SOUND_ENABLED: Final[bool] = True
SOUND_VOLUME: Final[float] = 0.7  # 0.0 – 1.0

# ---------------------------------------------------------------------------
# Camera
# ---------------------------------------------------------------------------
CAMERA_INDEX: Final[int] = 0
CAMERA_WIDTH: Final[int] = 640
CAMERA_HEIGHT: Final[int] = 480
CAMERA_MIRROR: Final[bool] = True  # Mirror so players see themselves naturally.
CAMERA_USE_DIRECTSHOW: Final[bool] = True  # Faster camera start-up on Windows.
CAMERA_REQUESTED_FPS: Final[int] = 30
CAMERA_RETRY_INTERVAL: Final[float] = 2.0  # seconds between reconnection attempts
CAMERA_MAX_READ_FAILURES: Final[int] = 30  # consecutive failed reads = disconnected
CAMERA_FPS_WINDOW: Final[float] = 1.0  # seconds over which camera FPS is averaged
CAMERA_STOP_TIMEOUT: Final[float] = 2.0  # seconds to wait for the capture thread
# Mean pixel brightness (0-255) below which the picture counts as "too dark":
# a closed privacy shutter or an unlit room. Webcams then also slow to ~1 FPS.
CAMERA_DARK_THRESHOLD: Final[float] = 25.0

# ---------------------------------------------------------------------------
# Hand detection (MediaPipe)
# ---------------------------------------------------------------------------
MAX_NUM_HANDS: Final[int] = 2
HAND_DETECTION_CONFIDENCE: Final[float] = 0.6
HAND_PRESENCE_CONFIDENCE: Final[float] = 0.5
HAND_TRACKING_CONFIDENCE: Final[float] = 0.5
# Show MediaPipe's native start-up warnings (normally hidden; useful to debug MediaPipe).
DEBUG_MODE_NATIVE_LOGS: Final[bool] = False
MODELS_DIR: Final[Path] = ASSETS_DIR / "models"
HAND_MODEL_FILE: Final[Path] = MODELS_DIR / "hand_landmarker.task"
HAND_MODEL_URL: Final[str] = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/latest/hand_landmarker.task"
)
VISION_IDLE_WAIT: Final[float] = 0.005  # seconds to wait when no new camera frame

# ---------------------------------------------------------------------------
# Gestures
# ---------------------------------------------------------------------------
# Pinch distance is normalised by hand size (wrist → middle-finger knuckle),
# so the thresholds work regardless of how far the player is from the camera.
# Measured on MediaPipe's sample photo: relaxed open hands read 0.38–0.47, so
# BOTH thresholds must stay below that or a relaxed hand could pinch or never
# release. Touching fingertips read roughly 0.1–0.2. Tune with the live pinch
# meter on the Camera Check screen.
PINCH_THRESHOLD: Final[float] = 0.25
# Hysteresis: a pinch only ends once the distance rises above this value.
PINCH_RELEASE_THRESHOLD: Final[float] = 0.33
PINCH_HOLD_TIME: Final[float] = 0.25  # seconds a pinch must be stable to fire
ACTION_COOLDOWN: Final[float] = 0.50  # seconds between two actions
# A gesture only counts as released after being open this long (ignores 1-frame flicker).
GESTURE_RELEASE_TIME: Final[float] = 0.10
# Closing the fingers drags the index tip; the action uses the cursor position
# from this long before the pinch started.
PINCH_POSITION_LOOKBACK: Final[float] = 0.15
# ...but only to undo a small drift. If the cursor moved further than this
# (normalised image units, about half a board cell) the hand was travelling on
# purpose, so the position where the pinch started is used instead.
PINCH_MAX_DRIFT: Final[float] = 0.08
FIST_HOLD_TIME: Final[float] = 0.5  # ✊ held this long = CANCEL
OPEN_PALM_HOLD_TIME: Final[float] = 1.5  # ✋ held still this long = MENU (pause)
# A relaxed hand (resting between moves, or opening after a pinch) has four
# fairly straight fingers too, so ✋ also needs clearly straight fingers AND the
# thumb spread away from the index knuckle. Measured: relaxed hands read finger
# ratios 1.23–1.33 but thumb spread only 0.27–0.36; a deliberate ✋ reads ~0.7.
PALM_EXTENDED_RATIO: Final[float] = 1.25
PALM_THUMB_SPREAD: Final[float] = 0.55  # thumb tip to index knuckle / hand size
# ✋ only counts while the hand is held still: moving further than this
# (normalised image units) restarts the hold, so reaching across the board
# with an open hand never pauses.
PALM_MAX_MOVEMENT: Final[float] = 0.05
# Finger pose: tip-to-wrist distance divided by knuckle(PIP)-to-wrist distance.
FINGER_EXTENDED_RATIO: Final[float] = 1.15  # above = finger extended
FINGER_CURLED_RATIO: Final[float] = 0.95  # below = finger curled
# Exponential moving average weight of the *previous* position (0 = raw).
CURSOR_SMOOTHING: Final[float] = 0.5
# Settings-screen presets. Pinch: (close, release) thresholds; both must stay
# below a relaxed open hand (~0.38) or a relaxed hand could never "let go".
PINCH_SENSITIVITY_PRESETS: Final[dict[str, tuple[float, float]]] = {
    "LOW": (0.20, 0.28),
    "NORMAL": (PINCH_THRESHOLD, PINCH_RELEASE_THRESHOLD),
    "HIGH": (0.30, 0.36),
}
CURSOR_SMOOTHING_PRESETS: Final[dict[str, float]] = {"LOW": 0.3, "NORMAL": CURSOR_SMOOTHING,
                                                     "HIGH": 0.7}
VOLUME_STEPS: Final[tuple[float, ...]] = (0.0, 0.25, 0.5, 0.75, 1.0)
CAMERA_INDEX_CHOICES: Final[tuple[int, ...]] = (0, 1, 2)
# Smoothing fades out as the hand speeds up (normalised image widths per second),
# so a still cursor is steady but a moving one does not lag.
CURSOR_FAST_SPEED: Final[float] = 1.5
HAND_LOST_GRACE_TIME: Final[float] = 0.6  # keep a player's identity this long

# ---------------------------------------------------------------------------
# Player tracking
# ---------------------------------------------------------------------------
PLAYER_ASSIGNMENT_SCREEN_SIDE: Final[str] = "SCREEN_SIDE"  # left/right half of the camera
PLAYER_ASSIGNMENT_HANDEDNESS: Final[str] = "HANDEDNESS"  # left hand / right hand
PLAYER_ASSIGNMENT_MODE: Final[str] = PLAYER_ASSIGNMENT_SCREEN_SIDE
PLAYER_1_CAMERA_SIDE: Final[str] = "LEFT"  # Player 1 (Tigers) stands on this side
# Largest move (in normalised image units) a tracked hand may make between two
# detections and still count as the same hand.
TRACK_MAX_DISTANCE: Final[float] = 0.25

# ---------------------------------------------------------------------------
# Board mapping (camera -> board)
# ---------------------------------------------------------------------------
# Default area of the (mirrored) camera image that maps onto the 4×4 board, as
# (left, top, right, bottom) in normalised coordinates. 0.6 × 640 px equals
# 0.8 × 480 px, so the region is square in the camera. Board calibration
# (Phase 12) replaces it with four measured corners.
BOARD_REGION: Final[tuple[float, float, float, float]] = (0.2, 0.1, 0.8, 0.9)
# A calibrated board side shorter than this (normalised units) is rejected:
# cells would be too small to point at reliably.
CALIBRATION_MIN_SIDE: Final[float] = 0.2

# ---------------------------------------------------------------------------
# Game rules
# ---------------------------------------------------------------------------
# Which side each physical player controls (names of game.state.Side members).
PLAYER_1_SIDE: Final[str] = "TIGER"
PLAYER_2_SIDE: Final[str] = "COW"

BOARD_ROWS: Final[int] = 4
BOARD_COLS: Final[int] = 4
TIGER_COUNT: Final[int] = 4
COW_COUNT: Final[int] = 12
TIGER_START_POSITIONS: Final[tuple[tuple[int, int], ...]] = (
    (0, 0),
    (0, BOARD_COLS - 1),
    (BOARD_ROWS - 1, 0),
    (BOARD_ROWS - 1, BOARD_COLS - 1),
)

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
# Names are matched with pygame.font.match_font(); the first one found wins.
# Custom .ttf files placed in assets/fonts/ take priority over system fonts.
LATIN_FONT_CANDIDATES: Final[tuple[str, ...]] = ("segoeui", "arial", "dejavusans")
KHMER_FONT_CANDIDATES: Final[tuple[str, ...]] = ("khmerui", "leelawadeeui", "daunpenh")
KHMER_FONT_FILE_HINTS: Final[tuple[str, ...]] = ("khmer", "battambang", "hanuman")

FONT_SIZE_HUGE: Final[int] = 96
FONT_SIZE_TITLE: Final[int] = 56
FONT_SIZE_LARGE: Final[int] = 36
FONT_SIZE_MEDIUM: Final[int] = 26
FONT_SIZE_SMALL: Final[int] = 20

# ---------------------------------------------------------------------------
# Colours (RGB)
# ---------------------------------------------------------------------------
Color = tuple[int, int, int]

COLOR_BACKGROUND: Final[Color] = (16, 22, 36)
COLOR_BACKGROUND_ACCENT: Final[Color] = (28, 38, 60)
COLOR_PANEL: Final[Color] = (32, 42, 64)
COLOR_PANEL_BORDER: Final[Color] = (64, 80, 112)
COLOR_TEXT: Final[Color] = (236, 240, 248)
COLOR_TEXT_MUTED: Final[Color] = (150, 162, 186)
COLOR_TIGER: Final[Color] = (245, 158, 11)
COLOR_COW: Final[Color] = (132, 204, 22)
COLOR_OK: Final[Color] = (34, 197, 94)
COLOR_ERROR: Final[Color] = (239, 68, 68)
COLOR_WARNING: Final[Color] = (250, 204, 21)
COLOR_PLAYER_1_CURSOR: Final[Color] = (59, 130, 246)  # 🔵
COLOR_PLAYER_2_CURSOR: Final[Color] = (34, 197, 94)  # 🟢
COLOR_BUTTON: Final[Color] = (44, 58, 88)
COLOR_BUTTON_HOVER: Final[Color] = (66, 86, 128)
COLOR_BUTTON_BORDER: Final[Color] = (96, 116, 160)
COLOR_BOARD_FRAME: Final[Color] = (110, 70, 38)
COLOR_CELL_LIGHT: Final[Color] = (226, 190, 140)
COLOR_CELL_DARK: Final[Color] = (206, 164, 112)
COLOR_BOARD_LABEL: Final[Color] = (246, 226, 196)
COLOR_HOVER: Final[Color] = (255, 255, 255)
COLOR_SELECTED: Final[Color] = (250, 204, 21)
COLOR_LEGAL_MOVE: Final[Color] = (34, 197, 94)
COLOR_LOCKED: Final[Color] = (148, 163, 184)

# ---------------------------------------------------------------------------
# Layout (pixels, in the 1280×720 logical window)
# ---------------------------------------------------------------------------
UI_MARGIN: Final[int] = 24
HEADER_HEIGHT: Final[int] = 96
SIDE_PANEL_WIDTH: Final[int] = 420
BOARD_FRAME_WIDTH: Final[int] = 34  # Room for the A–D / 1–4 labels.
PANEL_RADIUS: Final[int] = 16
BUTTON_WIDTH: Final[int] = 420
BUTTON_HEIGHT: Final[int] = 64
BUTTON_SPACING: Final[int] = 16
HOVER_ALPHA: Final[int] = 70  # 0–255 overlay strength on the hovered cell.

# ---------------------------------------------------------------------------
# Game screen feedback
# ---------------------------------------------------------------------------
TOAST_DURATION: Final[float] = 2.5  # seconds a feedback message stays visible
TOAST_FADE_TIME: Final[float] = 0.4  # fade-out at the end of TOAST_DURATION
GAME_OVER_DELAY: Final[float] = 2.0  # show the final board before the results
HISTORY_VISIBLE_MOVES: Final[int] = 4  # recent moves listed in the side panel
# ---------------------------------------------------------------------------
# Animations (seconds)
# ---------------------------------------------------------------------------
ANIMATIONS_ENABLED: Final[bool] = True
PLACE_ANIMATION_TIME: Final[float] = 0.35
MOVE_ANIMATION_TIME: Final[float] = 0.25
CAPTURE_ANIMATION_TIME: Final[float] = 0.55
CAPTURE_JUMP_HEIGHT: Final[float] = 0.6  # Arc height in cells.
SELECT_PULSE_SPEED: Final[float] = 6.0  # radians per second
SELECT_PULSE_AMOUNT: Final[float] = 0.07  # ±7 % size
TURN_FLASH_TIME: Final[float] = 0.6
CONFETTI_COUNT: Final[int] = 140

READY_COUNTDOWN_SECONDS: Final[int] = 3  # "3, 2, 1" once both players are ready
GAME_START_BANNER_TIME: Final[float] = 0.8  # "GAME START!" before the board appears
CELL_FLASH_DURATION: Final[float] = 0.45  # green/red flash on the cell a gesture targeted
CELL_FLASH_MAX_ALPHA: Final[int] = 150


def validate_config() -> list[str]:
    """Return a list of human-readable problems with the configuration.

    An empty list means the configuration is consistent.
    """
    problems: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    check(WINDOW_WIDTH > 0 and WINDOW_HEIGHT > 0, "Window size must be positive")
    check(TARGET_FPS > 0, "TARGET_FPS must be positive")
    check(INPUT_MODE in (INPUT_MODE_GESTURE, INPUT_MODE_MOUSE), "Unknown INPUT_MODE")
    check(LANGUAGE in (LANGUAGE_EN, LANGUAGE_KM), "Unknown LANGUAGE")
    check(0.0 <= SOUND_VOLUME <= 1.0, "SOUND_VOLUME must be within 0..1")
    check(CAMERA_WIDTH > 0 and CAMERA_HEIGHT > 0, "Camera size must be positive")
    check(1 <= MAX_NUM_HANDS <= 4, "MAX_NUM_HANDS must be within 1..4")
    for name, value in (
        ("HAND_DETECTION_CONFIDENCE", HAND_DETECTION_CONFIDENCE),
        ("HAND_PRESENCE_CONFIDENCE", HAND_PRESENCE_CONFIDENCE),
        ("HAND_TRACKING_CONFIDENCE", HAND_TRACKING_CONFIDENCE),
    ):
        check(0.0 <= value <= 1.0, f"{name} must be within 0..1")
    check(0.0 < PINCH_THRESHOLD < PINCH_RELEASE_THRESHOLD,
          "Require 0 < PINCH_THRESHOLD < PINCH_RELEASE_THRESHOLD")
    check(PINCH_HOLD_TIME >= 0.0, "PINCH_HOLD_TIME must not be negative")
    check(ACTION_COOLDOWN >= 0.0, "ACTION_COOLDOWN must not be negative")
    check(0.0 <= CURSOR_SMOOTHING < 1.0, "CURSOR_SMOOTHING must be within 0..<1")
    check(CURSOR_FAST_SPEED > 0.0, "CURSOR_FAST_SPEED must be positive")
    check(FINGER_CURLED_RATIO < FINGER_EXTENDED_RATIO,
          "FINGER_CURLED_RATIO must be below FINGER_EXTENDED_RATIO")
    for name, value in (("GESTURE_RELEASE_TIME", GESTURE_RELEASE_TIME),
                        ("PINCH_POSITION_LOOKBACK", PINCH_POSITION_LOOKBACK),
                        ("FIST_HOLD_TIME", FIST_HOLD_TIME),
                        ("OPEN_PALM_HOLD_TIME", OPEN_PALM_HOLD_TIME),
                        ("PALM_MAX_MOVEMENT", PALM_MAX_MOVEMENT)):
        check(value >= 0.0, f"{name} must not be negative")
    region_left, region_top, region_right, region_bottom = BOARD_REGION
    check(0.0 <= region_left < region_right <= 1.0 and 0.0 <= region_top < region_bottom <= 1.0,
          "BOARD_REGION must be (left, top, right, bottom) within 0..1")
    check(0.0 < CALIBRATION_MIN_SIDE < 1.0, "CALIBRATION_MIN_SIDE must be within 0..1")
    check(len(TIGER_START_POSITIONS) == TIGER_COUNT,
          "TIGER_START_POSITIONS must contain TIGER_COUNT cells")
    check(len(set(TIGER_START_POSITIONS)) == len(TIGER_START_POSITIONS),
          "TIGER_START_POSITIONS must not repeat a cell")
    check(all(0 <= r < BOARD_ROWS and 0 <= c < BOARD_COLS
              for r, c in TIGER_START_POSITIONS),
          "TIGER_START_POSITIONS must lie on the board")
    check(PLAYER_ASSIGNMENT_MODE in (PLAYER_ASSIGNMENT_SCREEN_SIDE,
                                     PLAYER_ASSIGNMENT_HANDEDNESS),
          "Unknown PLAYER_ASSIGNMENT_MODE")
    check(PLAYER_1_CAMERA_SIDE in ("LEFT", "RIGHT"), "PLAYER_1_CAMERA_SIDE must be LEFT/RIGHT")
    check(0.0 < TRACK_MAX_DISTANCE <= 1.0, "TRACK_MAX_DISTANCE must be within 0..1")
    check({PLAYER_1_SIDE, PLAYER_2_SIDE} == {"TIGER", "COW"},
          "PLAYER_1_SIDE / PLAYER_2_SIDE must be TIGER and COW (one each)")
    check(COMPUTER_LEVEL in COMPUTER_LEVELS, "Unknown COMPUTER_LEVEL")
    check(HUMAN_SIDE in ("TIGER", "COW"), "HUMAN_SIDE must be TIGER or COW")
    check(COMPUTER_THINK_TIME >= 0.0 and COMPUTER_STEP_TIME >= 0.0,
          "COMPUTER_THINK_TIME / COMPUTER_STEP_TIME must not be negative")
    check(TIGER_COUNT + COW_COUNT <= BOARD_ROWS * BOARD_COLS,
          "Board is too small for all pieces")
    return problems
