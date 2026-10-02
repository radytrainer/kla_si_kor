# Building the Windows program

How to turn the source code into `TigersVsCows.exe`, a program that runs on any Windows 10/11 (64-bit) computer
**without Python**. For players, see the [Installation guide](INSTALLATION.md#option-a-the-ready-made-windows-program).

## Build

From the project root, with the development venv active:

```bat
pip install pyinstaller
rem Folder + zip:
python packaging/build.py
rem One single .exe:
python packaging/build.py --onefile
```

Each takes about 2–3 minutes.

### Single file (`--onefile`)

`dist/TigersVsCows-<version>.exe` (~127 MB) contains everything; send just this one file. On every start it
unpacks itself to a temporary folder (deleted again on exit), so it takes **~7 s to start** instead of ~2 s. A
*Loading…* splash (`packaging/splash.png`) shows immediately during that time and the game closes it as soon as its
window opens. It has no console variant, so `--check` output is not visible; use the folder version for
diagnostics.

### Folder + zip (default)

Output:

| Path | Content |
| --- | --- |
| `dist/TigersVsCows/` | The program folder (~317 MB) |
| `dist/TigersVsCows/TigersVsCows.exe` | The game (no console window) |
| `dist/TigersVsCows/TigersVsCows-console.exe` | Same program with a console, for `--check` and error output |
| `dist/TigersVsCows/README.txt` | Short instructions for players (from `packaging/README.txt`) |
| `dist/TigersVsCows-<version>-win64.zip` | The folder zipped for sharing (~134 MB) |

The version number is `APP_VERSION` in `config.py`. PyInstaller is a build tool only, so it is not in
`requirements.txt`.

## Files

| File | Purpose |
| --- | --- |
| `packaging/build.py` | Runs PyInstaller, checks the essential files are present, adds README.txt, zips |
| `packaging/TigersVsCows.spec` | What goes into the program (see below) |
| `packaging/make_icon.py` | Regenerates `TigersVsCows.ico` and `splash.png` from the game's own art (needs Pillow) |
| `packaging/README.txt` | The player instructions shipped next to the .exe |

## What the packaged program does differently

| Topic | Behaviour |
| --- | --- |
| Settings, calibration, crash log | Saved in `%LOCALAPPDATA%\TigersVsCows` (the program folder may be read-only) |
| Assets and hand model | Bundled inside `_internal/` |
| Errors | No console, so a crash writes `crash.log` (in the folder above) and shows a dialog |
| MediaPipe start-up messages | Hidden; skipped safely when there is no console |

`config.FROZEN` is `True` inside the packaged program.

## Pitfalls handled in the spec

These were found while building and testing the package:

1. **MediaPipe's engine is loaded by path.** MediaPipe 1.x loads `mediapipe/tasks/c/libmediapipe.dll` with
   `ctypes` at runtime; PyInstaller cannot see that, so the spec uses `collect_all("mediapipe")`.
2. **matplotlib and Pillow must stay in.** `mediapipe.tasks.python.vision` imports its drawing helper, and so
   matplotlib, unconditionally. Excluding them breaks hand tracking. `sounddevice` *can* be excluded (MediaPipe guards
   that import).
3. **Only `opencv-contrib-python`** may be installed when building (see the [Architecture](ARCHITECTURE.md) notes).

## Testing a build

Test on a copy **outside the project folder**, in an environment without Python on the PATH, the closest thing
to another computer:

```bash
env -i SYSTEMROOT='C:\Windows' WINDIR='C:\Windows' PATH='/c/Windows/System32:/c/Windows' \
    LOCALAPPDATA="$LOCALAPPDATA" USERPROFILE="$USERPROFILE" TEMP="$TEMP" TMP="$TMP" \
    ./TigersVsCows-console.exe --check
```

(Git Bash syntax.) Then start `TigersVsCows.exe` and play a game. The build bundles the Microsoft C runtime,
Python 3.13 and all libraries; NumPy carries its own copy of `msvcp140.dll`.

Results for version 1.0.0: `--check` passes in the clean environment, including MediaPipe and the camera; the game
runs in gesture and mouse mode at 60 FPS with correct Khmer text. The single `.exe`, copied alone into an empty
folder, starts in ~7 s (splash visible from the first second, replaced by the game window at ~5 s), exits cleanly
and leaves no temporary files.

## Notes

- **"Windows protected your PC"** appears for unsigned programs downloaded from the internet. Players click
  *More info → Run anyway*. Removing it requires signing the .exe with a code-signing certificate.
- **The first start takes longer** (matplotlib builds a font cache in the user profile once).
- An installer (`Setup.exe` with Start-menu shortcut and uninstaller) can be made from `dist/TigersVsCows/` with a
  tool such as Inno Setup.
