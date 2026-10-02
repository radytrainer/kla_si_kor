Khla Si Ko - Tigers vs Cows
Computer Vision Edition

Two players, one webcam, no mouse: point with your index finger to move your
cursor, pinch thumb and index finger to play.

----------------------------------------------------------------------------
START
----------------------------------------------------------------------------
Double-click  TigersVsCows.exe

No Python or other software is needed. Windows 10/11, 64-bit.
The very first start takes longer (up to a minute) while components set
themselves up; later starts take a few seconds.

If Windows shows "Windows protected your PC", click "More info" and then
"Run anyway" (the program is not signed with a paid certificate).

----------------------------------------------------------------------------
PLAYERS AND CAMERA
----------------------------------------------------------------------------
- Player 1 (Tigers, blue cursor) stands on the LEFT of the camera picture,
  Player 2 (Cows, green cursor) on the RIGHT. Cows go first.
- About 1 to 1.5 m from the webcam, lit from the front.
- First time: menu > CALIBRATE CAMERA, then pinch four corners of a
  comfortable square in front of you (top-left, top-right, bottom-right,
  bottom-left).

Gestures:  point = move cursor   pinch = select   fist = cancel / back
           open palm (1 second) = pause

No webcam? Menu > SETTINGS > Controls: Mouse.
Keys (optional): ESC = pause/back, F11 = fullscreen.

----------------------------------------------------------------------------
PROBLEMS
----------------------------------------------------------------------------
Run  TigersVsCows-console.exe --check   in a command window: it tests the
camera and every component.

- "Camera not available": close Zoom/Teams/Camera; allow camera access in
  Windows Settings > Privacy & security > Camera > desktop apps.
- "Picture is black": open the webcam's privacy shutter / cover, or add
  light. In the dark, webcams also slow down to about 1 picture per second.
- Pinches missed or too sensitive: SETTINGS > Pinch sensitivity.

Settings, calibration and crash.log are stored in:
  %LOCALAPPDATA%\TigersVsCows
Delete that folder to reset everything.

Hand-tracking model: Google MediaPipe (Apache License 2.0).
