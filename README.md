# 🐯 ខ្លាស៊ីគោ: Tigers vs Cows 🐄

**Computer Vision Edition.** The traditional Khmer strategy game *ខ្លាស៊ីគោ* for two players, played **without
touching anything**: one webcam watches both players' hands. Point to move your cursor, pinch to play.

| Main menu | Playing with hand gestures | Results |
| --- | --- | --- |
| ![Main menu](screenshots/final/01_menu.png) | ![Game](screenshots/final/03_game_gestures.png) | ![Results](screenshots/final/05_game_over.png) |

| Ready check | Board calibration | Khmer interface |
| --- | --- | --- |
| ![Ready](screenshots/final/02_ready.png) | ![Calibration](screenshots/final/06_calibration.png) | ![Khmer](screenshots/final/09_game_khmer.png) |

## Features

- **Two players, one webcam, no mouse or keyboard.** Player 1 🐯 stands on the left, Player 2 🐄 on the right.
  Each player's hand is tracked with a stable identity, even when reaching across to point at the board.
- **Four gestures:** ☝️ point = cursor, 🤏 pinch = select/confirm, ✊ fist = cancel/back, ✋ open palm = pause.
  **One pinch = one action**, protected against accidental touches, long holds and noisy frames.
- **Complete rules** for 4 Tigers vs 12 Cows on a 4 × 4 board, with two phases, capture by jumping, and both
  win conditions. Illegal moves are refused with a clear reason.
- **Clear feedback:** bright cursor for the player on turn, a padlock for the other, green/red cell flashes,
  animated moves and captures, sound effects, move history, and end-of-game statistics.
- **Play alone:** a **computer opponent** (Easy / Normal / Hard, you choose Tigers or Cows), or **one-hand
  play** where one person plays both sides. Either way, one hand is all you need.
- **Board calibration:** pinch four corners to choose your own pointing area, with perspective correction, saved
  across launches.
- **English and ខ្មែរ (Khmer)** interface, a Settings screen (sound, sensitivity, smoothing, fullscreen, camera…),
  a pause menu, and a mouse mode for playing without a webcam.
- **Robust:** a missing or disconnected camera, missing model or damaged settings file never crashes the game.
  303 automated tests.

## Quick start (Windows)

**Just play (no Python needed):** copy **`TigersVsCows-1.0.0.exe`** (one file) to the computer and double-click it,
or unzip `TigersVsCows-1.0.0-win64.zip` and run `TigersVsCows.exe` inside (starts faster). Both are built with
`python packaging/build.py`; see [Building](docs/BUILDING.md).

**From source:**

```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py --check
python main.py
```

Requires Python 3.11+ and, for gesture play, a webcam. Full instructions, including camera placement:
**[Installation guide](docs/INSTALLATION.md)**.

No webcam? `python main.py --input mouse` plays the full game with the mouse.

## How to play (short version)

1. **START GAME** (pinch it). On the ready check, each player pinches once, then **3 · 2 · 1**.
2. **Cows go first:** Player 2 points at an empty cell and pinches to place a Cow.
3. **Tigers:** Player 1 pinches a Tiger, then pinches a green dot to move, or jumps over a Cow to eat it.
4. Place all 12 Cows, then both sides move one cell at a time.
5. 🐯 Tigers win by eating all 12 Cows. 🐄 Cows win by leaving the Tigers no legal move.

Details: **[User guide](docs/USER_GUIDE.md)** · **[Game rules](docs/GAME_RULES.md)**

## Documentation

| Document | For |
| --- | --- |
| [Installation](docs/INSTALLATION.md) | Setting up Python, the packages and the webcam |
| [User guide](docs/USER_GUIDE.md) | Gestures, screens, calibration, settings, mouse and keyboard |
| [Game rules](docs/GAME_RULES.md) | The full rules, with examples and clarifications |
| [Troubleshooting](docs/TROUBLESHOOTING.md) | Camera, hand tracking, gestures, display, sound |
| [Architecture](docs/ARCHITECTURE.md) | Layers, threads, data flow and design decisions (developers) |
| [Testing](docs/TESTING.md) | Test suite, final-testing results, known issues, manual checklist |
| [Building](docs/BUILDING.md) | Making the Windows program (`TigersVsCows.exe` + zip) |

## Technology

| Part | Used |
| --- | --- |
| Language | Python 3.11+ (developed with 3.13) |
| Hand tracking | [MediaPipe](https://ai.google.dev/edge/mediapipe) Hand Landmarker (21 landmarks per hand, 2 hands) |
| Camera | OpenCV (`opencv-contrib-python`) |
| Graphics, sound | `pygame-ce` (renders Khmer script correctly) |
| Maths | NumPy |

```text
Webcam → camera thread → vision thread (MediaPipe → players → gestures) → gesture events
       → game engine (rules) → UI (Pygame, 60 FPS)
```

The game engine is pure Python and independent of the camera, so it is fully testable without a webcam.

## Project structure

```text
main.py              Command line and start-up checks
config.py            Every setting and constant (validated at start-up)
requirements.txt     numpy, opencv-contrib-python, mediapipe, pygame-ce
app/                 Application, screens and navigation, saved settings, diagnostics
camera/              Threaded webcam capture
vision/              Hand detection, player tracking, gestures, board mapping, calibration file
game/                Rules engine (pure Python)
ui/                  Screens, board and cursor rendering, animations, English/Khmer text
audio/               Sound effects (files or generated tones)
assets/              Hand model; optional sounds, fonts, images
data/                settings.json, calibration.json (created at runtime)
docs/                Documentation
tests/               303 automated tests
packaging/           Windows program build (PyInstaller)
screenshots/         Screenshots (final/ is the current set; phase*/ document development)
```

## Testing

```bat
python -m unittest discover -s tests -t . -v
```

Runs without a webcam, window or speaker. See the [Testing report](docs/TESTING.md) for coverage (96 %), stress
results and the manual checklist for real players.

## Credits

- *ខ្លាស៊ីគោ* is a traditional Khmer game.
- Hand model `hand_landmarker.task` and the test photo `tests/data/woman_hands.jpg`: Google MediaPipe
  (Apache License 2.0).
- Piece artwork and sound effects are generated by the game's code.

## Future ideas

Online play, a draw rule option, larger boards, a native-speaker-reviewed Khmer translation,
a tutorial mode, and recording/replaying games.
