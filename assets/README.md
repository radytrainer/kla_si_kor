# Assets

All assets are optional; the game falls back to drawn shapes, system fonts and silence.

| Folder     | Contents                                                                 |
| --- | --- |
| `fonts/`   | Optional Khmer font (file name containing `khmer`, `battambang` or `hanuman`). |
| `sounds/`  | Optional `<name>.wav`/`.ogg`: menu_click, piece_select, piece_move, cow_place, tiger_capture, invalid_move, turn_change, victory, game_over. Missing ones are generated. |
| `models/`  | MediaPipe `hand_landmarker.task` model (added in Phase 6).               |
| `tiger.png`, `cow.png`, `background.png` | Optional piece/background images.            |
