# Testing report

Status at the end of development (Phase 15 final testing, Phase 16 documentation).

## Summary

| | |
| --- | --- |
| Automated tests | **303**, all passing (about 2 minutes) |
| Code coverage | **96 %** of 4,262 statements |
| Fresh install | New venv from `requirements.txt` alone: all tests pass (271 at the time of the check) |
| Windows program | `TigersVsCows.exe` passes `--check` and runs in a Python-free environment ([Building](BUILDING.md)) |
| Static checks | `pyflakes` and `pycodestyle` (100-character lines): clean |
| Crash testing | 25,000 random UI inputs: no crash |
| Rules stress | 20,000 random complete games: no rule violation |
| Performance | 60 FPS UI with the live webcam; hand tracking keeps up with the camera |

## Running the tests

```bat
venv\Scripts\activate
python -m unittest discover -s tests -t . -v
```

No webcam, window, speaker or saved files are used: `tests/__init__.py` selects SDL's dummy video and audio
drivers and points `TIGER_COW_DATA_DIR` at a temporary folder. The camera and hand detector are replaced by
fakes (`tests/fake_camera.py`), and synthetic hands with realistic geometry come from `tests/hand_factory.py`.
Tests that need the real MediaPipe model use MediaPipe's public sample photo (`tests/data/woman_hands.jpg`) and
are skipped if the model file is missing.

Optional tools used during development (not in `requirements.txt`): `pip install coverage pyflakes pycodestyle`.

```bat
python -m coverage run --source=app,audio,camera,game,ui,vision,config,main -m unittest discover -s tests -t .
python -m coverage report
```

## What is tested

| Area | Tests | Highlights |
| --- | --- | --- |
| Game rules | 64 | Initial board; placement; valid/invalid moves for both sides; every rejection reason; captures in all directions; no jumping Tigers; no landing on occupied cells; turn switching; phase change after the 12th Cow; passing; both win conditions; restart; statistics; 200 random full games with invariants (`test_board`, `test_movement`, `test_capture`, `test_win_conditions`, `test_game_engine`) |
| Architecture | 4 | Layer boundaries (`test_architecture`) |
| Camera | 11 | Frames, mirroring, unavailable camera, driver exceptions, disconnect and reconnect, late camera, stop/restart, black picture detection (`test_camera`) |
| Hand detection | 9 | Real MediaPipe on the sample photo: 2 hands, 21 landmarks, handedness, mirroring, blank image, repeated timestamps, missing model (`test_hand_detector`) |
| Vision pipeline | 8 | Results, player data, exactly-once event delivery, stale events discarded, errors (`test_vision_pipeline`) |
| Player tracking | 22 | Side assignment, stable identity, reaching across, hands crossing, dropouts, grace time, recovery after a fast move, extra hands, a real-MediaPipe midline crossing (`test_player_tracker`) |
| Gestures | 31 | Poses; scale-free pinch; hysteresis; hold time; one pinch = one action; noisy frames; cooldown; position look-back and its drift limit; fist ≠ pinch; open palm; smoothing; relaxed hands on the real photo (`test_gestures`) |
| Board mapping | 9 | Homography, every cell centre, perspective (tilted) areas, invalid corners (`test_coordinate_mapper`) |
| Cursors & gestures in the game | 19 | Cursors on cells, active/locked, a pinch plays once, locked player refused, off-board pinch, fist cancels, pause by open palm, camera loss mid-game, tracking error with mouse fallback, black-picture warning, full games by gestures (`test_cursors`, `test_gesture_game`) |
| Touchless flow & calibration | 22 | Menu by pinch, fist never quits, ready check and countdown, play again, mouse mode skips the ready check, calibration (save, grid, wrong order, too small, reset), calibration file (`test_touchless`) |
| UI & mouse game | 25 | Layout, hit-testing, translations (complete, placeholders match), menu navigation, pause, full games by mouse (`test_ui`, `test_mouse_game`) |
| Settings | 17 | Defaults, save/load, invalid values, command-line overrides not saved, live application of every setting, F11 and unsupported fullscreen (`test_settings`) |
| Animations & sound | 18 | Easing, each animation, the exact sound for every outcome, generated and file-based sounds, no audio device (`test_animations_sound`) |
| Start-up & diagnostics | 18 | `--check`, crash log, `--download-model` failure, invalid config, dependency detection including broken installs, system-check and camera-check screens (`test_project_setup`, `test_diagnostics_screens`) |
| **End to end** | 1 | A complete two-player touchless session through the real threads, with smoothly moving scripted hands: menu → ready → place → refused out-of-turn pinch → capture → win → play again (`test_end_to_end`) |
| **Monkey** | 1 | 5,000 random mouse/key/gesture/screen/setting inputs with random hands; no crash, consistent game state (`test_monkey`) |

## Final-testing results (Phase 15)

| Check | Result |
| --- | --- |
| Coverage | 92 % → 96 % after adding tests for the weakest areas |
| Fresh install | Exactly 4 packages, `pip check` clean, all tests pass |
| Monkey stress (one-off) | 25,000 random inputs over 10 seeds: no crash. Time per input flat (~5 ms) over 8,000 inputs and 81 app restarts. |
| End-to-end session | 4 of 4 runs passed (~25 s each) |
| Engine stress (one-off) | 20,000 random games: every game ended, piece counts always consistent, every winner matched the win rule, every history replay reproduced the final board. Tigers won 82 %, Cows 18 % (random play); median 162 moves; the Cow-pass rule occurred 5,706 times. |
| Soak (real webcam) | UI 60 FPS; tracking FPS equals camera FPS (30, or 15 when the webcam lowers its rate); 4 threads, stable |
| Memory | Python heap flat (1.2 MB traced after 2 minutes of play) |

### Bugs found by testing and fixed

These are the notable defects that tests caught during development, all fixed with a regression test:

| Phase | Defect |
| --- | --- |
| 1 → 5 | Uninstalling a duplicate OpenCV package left an empty `cv2`; the environment check reported "OK" because it only tested the import. The check now verifies OpenCV really works. |
| 3 | "Tigers trapped" could be judged before the turn passed to the Tigers |
| 8 | Initial pinch thresholds were above a relaxed open hand (measured 0.38–0.47): a relaxed hand could pinch, and a pinch could never be released |
| 10 | Quick move-then-pinch hit the previous cell (position look-back too far) |
| 10 | A player reaching across the middle could be lost permanently after a tracking dropout |
| 11 | A fist on the main menu quit the game; PLAY AGAIN in mouse mode waited for pinches with the camera off |
| 14 | Command-line options (e.g. `--input mouse`) were saved permanently |
| 15 | F11 on a driver that cannot toggle fullscreen crashed pygame (access violation) |
| 15 | The Camera Check "Last actions" log stopped recording gestures |

## Known issues and observations

| Observation | Assessment |
| --- | --- |
| When the camera starts, the UI pauses for ~1 s while MediaPipe loads | One-time; MediaPipe holds Python's interpreter lock while loading |
| Some webcams deliver 15 instead of 30 FPS in dim light or for the first seconds | Camera hardware (auto-exposure). Tracking keeps up with whatever the camera delivers. Better light helps. |
| Once, tracking stayed near 0 FPS for 3 minutes | **Explained later:** the webcam was delivering black frames at ~1 FPS (privacy shutter closed or no light). The game now warns *"Picture is black"* in `--check`, Camera Check and the game screen. |
| Process memory rose ~11 MB over 4.5 minutes (not steadily) | Not in Python code (heap flat). Likely native allocations (MediaPipe, NumPy, graphics driver). Worth watching in hour-long sessions. |
| `DEBUG_MODE` is `True` by default | Shows the FPS counter; switch off in Settings or `config.py` |
| No draw rule | By design (see [Game rules](GAME_RULES.md#rule-clarifications)) |
| The Khmer translation has not been reviewed by a native speaker | Fixes need only `ui/text.py` |

## Manual test checklist (real players)

Automated tests use scripted hands. These need real people in front of a webcam; tick them off after a session.

**Setup**

- [ ] `python main.py --check` is all OK on the target computer
- [ ] Both players fit in the camera picture, lit from the front

**Gestures**

- [ ] Pointing moves the cursor smoothly; it is steady when the hand is still
- [ ] A pinch registers every time (10 of 10); CAMERA CHECK pinch meter: relaxed hand grey, pinch green
- [ ] No accidental pinches while just pointing for a minute
- [ ] Holding a pinch gives exactly one action
- [ ] A fist cancels a selection; an open palm (thumb spread, held still 1.5 s) pauses; a relaxed or moving open hand does not

**Two players**

- [ ] Left person = Player 1 (blue), right person = Player 2 (green)
- [ ] Reaching across the middle keeps the right player
- [ ] A pinch by the player who is not on turn is refused

**Calibration**

- [ ] Pinching four corners of a comfortable square works; the grid covers it
- [ ] All 16 cells can be reached comfortably after calibration

**Full game**

- [ ] Menu → ready check (both pinch) → countdown → a complete game → results → play again, without the mouse
- [ ] Sounds are audible and pleasant at the chosen volume
- [ ] Khmer interface reviewed by a native speaker
- [ ] A 30-minute session stays smooth
