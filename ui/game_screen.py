"""In-game screen: turns pointer input into GameEvents and renders the engine state.

The screen owns no rules. It converts a pointer position into a board cell,
sends a :class:`GameEvent` to the :class:`GameEngine`, and draws whatever state
the engine reports.

In GESTURE mode each player's index fingertip is mapped onto the board by the
:class:`BoardCoordinateMapper` and shown as a cursor (🔵 P1, 🟢 P2). The mouse
keeps working as a fallback.

In one-hand play a single hand plays both sides: only one cursor is shown and
every gesture acts for the side whose turn it is (like the mouse, hot-seat).

Against the computer, every hand (and the mouse) plays the person's side, and
the screen plays the computer's turns: a short "thinking" pause, then it picks
up its piece and moves it, so the person can follow what happened.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pygame

import config
from game.ai import ComputerPlayer
from game.cell import Cell
from game.events import Action, GameEvent
from game.game_engine import ActionResult, GameEngine
from game.state import Phase, Side
from audio.sound_manager import SoundEffect
from game.game_engine import Outcome
from game.piece import Piece
from ui.animations import BoardAnimator, animation_for
from ui.board_renderer import BoardRenderer, BoardView
from ui.cursor_renderer import CursorRenderer, PlayerCursor
from ui.layout import GameLayout
from ui.move_text import describe_record
from ui.player_column import PlayerColumn
from ui.screen import Screen, ScreenId, UiContext
from ui.status_panel import StatusInfo, StatusPanel
from ui.toast import Toast
from ui.touchless_screen import camera_to_window, draw_pointers
from ui.widgets import Button, draw_background
from vision.coordinate_mapper import BoardCoordinateMapper
from vision.gesture_detector import GestureAction, GestureEvent, GestureState
from vision.pipeline import PipelineStatus, VisionPipeline


PAUSE_SHADE_ALPHA = 200
PAUSE_GAP = 24

OUTCOME_SOUNDS: dict[Outcome, SoundEffect] = {
    Outcome.PLACED: SoundEffect.COW_PLACE,
    Outcome.SELECTED: SoundEffect.PIECE_SELECT,
    Outcome.DESELECTED: SoundEffect.MENU_CLICK,
    Outcome.MOVED: SoundEffect.PIECE_MOVE,
    Outcome.CAPTURED: SoundEffect.TIGER_CAPTURE,
    Outcome.REJECTED: SoundEffect.INVALID_MOVE,
}


class GameScreen(Screen):
    """Shows the board and side panel; forwards selections to the engine."""

    def __init__(self, ctx: UiContext, engine: GameEngine, pipeline: VisionPipeline,
                 mapper: BoardCoordinateMapper) -> None:
        super().__init__(ctx)
        self._engine = engine
        self._pipeline = pipeline
        self._mapper = mapper
        self._cursor_renderer = CursorRenderer(ctx.fonts)
        self._player_column = PlayerColumn(ctx.fonts, ctx.sprites, ctx.tr)
        self._cursors: dict[int, PlayerCursor] = {}
        self._flash: tuple[Cell, config.Color] | None = None
        self._flash_remaining = 0.0
        self._animator = BoardAnimator()
        self._clock = 0.0  # Seconds on this screen (drives the selection pulse).
        self._turn_flash = 0.0  # Remaining banner-flash time after a turn change.
        self._turn_change_pending = False  # Flash + sound once the move animation ends.
        self._paused = False
        self._pause_buttons = self._make_pause_buttons()
        self._layout = GameLayout.for_size(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        self._board_renderer = BoardRenderer(ctx.fonts, ctx.sprites)
        self._status_panel = StatusPanel(ctx.fonts, ctx.sprites, ctx.tr)
        self._toast = Toast()
        self._hover: Cell | None = None
        self._game_over_elapsed = 0.0
        self._computer: ComputerPlayer | None = None
        self._computer_wait = 0.0  # Seconds the computer has been "thinking".
        self._computer_target: Cell | None = None  # Where its picked-up piece goes.

    @property
    def gesture_mode(self) -> bool:
        return self.ctx.input_mode == config.INPUT_MODE_GESTURE

    @property
    def one_hand(self) -> bool:
        """One player controls both sides with a single hand."""
        return self.gesture_mode and self.ctx.one_hand

    @property
    def human_player(self) -> int:
        """The person's player number against the computer."""
        return self._engine.player_of_side(Side[self.ctx.human_side])

    @property
    def computer_player(self) -> int | None:
        """The computer's player number, or None when two people play."""
        return 3 - self.human_player if self._computer is not None else None

    @property
    def computer_turn(self) -> bool:
        return (self.computer_player == self._engine.current_player
                and not self._engine.state.game_over)

    def _player_for_input(self, player: int) -> int:
        """Who a pinch/click acts for: the person against the computer, otherwise the
        side on turn in one-hand play; otherwise the hand's own player."""
        if self._computer is not None:
            return self.human_player
        if self.one_hand:
            return self._engine.current_player
        return player

    @property
    def uses_vision(self) -> bool:
        return self.gesture_mode

    # ----------------------------------------------------------------- input
    def on_enter(self) -> None:
        """Entering the screen always starts a new game."""
        self._engine.reset_game()
        self._hover = None
        self._cursors = {}
        self._flash = None
        self._animator.clear()
        self._turn_flash = 0.0
        self._turn_change_pending = False
        self._paused = False
        self._pipeline.drain_events()  # Gestures made before the game started are void.
        self._toast.clear()
        self._game_over_elapsed = 0.0
        self._computer = (ComputerPlayer(self.ctx.computer_level) if self.ctx.vs_computer
                          else None)
        self._computer_wait = 0.0
        self._computer_target = None

    # ----------------------------------------------------------------- pause
    @property
    def paused(self) -> bool:
        return self._paused

    def _make_pause_buttons(self) -> list[Button]:
        rect = pygame.Rect(0, 0, config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        rect.center = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT // 2)
        menu_rect = rect.move(0, config.BUTTON_HEIGHT + config.BUTTON_SPACING)
        return [Button(rect, lambda: self.ctx.tr("pause.resume"), self.resume),
                Button(menu_rect, lambda: self.ctx.tr("gameover.menu"),
                       lambda: self.ctx.navigate(ScreenId.MENU))]

    def pause(self) -> None:
        if not self._engine.state.game_over:
            self._paused = True

    def resume(self) -> None:
        self._paused = False

    def on_back(self) -> None:
        """ESC: pause / resume (leaving the game is a button on the pause screen)."""
        if self._engine.state.game_over:
            self.ctx.navigate(ScreenId.MENU)
        elif self._paused:
            self.resume()
        else:
            self.pause()

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        if self._paused:
            for button in self._pause_buttons:
                button.update_hover(pos)
            return
        self._hover = self._board_renderer.cell_at(self._layout.board, pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        if self._paused:
            for button in self._pause_buttons:
                if button.try_click(pos):
                    return
            return
        # Mouse mode is hot-seat: the mouse acts for the player on turn (or the person).
        self.select_as(self._player_for_input(self._engine.current_player), pos)

    def on_cancel(self) -> None:
        if self._paused:
            self.resume()
            return
        self.submit(GameEvent(self._player_for_input(self._engine.current_player),
                              Action.CANCEL))

    def select_as(self, player: int, pos: tuple[int, int]) -> None:
        """Player ``player`` confirmed at screen position ``pos``."""
        cell = self._board_renderer.cell_at(self._layout.board, pos)
        if cell is not None:
            self.submit(GameEvent(player, Action.SELECT, cell))

    def submit(self, event: GameEvent, from_gesture: bool = False) -> ActionResult | None:
        """Send an event to the engine and show feedback."""
        if self._engine.state.game_over:
            return None
        side_before = self._engine.state.current_side
        result = self._engine.handle_event(event)
        # Name whose gesture was rejected, unless only one person plays.
        self._show_feedback(result, event.player if from_gesture and not self.ctx.solo
                            else None)
        self.ctx.play(OUTCOME_SOUNDS[result.outcome])
        if result.record is not None:
            state = self._engine.state
            piece = (Piece.TIGER if result.outcome is Outcome.CAPTURED
                     else state.board.get(result.record.to_cell))
            self._animator.start(animation_for(result.record, piece))
            if state.current_side is not side_before and not state.game_over:
                self._turn_change_pending = True
        if from_gesture and event.cell is not None and event.action is Action.SELECT:
            color = config.COLOR_OK if result.valid else config.COLOR_ERROR
            self._flash, self._flash_remaining = (event.cell, color), config.CELL_FLASH_DURATION
        return result

    def handle_gesture(self, gesture: GestureEvent) -> ActionResult | None:
        """Turn a confirmed gesture into a game event for that player."""
        gesture = replace(gesture, player_id=self._player_for_input(gesture.player_id))
        if self._paused:
            self._handle_paused_gesture(gesture)
            return None
        if gesture.action is GestureAction.MENU:  # ✋ open palm held: pause.
            self.pause()
            return None
        if gesture.action is GestureAction.SELECT:
            cell = self._mapper.cell_at(gesture.position) if gesture.position else None
            event = GameEvent(gesture.player_id, Action.SELECT,
                              Cell(*cell) if cell is not None else None)
        else:
            event = GameEvent(gesture.player_id, Action.CANCEL)
        return self.submit(event, from_gesture=True)

    def _handle_paused_gesture(self, gesture: GestureEvent) -> None:
        """On the pause screen a pinch presses a button and a fist resumes."""
        if gesture.action is GestureAction.CANCEL:
            self.resume()
        elif gesture.action is GestureAction.SELECT and gesture.position is not None:
            pos = camera_to_window(gesture.position)
            for button in self._pause_buttons:
                if button.try_click(pos):
                    return

    def _show_feedback(self, result: ActionResult, player: int | None = None) -> None:
        if not result.valid:
            code = result.validation.code
            text = self.ctx.tr.lookup(f"reason.{code}") or result.reason
            if player is not None:  # Say whose gesture was rejected.
                text = self.ctx.tr("gesture.player_prefix", number=player, message=text)
            self._toast.show(text, config.COLOR_ERROR)
        elif result.record is not None:
            state = self._engine.state
            if state.game_over:
                key = "gameover.tiger_wins" if state.winner is Side.TIGER else "gameover.cow_wins"
                self._toast.show(self.ctx.tr(key), config.COLOR_SELECTED)
            else:
                self._toast.show(describe_record(result.record, self.ctx.tr), config.COLOR_OK)

    # ---------------------------------------------------------------- update
    def update(self, dt: float) -> None:
        self._toast.update(dt)
        self._flash_remaining = max(0.0, self._flash_remaining - dt)
        self._clock += dt
        self._animator.update(dt)
        self._turn_flash = max(0.0, self._turn_flash - dt)
        if self._turn_change_pending and not self._animator.busy:
            self._turn_change_pending = False
            self._turn_flash = config.TURN_FLASH_TIME
            self.ctx.play(SoundEffect.TURN_CHANGE)
        self._update_computer(dt)
        if self.gesture_mode:
            self._cursors = self._build_cursors()
            for gesture in self._pipeline.drain_events():
                self.handle_gesture(gesture)
        if self._engine.state.game_over:
            self._game_over_elapsed += dt
            if self._game_over_elapsed >= config.GAME_OVER_DELAY:
                self.ctx.navigate(ScreenId.GAME_OVER)

    # -------------------------------------------------------------- computer
    def _update_computer(self, dt: float) -> None:
        """Play the computer's turn: think, pick up the piece, then move it."""
        if self._computer is None or self._paused or self._engine.state.game_over:
            return
        if not self.computer_turn:
            self._computer_wait, self._computer_target = 0.0, None
            return
        if self._animator.busy:  # Let the person see the last move land first.
            return
        self._computer_wait += dt
        player = self.computer_player
        if self._computer_target is not None:
            if self._computer_wait >= config.COMPUTER_STEP_TIME:
                target, self._computer_target = self._computer_target, None
                self._computer_wait = 0.0
                self.submit(GameEvent(player, Action.SELECT, target))
            return
        if self._computer_wait < config.COMPUTER_THINK_TIME:
            return
        self._computer_wait = 0.0
        move = self._computer.choose_move(self._engine.state)
        if move is None:
            return
        self.submit(GameEvent(player, Action.SELECT, move.from_cell))  # Place, or pick up.
        if move.from_cell != move.to_cell:
            self._computer_target = move.to_cell

    # --------------------------------------------------------------- cursors
    def _build_cursors(self) -> dict[int, PlayerCursor]:
        """Map each player's smoothed fingertip onto the board and the screen."""
        result = self._pipeline.latest_result()
        if result is None:
            return {}
        grid = BoardRenderer.grid_rect(self._layout.board)
        screen = pygame.Rect(0, 0, config.WINDOW_WIDTH, config.WINDOW_HEIGHT)
        gestures = result.gestures
        if self.ctx.solo:
            gestures = self._solo_gestures(gestures)
        cursors = {}
        for gesture in gestures:
            if gesture.cursor is None:
                continue
            u, v = self._mapper.camera_to_board(gesture.cursor)
            x = min(max(round(grid.left + u * grid.width), screen.left), screen.right - 1)
            y = min(max(round(grid.top + v * grid.height), screen.top), screen.bottom - 1)
            cell = self._mapper.cell_at(gesture.cursor)
            cursors[gesture.player_id] = PlayerCursor(
                player_id=gesture.player_id,
                position=(x, y),
                cell=cell,
                cell_name=Cell(*cell).name if cell is not None else None,
                active=gesture.player_id == self._engine.current_player
                and not self._engine.state.game_over,
                tracked=gesture.tracked,
                gesture=gesture,
            )
        return cursors

    def _solo_gestures(self, gestures: tuple[GestureState, ...]) -> tuple[GestureState, ...]:
        """The one person's hand, relabelled as the player it acts for."""
        visible = [g for g in gestures if g.cursor is not None]
        if not visible:
            return ()
        hand = max(visible, key=lambda g: g.tracked)  # Prefer a hand seen this frame.
        return (replace(hand, player_id=self._player_for_input(hand.player_id)),)

    def _active_cursor_cell(self) -> Cell | None:
        cursor = self._cursors.get(self._engine.current_player)
        if cursor is None or not cursor.tracked or cursor.cell is None:
            return None
        return Cell(*cursor.cell)

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        state = self._engine.state
        draw_background(surface)
        self.draw_compact_header(surface, self._layout.header)
        hover = self._active_cursor_cell() or self._hover
        view = BoardView(
            pieces=state.board.rows_view(),
            hover=hover if not state.game_over else None,
            selected=state.selected,
            legal_targets=self._engine.legal_targets(),
            hidden=self._animator.hidden_cells(),
            selected_scale=1.0 + config.SELECT_PULSE_AMOUNT * math.sin(
                self._clock * config.SELECT_PULSE_SPEED),
        )
        self._board_renderer.draw(surface, self._layout.board, view)
        for frame in self._animator.frames():
            self._board_renderer.draw_sprite_frame(surface, self._layout.board, frame)
        if self._flash is not None and self._flash_remaining > 0:
            alpha = round(config.CELL_FLASH_MAX_ALPHA * self._flash_remaining
                          / config.CELL_FLASH_DURATION)
            BoardRenderer.draw_cell_flash(surface, self._layout.board, *self._flash, alpha)
        self._status_panel.draw(surface, self._layout.side_panel, self._status_info())
        # Centre the message on the board's bottom frame so it hides little of row 4.
        board = self._layout.board
        self._toast.draw(surface, self.ctx.fonts,
                         (board.centerx, board.bottom - config.BOARD_FRAME_WIDTH // 2))
        if self.gesture_mode:
            column_cursors = self._cursors
            if self.one_hand and self._computer is None and self._cursors:
                hand = next(iter(self._cursors.values()))  # One hand plays both cards.
                column_cursors = {1: hand, 2: hand}
            self._player_column.draw(surface, self._layout.camera_column,
                                     self._pipeline.latest_result(),
                                     self._pipeline.camera.status, column_cursors,
                                     self._engine.current_player, self._mapper, self.ctx.debug,
                                     tracking_error=self._pipeline.status is PipelineStatus.ERROR,
                                     computer_player=self.computer_player)
            # Locked cursor first so the active player's cursor is drawn on top.
            for cursor in sorted(self._cursors.values(), key=lambda c: c.active):
                label = f"P{cursor.player_id}" + (f" · {cursor.cell_name}"
                                                  if cursor.cell_name else "")
                self._cursor_renderer.draw(surface, cursor, label)
        if self._paused:
            self._draw_pause(surface)

    def _pause_pointers(self) -> dict[int, tuple[int, int]]:
        """Players' window pointers (the whole camera image maps onto the window)."""
        return {cursor.player_id: camera_to_window(cursor.gesture.cursor)
                for cursor in self._cursors.values()
                if cursor.tracked and cursor.gesture.cursor is not None}

    def _draw_pause(self, surface: pygame.Surface) -> None:
        shade = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        shade.fill((*config.COLOR_BACKGROUND, PAUSE_SHADE_ALPHA))
        surface.blit(shade, (0, 0))
        fonts, tr = self.ctx.fonts, self.ctx.tr
        center_x = surface.get_width() // 2
        title = fonts.render(tr("pause.title"), config.FONT_SIZE_HUGE, config.COLOR_TIGER,
                             bold=True)
        top_button = self._pause_buttons[0].rect
        surface.blit(title, title.get_rect(midbottom=(center_x, top_button.top - PAUSE_GAP)))
        pointers = self._pause_pointers()
        if pointers:  # Gesture hover: the lowest-numbered visible player's pointer.
            for button in self._pause_buttons:
                button.update_hover(pointers[min(pointers)])
        for button in self._pause_buttons:
            button.draw(surface, fonts)
        hint = fonts.render(tr("pause.hint"), config.FONT_SIZE_MEDIUM, config.COLOR_TEXT)
        surface.blit(hint, hint.get_rect(midtop=(center_x,
                                                 self._pause_buttons[-1].rect.bottom + PAUSE_GAP)))
        draw_pointers(surface, pointers)

    def _status_info(self) -> StatusInfo:
        state = self._engine.state
        phase_key = {
            Phase.COW_PLACEMENT: "phase.placement",
            Phase.MOVEMENT: "phase.movement",
            Phase.GAME_OVER: "phase.game_over",
        }[state.phase]
        recent = state.move_history[-config.HISTORY_VISIBLE_MOVES:]
        return StatusInfo(
            tiger_turn=state.current_side is Side.TIGER,
            phase_key=phase_key,
            tigers=state.tigers_on_board,
            cows_on_board=state.cows_on_board,
            cows_to_place=state.cows_to_place,
            cows_captured=state.cows_captured,
            hint_key=self._hint_key(),
            recent_moves=tuple(f"{r.number:02d}. {describe_record(r, self.ctx.tr)}"
                               for r in recent),
            winner_is_tiger=None if state.winner is None else state.winner is Side.TIGER,
            turn_flash=self._turn_flash / config.TURN_FLASH_TIME,
            computer_player=self.computer_player,
        )

    def _hint_key(self) -> str:
        state = self._engine.state
        if state.game_over:
            return "hint.game_over"
        if self.computer_turn:
            return "hint.computer"
        mode = "gesture" if self.ctx.input_mode == config.INPUT_MODE_GESTURE else "mouse"
        if state.current_side is Side.COW and state.phase is Phase.COW_PLACEMENT:
            situation = "place"
        elif state.selected is not None:
            situation = "move"
        else:
            situation = "select_tiger" if state.current_side is Side.TIGER else "select_cow"
        return f"hint.{mode}.{situation}"
