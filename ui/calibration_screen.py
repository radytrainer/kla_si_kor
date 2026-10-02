"""Guided four-corner board calibration using the live camera preview.

Players choose the square in front of the camera that maps onto the board:
they pinch (or click) its corners in order top-left, top-right, bottom-right,
bottom-left. Each player's fingertip is drawn on the preview so they can aim.
After the fourth corner the area is validated (order, convexity, size), saved
to data/calibration.json, applied to the shared mapper at once, and the
resulting 4×4 grid is drawn in perspective for checking.
"""

from __future__ import annotations

import math

import pygame

import config
from ui.camera_view import CameraView
from ui.hand_overlay import to_screen
from ui.player_style import PLAYER_COLORS
from ui.screen import ScreenId, UiContext
from ui.touchless_screen import TouchlessScreen
from ui.widgets import Button, draw_background, draw_panel
from vision.calibration_store import clear_corners, default_corners, save_corners
from vision.coordinate_mapper import BoardCoordinateMapper, Point, Quad
from vision.gesture_detector import GestureEvent
from vision.pipeline import VisionPipeline

CORNER_KEYS = ("calibration.tl", "calibration.tr", "calibration.br", "calibration.bl")
CORNER_COUNT = 4
TITLE_TOP = 16
PROMPT_TOP = 82
PREVIEW = pygame.Rect(40, 120, 760, 540)
PREVIEW_FRAME = 8
NOTE_GAP = 8
CORNER_RADIUS = 12
FINGERTIP_RADIUS = 9
LINE_WIDTH = 3
GRID_WIDTH = 2
SIDE_BUTTON_WIDTH = 300
SIDE_BUTTON_GAP = 16


class CalibrationScreen(TouchlessScreen):
    def __init__(self, ctx: UiContext, pipeline: VisionPipeline,
                 mapper: BoardCoordinateMapper) -> None:
        super().__init__(ctx, pipeline)
        # Every pinch here marks a corner, so pointing must not highlight the
        # (mouse-only) side buttons as if they could be pinched.
        self.gesture_hover = False
        self._mapper = mapper
        self._view = CameraView(ctx.fonts)
        self._points: list[Point] = []
        self._saved = False  # True after a successful calibration (grid shown).
        self._message = ""
        self._message_is_error = False
        actions = (("calibration.camera_check", lambda: ctx.navigate(ScreenId.CAMERA_CHECK)),
                   ("calibration.reset", self.reset_to_default),
                   ("calibration.done", lambda: ctx.navigate(ScreenId.MENU)))
        left = PREVIEW.right + config.UI_MARGIN * 2
        self._buttons = []
        step = config.BUTTON_HEIGHT + SIDE_BUTTON_GAP
        for index, (key, action) in enumerate(actions):
            rect = pygame.Rect(left, PREVIEW.top + index * step, SIDE_BUTTON_WIDTH,
                               config.BUTTON_HEIGHT)
            self._buttons.append(Button(rect, lambda key=key: ctx.tr(key), action))

    @property
    def uses_vision(self) -> bool:
        # Calibration needs a live image even when the rest of the app is in mouse mode.
        return True

    @property
    def points(self) -> list[Point]:
        return list(self._points)

    def on_enter(self) -> None:
        super().on_enter()
        self._points.clear()
        self._saved = False
        self._set_message("")

    def on_back(self) -> None:
        self.ctx.navigate(ScreenId.MENU)

    # ----------------------------------------------------------------- input
    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        for button in self._buttons:
            button.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        """Mouse: buttons, or a click on the preview adds a corner."""
        for button in self._buttons:
            if button.try_click(pos):
                return
        image = self._view.last_image_rect
        if image is not None and image.collidepoint(pos):
            self.add_point(((pos[0] - image.left) / image.width,
                            (pos[1] - image.top) / image.height))

    def on_gesture_event(self, event: GestureEvent, pos: tuple[int, int]) -> None:
        """Pinch: the pinch position in the camera image is the corner."""
        if event.position is not None:
            self.add_point(event.position)

    def add_point(self, point: Point) -> None:
        if self._saved or len(self._points) == CORNER_COUNT:
            self._points.clear()  # Pinching after a calibration starts a new one.
            self._saved = False
        self._points.append(point)
        self._set_message("")
        if len(self._points) == CORNER_COUNT:
            self._finish(tuple(self._points))  # type: ignore[arg-type]

    def _finish(self, corners: Quad) -> None:
        if min(math.dist(corners[i], corners[(i + 1) % CORNER_COUNT])
               for i in range(CORNER_COUNT)) < config.CALIBRATION_MIN_SIDE:
            self._reject("calibration.too_small")
            return
        try:
            candidate = BoardCoordinateMapper(corners)
            save_corners(candidate.corners)
        except ValueError:
            self._reject("calibration.invalid")
            return
        except OSError as exc:
            self._reject("calibration.invalid", detail=str(exc))
            return
        self._mapper.set_corners(candidate.corners)
        self._saved = True
        self._set_message(self.ctx.tr("calibration.saved"))

    def _reject(self, key: str, detail: str = "") -> None:
        self._points.clear()
        text = self.ctx.tr(key)
        self._set_message(f"{text} ({detail})" if detail else text, error=True)

    def reset_to_default(self) -> None:
        try:
            clear_corners()
        except OSError as exc:
            self._set_message(str(exc), error=True)
            return
        self._mapper.set_corners(default_corners())
        self._points.clear()
        self._saved = True  # Show the (default) grid.
        self._set_message(self.ctx.tr("calibration.reset_done"))

    def _set_message(self, text: str, error: bool = False) -> None:
        self._message, self._message_is_error = text, error

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        tr, fonts = self.ctx.tr, self.ctx.fonts
        center_x = surface.get_width() // 2
        title = fonts.render(tr("calibration.title"), config.FONT_SIZE_TITLE, config.COLOR_TIGER,
                             bold=True)
        surface.blit(title, title.get_rect(midtop=(center_x, TITLE_TOP)))
        prompt_text = (tr("calibration.complete") if self._saved
                       else tr(CORNER_KEYS[min(len(self._points), CORNER_COUNT - 1)]))
        prompt = fonts.render(prompt_text, config.FONT_SIZE_MEDIUM, config.COLOR_TEXT, bold=True)
        surface.blit(prompt, prompt.get_rect(midtop=(PREVIEW.centerx, PROMPT_TOP)))

        draw_panel(surface, PREVIEW.inflate(PREVIEW_FRAME, PREVIEW_FRAME))
        result = self._pipeline.latest_result()
        camera = self._pipeline.camera
        frame = result.frame if result is not None else camera.latest_frame()
        self._view.draw(surface, PREVIEW, frame, tr(f"camera.status.{camera.status.value}"),
                        config.COLOR_WARNING)
        image = self._view.last_image_rect
        if image is not None:
            self._draw_region(surface, image)
            if result is not None:
                for gesture in result.gestures:
                    if gesture.tracked and gesture.cursor is not None:
                        pygame.draw.circle(surface, PLAYER_COLORS[gesture.player_id],
                                           to_screen(*gesture.cursor, image), FINGERTIP_RADIUS)

        note = self._message or tr("calibration.help")
        color = config.COLOR_ERROR if self._message_is_error else (
            config.COLOR_OK if self._message else config.COLOR_TEXT_MUTED)
        side_width = surface.get_width() - PREVIEW.right - config.UI_MARGIN * 3
        y = self._buttons[-1].rect.bottom + SIDE_BUTTON_GAP
        for line in fonts.render_wrapped(note, config.FONT_SIZE_SMALL, color, side_width):
            surface.blit(line, (self._buttons[0].rect.left, y))
            y += line.get_height() + NOTE_GAP
        for button in self._buttons:
            button.draw(surface, fonts)

    def _draw_region(self, surface: pygame.Surface, image: pygame.Rect) -> None:
        if self._saved:
            self._draw_grid(surface, image)
        elif not self._points:  # Show the area in use before recalibrating.
            corners = [to_screen(x, y, image) for x, y in self._mapper.corners]
            pygame.draw.polygon(surface, config.COLOR_LOCKED, corners, GRID_WIDTH)
        picked = [to_screen(x, y, image) for x, y in self._points]
        if len(picked) >= 2:
            closed = len(picked) == CORNER_COUNT
            pygame.draw.lines(surface, config.COLOR_SELECTED, closed, picked, LINE_WIDTH)
        for number, center in enumerate(picked, start=1):
            pygame.draw.circle(surface, config.COLOR_SELECTED, center, CORNER_RADIUS)
            label = self.ctx.fonts.render(str(number), config.FONT_SIZE_SMALL,
                                          config.COLOR_BACKGROUND, bold=True)
            surface.blit(label, label.get_rect(center=center))

    def _draw_grid(self, surface: pygame.Surface, image: pygame.Rect) -> None:
        """The calibrated board's 4×4 grid, warped by the mapper's perspective."""
        rows, cols = self._mapper.rows, self._mapper.cols
        for index in range(cols + 1):
            u = index / cols
            start = to_screen(*self._mapper.board_to_camera((u, 0.0)), image)
            end = to_screen(*self._mapper.board_to_camera((u, 1.0)), image)
            pygame.draw.line(surface, config.COLOR_OK, start, end, GRID_WIDTH)
        for index in range(rows + 1):
            v = index / rows
            start = to_screen(*self._mapper.board_to_camera((0.0, v)), image)
            end = to_screen(*self._mapper.board_to_camera((1.0, v)), image)
            pygame.draw.line(surface, config.COLOR_OK, start, end, GRID_WIDTH)
