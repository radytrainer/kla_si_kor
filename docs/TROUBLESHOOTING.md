# Troubleshooting

Start with the built-in check. It tests Python, every package, the hand model and the camera:

```bat
venv\Scripts\activate
python main.py --check
```

The game is built so that problems never crash it: if the camera or hand tracking fails, a message explains what
is wrong and **the mouse always works** as a fallback.

## Installation

| Problem | Cause | Fix |
| --- | --- | --- |
| `python` is not recognised | Python is not on PATH | Reinstall Python and tick *"Add python.exe to PATH"*, or use the full path to `python.exe` |
| PowerShell: *running scripts is disabled* (when activating) | Windows script policy | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or use Command Prompt |
| *Unsupported Python version* | Python older than 3.11 | Install Python 3.11 or newer and recreate the venv |
| *Could not start: No module named …* | Packages not installed, or venv not active | Activate the venv (`venv\Scripts\activate`), then `pip install -r requirements.txt` |
| `--check` shows **OpenCV: broken install** | Two OpenCV packages overwrote each other's files | `pip uninstall -y opencv-python opencv-contrib-python`, then `pip install opencv-contrib-python` |
| Khmer text shows as broken, disconnected letters | Plain `pygame` installed instead of `pygame-ce` | `pip uninstall -y pygame`, then `pip install pygame-ce` |
| *Khmer font* is red on the system-check screen | No Khmer font found (Windows normally has *Khmer UI*) | Put a Khmer `.ttf` whose name contains `khmer`, `battambang` or `hanuman` in `assets/fonts/` |

## Camera

| Problem | Fix |
| --- | --- |
| *Camera not available* | Close apps that use the camera (Zoom, Teams, Camera, browser tabs). Check **Settings → Privacy & security → Camera → Let desktop apps access your camera**. The game retries by itself every 2 seconds. |
| *Camera disconnected* | Reconnect the webcam; the game reconnects automatically |
| The wrong webcam is used | SETTINGS → **Camera: 0 / 1 / 2** |
| *Picture is black* / tracking stops, camera at ~1 FPS | The webcam's privacy shutter or cover is closed, or the room is dark. In darkness webcams slow to about 1 picture per second. Open the shutter or add light. |
| Picture is dark or tracking is jumpy | Light the players from the front; avoid a window behind them. Some webcams drop from 30 to 15 FPS in dim light (CAMERA CHECK shows the camera's FPS). |
| Camera takes a second to start; the game pauses briefly | Normal: the hand-tracking model loads when the camera starts (about 1 second) |

## Hand tracking

| Problem | Fix |
| --- | --- |
| *Hand tracking unavailable* / *Hand model not found* | `python main.py --download-model`, or download `hand_landmarker.task` and put it in `assets/models/` |
| Hands not detected | Show the whole hand, palm towards the camera, 1–1.5 m away, in good light |
| Players are swapped | Player 1 must stand on the **left** of the picture and Player 2 on the **right** when their hands first appear. To swap: hide both hands for a second and show them again from the correct sides. |
| One player's second hand steals control | Use one hand per player; lower the other hand |
| Cursor is shaky | SETTINGS → Cursor smoothing: **High** |
| Cursor feels slow | SETTINGS → Cursor smoothing: **Low** |
| Hard to reach some cells / cursor leaves the board | Recalibrate (CALIBRATE CAMERA) with a square you can reach comfortably |

## Gestures

| Problem | Fix |
| --- | --- |
| Pinches are missed | Hold the pinch a little longer (¼ second) and keep still while pinching. SETTINGS → Pinch sensitivity: **High**. |
| Pinches fire by accident | SETTINGS → Pinch sensitivity: **Low**. Keep your thumb away from your index finger while pointing. |
| A pinch selects the neighbouring cell | Point, pause briefly, then pinch; don't move while closing your fingers |
| "Nothing happens" when pinching | Is it your turn? Your cursor must be bright, not grey with a padlock. Is your pointer on the board? Is the game paused? |
| Game paused by itself | A spread open palm (thumb out) held still for 1.5 seconds pauses the game. Keep a resting hand relaxed or move it out of view. Make a fist to resume. |
| To see exactly what the game recognises | CALIBRATE CAMERA → **CAMERA CHECK**: live skeletons, each player's gesture, the pinch meter and a log of recognised gestures |

## Display and sound

| Problem | Fix |
| --- | --- |
| Window too big or small | Resize it; the game scales. Or press **F11** for fullscreen. |
| F11 does nothing | Some graphics drivers cannot switch while running; start with `python main.py --fullscreen` instead |
| No sound | SETTINGS → Sound: On and Volume above 0; check that you did not start with `--mute`. Without an audio device the game is silent by design. |
| Replace the sounds | Put `.wav` or `.ogg` files named `menu_click`, `piece_select`, `piece_move`, `cow_place`, `tiger_capture`, `invalid_move`, `turn_change`, `victory`, `game_over` in `assets/sounds/` |
| Frame-rate counter in the corner | SETTINGS → Debug info: Off |

## Resetting

| To reset | Delete |
| --- | --- |
| All settings | `data/settings.json` |
| Calibration | `data/calibration.json` (or RESET TO DEFAULT on the calibration screen) |

Both files are recreated as needed. A damaged file is ignored automatically: the game falls back to defaults
instead of failing.

## Still stuck?

Run with the debug overlay and check the Camera Check screen, then note what `python main.py --check` prints.
MediaPipe's own start-up messages are hidden; set `DEBUG_MODE_NATIVE_LOGS = True` in `config.py` to see them.
