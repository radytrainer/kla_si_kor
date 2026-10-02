# Installation guide

This guide sets up ខ្លាស៊ីគោ, Tigers vs Cows, on **Windows 10 or 11**. It takes about 10 minutes, most of it
downloading packages.

## What you need

| | |
| --- | --- |
| Computer | Windows 10/11, 64-bit. A mid-range laptop is enough (the game was tested at 60 FPS on a standard office laptop). |
| Python | **3.11 or newer** from [python.org](https://www.python.org/downloads/) (tick *"Add python.exe to PATH"* during setup) or Anaconda. Developed and tested with 3.13. |
| Webcam | Any built-in or USB webcam. Optional: without one you can still play with the mouse. |
| Disk space | About 600 MB for the Python packages |
| Internet | Only during installation |

Other operating systems (macOS, Linux) are not tested. The code has no Windows-only features except the faster
DirectShow camera start-up, which falls back automatically.

## Option A: the ready-made Windows program

The easiest way for players: **no Python needed.** There are two versions (built with
`python packaging/build.py`, see [Building](BUILDING.md)):

| | Single file | Zip |
| --- | --- | --- |
| File | `TigersVsCows-1.0.0.exe` (127 MB) | `TigersVsCows-1.0.0-win64.zip` (134 MB) |
| Setup | Copy it anywhere, double-click it | Right-click → **Extract All…**, then double-click `TigersVsCows.exe` in the folder |
| Start time | ~7 s every time (a *Loading…* picture shows while it unpacks) | ~2 s |
| Also includes | Just the game | `TigersVsCows-console.exe` for `--check`, and `README.txt` |

With the zip, always extract first: the `.exe` needs the `_internal` folder next to it.

- If Windows shows *"Windows protected your PC"*, click **More info → Run anyway** (the program is not signed with
  a paid certificate).
- The **first** start takes longer (up to a minute); later starts take a few seconds.
- Settings and calibration are stored in `%LOCALAPPDATA%\TigersVsCows`. Delete that folder to reset.
- To check the camera and components: open a command window in the folder and run
  `TigersVsCows-console.exe --check`.
- To uninstall: delete the `TigersVsCows` folder (and `%LOCALAPPDATA%\TigersVsCows`).

The rest of this guide is **Option B: running from source**, for developers or if you want to change the code.

## Option B: running from source

## Step 1: Get the project

Copy the project folder anywhere, for example `C:\Games\kla_c_kor`. Open **PowerShell** or **Command Prompt** in that
folder: in File Explorer, type `powershell` in the address bar and press Enter.

## Step 2: Create a virtual environment

```bat
python -m venv venv
```

This creates a private `venv` folder holding the game's packages, so they never interfere with other Python
programs on the computer.

## Step 3: Activate it

```bat
venv\Scripts\activate
```

The prompt now starts with `(venv)`. Do this every time you open a new terminal to run the game.

> **PowerShell says "running scripts is disabled"?** Run this once, then try again:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
> Alternatively, use Command Prompt (`cmd`) instead of PowerShell.

## Step 4: Install the packages

```bat
pip install -r requirements.txt
```

This installs exactly four packages:

| Package | Used for |
| --- | --- |
| `numpy` | Image and geometry maths |
| `opencv-contrib-python` | Webcam capture |
| `mediapipe` | Hand tracking (Google's hand-landmark model) |
| `pygame-ce` | Window, graphics and sound |

> **Do not also install `opencv-python`.** MediaPipe already uses `opencv-contrib-python`, and having both
> installed breaks OpenCV. `pygame-ce` is a maintained drop-in version of `pygame`; it is required because plain
> `pygame` cannot display Khmer text correctly.

## Step 5: Check everything

```bat
python main.py --check
```

Expected output:

```text
Environment check:
  [     OK]  Python      3.13.9
  [     OK]  NumPy       2.5.3
  [     OK]  OpenCV      5.0.0
  [     OK]  MediaPipe   1.0.1
  [     OK]  pygame-ce   2.5.8
  [     OK]  Hand model  7.8 MB
  [     OK]  Camera      640x480 @ 30 fps
All good.
```

Version numbers may differ. If **Hand model** is missing, download it once (about 7.8 MB):

```bat
python main.py --download-model
```

If **Camera** fails, see [Troubleshooting: camera](TROUBLESHOOTING.md#camera). You can still play with
`python main.py --input mouse`.

## Step 6: Play

```bat
python main.py
```

Next: read the [User guide](USER_GUIDE.md), or just open **HOW TO PLAY** in the game.

## Setting up the camera and players

For two players with one webcam:

```text
                 [ screen + webcam ]
                         |
        about 1–1.5 m    |
                         v
   Player 1 🐯 (left)          Player 2 🐄 (right)
```

- **Placement:** put the webcam on top of the screen, facing the players, at about chest-to-face height.
- **Positions:** stand or sit **side by side**: Player 1 on the left, Player 2 on the right, as seen on screen.
  The image is mirrored like a mirror, so your left is the screen's left.
- **Distance:** about 1–1.5 m from the camera, so both players' hands fit in the picture.
- **Lighting:** light the players from the front; avoid a bright window behind them. Good light also keeps the
  webcam at 30 FPS; some webcams drop to 15 FPS in dim light.
- **First time:** open **CALIBRATE CAMERA** from the menu and pinch the four corners of a comfortable square in
  front of you (see the [User guide](USER_GUIDE.md#calibrating-the-board-area)).

## Updating, resetting, uninstalling

| Task | How |
| --- | --- |
| Reset all settings | Delete `data\settings.json` |
| Reset the calibration | Delete `data\calibration.json` (or **RESET TO DEFAULT** on the calibration screen) |
| Reinstall packages | `pip install --force-reinstall -r requirements.txt` |
| Uninstall | Delete the project folder; everything, including `venv`, is inside it |

## Running the tests (optional)

```bat
python -m unittest discover -s tests -t . -v
```

303 automated tests run in about 2 minutes without a webcam, window or speaker. See [Testing](TESTING.md).
