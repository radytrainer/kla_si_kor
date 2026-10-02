# Game rules: ខ្លាស៊ីគោ (Tigers vs Cows)

A traditional Khmer strategy game for two players. One player controls **4 Tigers** 🐯, the other
**12 Cows** 🐄. The Tigers try to eat every Cow; the Cows try to trap the Tigers so they cannot move.

## The board

A 4 × 4 grid. Columns are named **A–D** (left to right) and rows **1–4** (top to bottom), so every cell has a
name like **B2**. Move history and messages use these names.

```text
      A    B    C    D
 1   🐯   ·    ·    🐯
 2   ·    ·    ·    ·
 3   ·    ·    ·    ·
 4   🐯   ·    ·    🐯
```

The Tigers start in the four corners (A1, D1, A4, D4). The Cows start off the board.

| Player | Side | Stands | Cursor |
| --- | --- | --- | --- |
| Player 1 | 🐯 Tigers | left of the camera | 🔵 blue |
| Player 2 | 🐄 Cows | right of the camera | 🟢 green |

## Phase 1: Cow placement

**The Cows go first.**

1. The Cow player places **one** Cow on any empty cell.
2. The Tiger player makes one move: a step or a capture (see below).
3. Repeat until all **12** Cows have been placed.

While Cows are still being placed, the Cows on the board **cannot move**; each Cow turn is a placement.
Tigers may move and capture as normal.

## Phase 2: Movement

It starts automatically once the 12th Cow is placed, with the Tigers to move. Players then alternate, each
moving one of their own pieces.

### Moving

Every piece moves **one cell up, down, left or right** onto an **empty** cell.

- No diagonal moves.
- No moving more than one cell (except a Tiger's capture jump).
- No moving onto an occupied cell.

### Capturing (Tigers only)

A Tiger captures a Cow by **jumping over it**:

1. The Cow is **directly next to** the Tiger (up, down, left or right).
2. The cell **immediately beyond** the Cow, in the same straight line, is **empty**.
3. The Tiger lands on that cell and the Cow is removed.

```text
Before:  🐯 🐄 ·        After:  · · 🐯        (the Cow is eaten)
```

Vertically:

```text
Before:  🐯        After:  ·
         🐄                ·
         ·                 🐯
```

Not allowed:

| Situation | Why |
| --- | --- |
| 🐯 🐯 · | A Tiger can never jump over another Tiger |
| 🐯 🐄 🐄 | The landing cell must be empty |
| 🐯 · 🐄 | Only a Cow directly next to the Tiger can be jumped |
| diagonal jump | Captures are horizontal or vertical only |

Cows **never** capture and **never** jump.

## Winning

| Winner | When |
| --- | --- |
| 🐯 **Tigers win** | All **12** Cows have been captured |
| 🐄 **Cows win** | It is the Tigers' turn and **no Tiger has a legal move** (no step and no capture) |

When the game ends, the final board stays on screen for 2 seconds, then the results screen shows the winner and the
statistics: duration, total moves, Cows captured, Tiger moves, Cow moves, Cows placed.

## Rule clarifications

The traditional rules leave a few situations open. This version decides them as follows:

| Situation | Decision |
| --- | --- |
| When is "Tigers trapped" checked? | Whenever it becomes the Tigers' turn, in **either** phase. For example, placing the 12th Cow without any capture fills the whole board, so the Cows win immediately. |
| The Cows cannot move (movement phase) | The Cows **pass** their turn (shown as *"turn passed"* in the history). A Tiger can always move then, so the game never freezes. |
| Is capturing compulsory? | **No.** A Tiger may step instead of capturing. |
| Multiple jumps in one turn? | **No.** One capture per turn. |
| When do Tigers win? | Only after **12 captures**, so every Cow must first be placed and then eaten. Clearing the board while Cows are still waiting to be placed is not a win. |
| Endless back-and-forth moves | There is **no draw rule**. Players can simply start a new game. |

## How your actions are interpreted

Every selection (a pinch or a click) is interpreted by the game depending on the situation:

| Situation | Selecting a cell… |
| --- | --- |
| Cows' turn during placement | places a Cow there (if empty) |
| Nothing selected | selects your piece there (it must have a legal move) |
| Your own piece already selected, same cell | deselects it |
| Your own piece selected, another of your pieces | switches the selection |
| Your own piece selected, any other cell | moves there, if legal (green dot) |

✊ A fist (or a right-click) cancels the selection. Illegal actions are refused with a short reason,
for example *"Tiger cannot move diagonally"* or *"It is not your turn"*; nothing changes on the board.
