"""CAMERA CHECK screen: live preview with hand landmarks, status and troubleshooting."""

from __future__ import annotations

from collections import deque

import pygame

import config
from camera.camera import CameraStatus
from ui.camera_view import CameraView
from ui.gesture_overlay import draw_cursor, draw_pinch_meter
from ui.hand_overlay import HandOverlay, to_screen
from ui.player_style import PLAYER_COLORS, side_key
from ui.player_view import draw_player_zones, hand_styles
from ui.screen import ScreenId, UiContext
from ui.touchless_screen import TouchlessScreen
from ui.widgets import Button, draw_background, draw_panel
from vision.gesture_detector import GestureEvent
from vision.pipeline import PipelineStatus, VisionPipeline, VisionResult
from vision.player_tracker import TrackStatus

TITLE_TOP = 16
PREVIEW_TOP = 100
PREVIEW_WIDTH = 688  # 4:3, matches the camera
PREVIEW_HEIGHT = 516
PADDING = 20
DOT_RADIUS = 10
LINE_GAP = 6
SECTION_GAP = 14
EVENT_LOG_SIZE = 2
METER_HEIGHT = 12

STATUS_COLORS: dict[CameraStatus, config.Color] = {
    CameraStatus.RUNNING: config.COLOR_OK,
    CameraStatus.STARTING: config.COLOR_WARNING,
    CameraStatus.DISCONNECTED: config.COLOR_WARNING,
    CameraStatus.UNAVAILABLE: config.COLOR_ERROR,
    CameraStatus.STOPPED: config.COLOR_LOCKED,
}
HELP_KEYS = ("camera.help_connected", "camera.help_privacy", "camera.help_retry")


class CameraCheckScreen(TouchlessScreen):
    """Runs the vision pipeline while visible and shows what it sees."""

    def __init__(self, ctx: UiContext, pipeline: VisionPipeline) -> None:
        super().__init__(ctx, pipeline)
        self._pipeline = pipeline
        self._view = CameraView(ctx.fonts)
        self._overlay = HandOverlay(ctx.fonts)
        self._preview_area = pygame.Rect(config.UI_MARGIN, PREVIEW_TOP, PREVIEW_WIDTH,
                                         PREVIEW_HEIGHT)
        info_left = self._preview_area.right + config.UI_MARGIN
        self._info_area = pygame.Rect(info_left, PREVIEW_TOP,
                                      config.WINDOW_WIDTH - info_left - config.UI_MARGIN,
                                      PREVIEW_HEIGHT)
        back = pygame.Rect(0, 0, config.BUTTON_WIDTH, config.BUTTON_HEIGHT)
        back.midbottom = (config.WINDOW_WIDTH // 2, config.WINDOW_HEIGHT - config.UI_MARGIN)
        self._back = Button(back, lambda: ctx.tr("common.back"),
                            lambda: ctx.navigate(ScreenId.CALIBRATION))
        self._events: deque[GestureEvent] = deque(maxlen=EVENT_LOG_SIZE)
        self.accept_multiple_gestures = True  # Log both players' pinches.

    def on_enter(self) -> None:
        super().on_enter()
        self._events.clear()

    def on_any_gesture(self, event: GestureEvent) -> None:
        """Every gesture goes into the "Last actions" log (pinch testing)."""
        self._events.append(event)

    def on_back(self) -> None:
        self.ctx.navigate(ScreenId.CALIBRATION)  # Camera Check is opened from calibration.

    def on_pointer_move(self, pos: tuple[int, int]) -> None:
        self._back.update_hover(pos)

    def on_select(self, pos: tuple[int, int]) -> None:
        self._back.try_click(pos)

    # ------------------------------------------------------------------ draw
    def draw(self, surface: pygame.Surface) -> None:
        draw_background(surface)
        tr, fonts = self.ctx.tr, self.ctx.fonts
        title = fonts.render(tr("camera.title"), config.FONT_SIZE_TITLE, config.COLOR_TEXT,
                             bold=True)
        surface.blit(title, title.get_rect(midtop=(surface.get_width() // 2, TITLE_TOP)))

        camera = self._pipeline.camera
        status = camera.status
        result = self._pipeline.latest_result()
        # Prefer the frame the hands were detected in, so the overlay lines up.
        frame = result.frame if result is not None else camera.latest_frame()
        self._view.draw(surface, self._preview_area, frame,
                        tr(f"camera.status.{status.value}"), STATUS_COLORS[status])
        image_rect = self._view.last_image_rect
        if image_rect is not None:
            draw_player_zones(surface, image_rect, self.ctx.fonts, self.ctx.tr)
            if result is not None:
                self._overlay.draw(surface, image_rect, result.hands,
                                   hand_styles(result, self.ctx.tr))
                for gesture in result.gestures:
                    if gesture.cursor is not None:
                        center = to_screen(*gesture.cursor, image_rect)
                        draw_cursor(surface, center, gesture, PLAYER_COLORS[gesture.player_id])
        self._draw_info(surface)
        self._back.draw(surface, fonts)
        self.draw_touch_cursor(surface)

    def _draw_info(self, surface: pygame.Surface) -> None:
        area = self._info_area
        draw_panel(surface, area)
        x, y = area.left + PADDING, area.top + PADDING
        camera = self._pipeline.camera
        status = camera.status
        y = self._status_line(surface, x, y, self.ctx.tr(f"camera.status.{status.value}"),
                              STATUS_COLORS[status])
        frame = camera.latest_frame()
        if status is CameraStatus.RUNNING and frame is not None:
            width, height = frame.size
            y = self._small(surface, x, y, f"{self.ctx.tr('camera.resolution')}: "
                            f"{width} × {height}  ·  {camera.fps:.0f} FPS")
            if frame.too_dark:
                y = self._small(surface, x, y, self.ctx.tr("camera.too_dark"), config.COLOR_ERROR)
            self._draw_tracking(surface, x, y + SECTION_GAP, area.width - 2 * PADDING)
        elif status in (CameraStatus.UNAVAILABLE, CameraStatus.DISCONNECTED):
            self._draw_help(surface, x, y, area.width - 2 * PADDING)

    def _draw_tracking(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        tr = self.ctx.tr
        pipeline = self._pipeline
        if pipeline.status is PipelineStatus.ERROR:
            y = self._status_line(surface, x, y, tr("hands.error"), config.COLOR_ERROR)
            for line in self.ctx.fonts.render_wrapped(pipeline.message, config.FONT_SIZE_SMALL,
                                                      config.COLOR_ERROR, width):
                surface.blit(line, (x, y))
                y += line.get_height()
            return
        result = pipeline.latest_result()
        if result is None:
            self._status_line(surface, x, y, tr("hands.starting"), config.COLOR_WARNING)
            return
        count = len(result.hands)
        color = config.COLOR_OK if count == config.MAX_NUM_HANDS else (
            config.COLOR_WARNING if count else config.COLOR_LOCKED)
        y = self._status_line(surface, x, y, tr("hands.count", count=count), color)
        y = self._small(surface, x, y, tr("hands.speed", fps=pipeline.fps,
                                          ms=result.detection_ms))
        self._draw_players(surface, x, y + SECTION_GAP, width, result)

    def _draw_players(self, surface: pygame.Surface, x: int, y: int, width: int,
                      result: VisionResult) -> None:
        tr = self.ctx.tr
        title = self.ctx.fonts.render(tr("players.title"), config.FONT_SIZE_MEDIUM,
                                      config.COLOR_TEXT, bold=True)
        surface.blit(title, (x, y))
        y += title.get_height() + LINE_GAP
        for player in result.players:
            status = tr(f"players.status.{player.status.value}", seconds=player.lost_for)
            name = tr("player.label", number=player.player_id)
            color = {TrackStatus.TRACKED: PLAYER_COLORS[player.player_id],
                     TrackStatus.LOST: config.COLOR_WARNING,
                     TrackStatus.ABSENT: config.COLOR_LOCKED}[player.status]
            pygame.draw.circle(surface, color, (x + DOT_RADIUS, y + DOT_RADIUS), DOT_RADIUS)
            text = f"{name} ({tr(side_key(player.player_id))}): {status}"
            y = self._small(surface, x + DOT_RADIUS * 3, y, text, config.COLOR_TEXT)
            gesture = result.gesture(player.player_id)
            if gesture is not None and gesture.tracked:
                indent = x + DOT_RADIUS * 3
                y = self._small(surface, indent, y, tr(
                    "gesture.line", pose=tr(f"gesture.pose.{gesture.pose.value}"),
                    phase=tr(f"gesture.phase.{gesture.pinch_phase.value}"),
                    distance=gesture.pinch_distance))
                meter = pygame.Rect(indent, y, width - DOT_RADIUS * 3, METER_HEIGHT)
                draw_pinch_meter(surface, meter, gesture.pinch_distance)
                y = meter.bottom + LINE_GAP * 2
        # The player dots already show who is detected; only explain when someone is missing.
        if not all(p.status is TrackStatus.TRACKED for p in result.players):
            for line in self.ctx.fonts.render_wrapped(tr("players.instructions"),
                                                      config.FONT_SIZE_SMALL,
                                                      config.COLOR_WARNING, width):
                surface.blit(line, (x, y))
                y += line.get_height()
        self._draw_event_log(surface, x, y + LINE_GAP)

    def _draw_event_log(self, surface: pygame.Surface, x: int, y: int) -> int:
        tr = self.ctx.tr
        y = self._small(surface, x, y, tr("gesture.log_title"), config.COLOR_TEXT)
        if not self._events:
            return self._small(surface, x, y, tr("gesture.log_empty"))
        for event in reversed(self._events):
            position = (f"({event.position[0]:.2f}, {event.position[1]:.2f})"
                        if event.position else "")
            text = tr("gesture.log_entry", number=event.player_id,
                      action=tr(f"gesture.action.{event.action.value}"), position=position)
            y = self._small(surface, x, y, text, PLAYER_COLORS[event.player_id])
        return y

    def _draw_help(self, surface: pygame.Surface, x: int, y: int, width: int) -> None:
        for key in HELP_KEYS:
            for line in self.ctx.fonts.render_wrapped(f"• {self.ctx.tr(key)}",
                                                      config.FONT_SIZE_SMALL,
                                                      config.COLOR_TEXT_MUTED, width):
                surface.blit(line, (x, y))
                y += line.get_height()
            y += LINE_GAP

    def _status_line(self, surface: pygame.Surface, x: int, y: int, text: str,
                     color: config.Color) -> int:
        label = self.ctx.fonts.render(text, config.FONT_SIZE_MEDIUM, config.COLOR_TEXT,
                                      bold=True)
        pygame.draw.circle(surface, color, (x + DOT_RADIUS, y + label.get_height() // 2),
                           DOT_RADIUS)
        surface.blit(label, (x + DOT_RADIUS * 3, y))
        return y + label.get_height() + LINE_GAP

    def _small(self, surface: pygame.Surface, x: int, y: int, text: str,
               color: config.Color = config.COLOR_TEXT_MUTED) -> int:
        rendered = self.ctx.fonts.render(text, config.FONT_SIZE_SMALL, color)
        surface.blit(rendered, (x, y))
        return y + rendered.get_height() + LINE_GAP
