# Architecture

This document explains how the game is built: the layers, the threads, how a pinch becomes a move, and why the key
design decisions were made. File references are relative to the project root.

## Layers

```text
VISION   camera/camera.py          webcam capture (own thread)
         vision/hand_detector.py   MediaPipe HandLandmarker -> Hand objects
         vision/player_tracker.py  hands -> Player 1 / Player 2 (stable identities)
         vision/gesture_detector.py point / pinch / fist / open palm -> GestureEvents
         vision/coordinate_mapper.py camera point -> board (u, v) -> cell (row, col)
         vision/pipeline.py        runs the above on its own thread

INPUT    vision GestureEvent  --(ui/game_screen.py)-->  game GameEvent {"player", "action", "cell"}
         (the mouse produces the same GameEvent)

GAME     game/game_engine.py       the only place rules are applied
         game/{board,movement,tiger,cow,capture,win_condition,state}.py
         game/ai.py                computer opponent (look-ahead search)

UI       app/application.py        window, screens, main loop, settings
         ui/*.py                   screens and renderers (Pygame)
         audio/sound_manager.py    sound effects
```

The separation is enforced by tests (`tests/test_architecture.py`):

| Layer | May not import |
| --- | --- |
| `game/` | pygame, OpenCV, MediaPipe, NumPy, or any other project layer |
| `vision/` | pygame, `ui`, `app`, `audio` |
| `camera/` | pygame and every other project layer |
| `ui/`, `app/`, `game/`, `audio/` | OpenCV, MediaPipe (only `camera/` and `vision/` touch them) |

So the rules can be tested and played without a webcam, and the vision code can run without a window.

## Threads

```text
camera thread   : webcam.read() -> mirror -> latest Frame                      (~30 FPS)
vision thread   : new Frame -> detect hands -> track players -> gestures
                  -> latest VisionResult + GestureEvents into a queue        (~30 FPS, ~15-25 ms each)
UI (main) thread: pygame events -> screen; drain gesture queue -> screen;
                  update animations; draw; flip                              (60 FPS)
```

- Hand detection takes about 20 ms per frame. Running it in the UI loop would halve the frame rate, so it has its own
  thread. The UI only reads the **latest** result, under a lock.
- Each `VisionResult` keeps the camera frame it was computed from, so drawings of hands always line up with the
  image they belong to.
- **Gesture events go through a queue** (`VisionPipeline.drain_events()`), not through "latest result". Every
  pinch reaches the UI **exactly once**, even if the UI and vision threads run at different speeds. Pending events
  are discarded when the pipeline stops and when a screen is entered, so a pinch can never leak into the next
  screen.
- The camera and vision threads run only while the current screen needs them (`Screen.uses_vision`). In mouse mode
  the camera is off everywhere except the calibration screens.

## From a pinch to a move

```text
1. camera thread      640x480 frame, mirrored                        camera/camera.py
2. vision thread      HandDetector.detect -> (Hand, Hand)             vision/hand_detector.py
3.                    PlayerTracker.update -> P1 = hand 0, P2 = hand 1 vision/player_tracker.py
4.                    PlayerGestureTracker: smoothed index tip,       vision/gesture_detector.py
                      pinch closed for 0.25 s -> GestureEvent(P2, SELECT, position before the pinch)
5. UI thread          GameScreen.handle_gesture: mapper.cell_at(position) -> Cell(1, 2)
                      -> GameEvent(player=2, SELECT, cell=C2)         ui/game_screen.py
6.                    GameEngine.handle_event -> ActionResult(PLACED, record)  game/game_engine.py
7.                    feedback: sound, green flash, "Cow placed at C2", drop-in animation
```

The engine never knows whether an event came from a pinch or a mouse click.

## Key design decisions

| Decision | Why |
| --- | --- |
| **MediaPipe Tasks `HandLandmarker`** (VIDEO mode) instead of `mp.solutions.hands` | MediaPipe 1.x removed the old API. VIDEO mode tracks hands between frames (faster, steadier). |
| **pygame-ce** instead of pygame | Only pygame-ce can shape Khmer script (HarfBuzz via `Font.set_script("Khmr")`); plain pygame draws ខ្លាស៊ីគោ as broken glyphs. It is a drop-in replacement (`import pygame`). |
| **`opencv-contrib-python`** only | MediaPipe depends on it; also installing `opencv-python` makes both packages overwrite the same `cv2` files and breaks OpenCV. |
| Pinch distance ÷ hand size, with **hysteresis** (close < 0.25, open > 0.33) | Works at any distance from the camera and doesn't flicker at the threshold. Both values were set **below a relaxed open hand (0.38–0.47, measured)**; otherwise a relaxed hand could pinch, or a pinch could never end. |
| Hold time, fire-once, release debounce, cooldown | "One pinch = one action": brief touches, long holds, noisy frames and quick repeats cannot cause duplicate actions. |
| Pinch uses the cursor position **0.15 s before** the pinch, but only if it moved < 0.08 | Closing the fingers drags the fingertip; a larger movement means the player deliberately moved to a new cell. |
| Player tracking: **continuity first, then camera side, then recovery** | Players reach across the middle to point at any cell, so "left half = Player 1" can only be used for *new* hands. A briefly lost hand keeps its identity for 0.6 s, and an orphan hand that reappears goes back to the player who just lost it. |
| Board mapping by **homography** from four corners | One code path for the default rectangle and for calibrated (possibly tilted) areas. |
| Engine state changes instantly; **animations are UI-only** | Rules never wait for visuals; tests stay fast and deterministic. |
| Only the **engine** enforces whose turn it is | The locked player's pinches are sent with their own player number and refused by the engine, so there is one source of truth. |
| **Settings = saved + command-line overrides**; only changed fields are saved | `--input mouse` for one session never becomes a permanent setting. |
| Generated fallback sounds | The game has sound without any asset files; real files in `assets/sounds/` take priority. |

## Module map

| Module | Responsibility |
| --- | --- |
| `main.py` | Command line (`--check`, `--download-model`, session options), start-up checks |
| `config.py` | Every constant, plus `validate_config()` |
| `app/application.py` | Window, screen registry and navigation, event routing, settings application, main loop |
| `app/settings.py` | `Settings` dataclass, validated load/save of `data/settings.json` |
| `app/diagnostics.py` | Dependency, hand-model and camera checks; model download |
| `camera/camera.py` | Threaded capture, mirroring, FPS, retry/reconnect, camera switching |
| `vision/hand_detector.py` | MediaPipe wrapper, `Hand` / `Landmark` data |
| `vision/player_tracker.py` | Hand → player assignment with stable identities |
| `vision/gesture_detector.py` | Poses, `HoldTrigger`, per-player gesture tracking, `GestureEvent` |
| `vision/smoothing.py` | Speed-adaptive cursor smoothing |
| `vision/coordinate_mapper.py` | Homography and camera → board → cell mapping |
| `vision/calibration_store.py` | Validated load/save of `data/calibration.json` |
| `vision/pipeline.py` | Vision thread, latest result, exactly-once event queue |
| `game/game_engine.py` | Applies events, validates, turns, phases, history, statistics |
| `game/state.py` | `GameState`, `Side`, `Phase`, `MoveRecord`, `GameStats` |
| `game/movement.py`, `tiger.py`, `cow.py`, `capture.py`, `win_condition.py` | The rules, as pure functions |
| `game/ai.py` | Computer opponent: alpha-beta search over a compact copy of the rules (tests check it always agrees with the engine); `GameScreen` plays its turns |
| `ui/screen.py` | `Screen` base class, `ScreenId`, shared `UiContext` |
| `ui/touchless_screen.py` | Point-and-pinch buttons for non-game screens |
| `ui/game_screen.py` | The board screen: input → engine, cursors, feedback, pause |
| `ui/board_renderer.py`, `animations.py`, `piece_sprites.py` | Board drawing, animations, procedural pieces |
| `ui/text.py`, `move_text.py`, `fonts.py` | English/Khmer strings, translated move text, Khmer-aware fonts |
| other `ui/*.py` | One module per screen or widget (menu, ready, calibration, settings, camera check, game over, …) |
| `audio/sound_manager.py` | Sound effects with file or generated fallback |

## Extending the game

| To add… | Change |
| --- | --- |
| A language | Add a table to `STRINGS` in `ui/text.py`, the language code to `LANGUAGES` in `app/settings.py`, and its name as `settings.language.<code>` in every table. `tests/test_ui.py` checks that every English string is translated and that placeholders match. |
| A gesture | Add a pose test in `vision/gesture_detector.py`, a `HoldTrigger`, and a `GestureAction`; handle it in `GameScreen.handle_gesture` / `TouchlessScreen.update`. |
| A rule variant (e.g. compulsory capture) | `game/` only; add tests next to `tests/test_game_engine.py`. The UI needs no change. |
| A setting | A field in `Settings` (+ validation), an `Option` in `ui/settings_screen.py`, applied in `Application.update_settings`. |
| Different sides | `PLAYER_1_SIDE` / `PLAYER_2_SIDE` and `PLAYER_1_CAMERA_SIDE` in `config.py` |

## Runtime files

| Path | Content |
| --- | --- |
| `data/settings.json` | Saved settings (only what the player changed) |
| `data/calibration.json` | Four calibrated corners |
| `assets/models/hand_landmarker.task` | MediaPipe hand model (Apache 2.0) |
| `assets/sounds/`, `assets/fonts/`, `assets/tiger.png`, `assets/cow.png` | Optional replacements |

`TIGER_COW_DATA_DIR` (environment variable) relocates `data/`; the test suite uses it so tests never touch the
player's files.
