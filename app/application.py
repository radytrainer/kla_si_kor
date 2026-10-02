"""Main application object: owns the window, settings, screens and frame loop."""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

import pygame

import config
from app.diagnostics import check_dependencies
from app.settings import Settings, load_settings, save_settings
from audio.sound_manager import SoundEffect, SoundManager
from camera.camera import Camera
from game.game_engine import GameEngine
from game.piece import Piece
from ui.calibration_screen import CalibrationScreen
from ui.camera_check import CameraCheckScreen
from ui.fonts import FontManager
from ui.game_over import GameOverScreen
from ui.game_screen import GameScreen
from ui.how_to_play import HowToPlayScreen
from ui.menu import MainMenu
from ui.piece_sprites import PieceSprites
from ui.ready_screen import ReadyScreen
from ui.screen import Screen, ScreenId, UiContext
from ui.settings_screen import SettingsScreen
from ui.system_check import SystemCheckScreen
from ui.text import Translator
from ui.widgets import Button
from vision.calibration_store import load_corners
from vision.coordinate_mapper import BoardCoordinateMapper
from vision.gesture_detector import GestureTuning
from vision.pipeline import DetectorFactory, VisionPipeline

MOUSE_LEFT_BUTTON = 1
MOUSE_RIGHT_BUTTON = 3
DEBUG_TEXT_POS = (8, 4)
WINDOW_ICON_SIZE = 64
WINDOW_FLAGS = pygame.SCALED | pygame.RESIZABLE  # Fixed 1280×720 canvas, scaled to fit.


def close_startup_splash() -> None:
    """Close the one-file .exe's loading splash (only exists in that build)."""
    try:
        import pyi_splash  # type: ignore[import-not-found]
    except ImportError:
        return
    pyi_splash.close()


@dataclass(frozen=True)
class LaunchOptions:
    """Command-line choices. ``None`` means "use the saved setting"; a value
    overrides it for this session only (it is not saved)."""

    fullscreen: bool | None = None
    debug: bool | None = None
    input_mode: str | None = None  # GESTURE (camera) or MOUSE.
    sound: bool | None = None
    start_screen: ScreenId | None = None  # Jump straight to a screen (developer).
    max_frames: int | None = None  # Stop automatically after N frames (testing).
    screenshot_path: Path | None = None  # Save the last frame here on exit.


def session_settings(saved: Settings, options: LaunchOptions) -> Settings:
    """Saved settings with command-line overrides applied."""
    overrides = {name: value for name, value in (
        ("fullscreen", options.fullscreen), ("debug", options.debug),
        ("input_mode", options.input_mode), ("sound", options.sound)) if value is not None}
    return saved.with_changes(**overrides)


class Application:
    """Initialises Pygame, routes input to the active screen, runs the loop."""

    def __init__(self, options: LaunchOptions, camera: Camera | None = None,
                 detector_factory: DetectorFactory | None = None) -> None:
        self._options = options
        # What is on disk vs. what this session uses (saved + command-line overrides).
        self._saved_settings = load_settings()
        self._settings = session_settings(self._saved_settings, options)
        pygame.init()
        pygame.display.set_caption(f"{config.APP_TITLE_KM} - {config.APP_TITLE_EN}")
        sprites = PieceSprites()
        pygame.display.set_icon(sprites.get(Piece.TIGER, WINDOW_ICON_SIZE))
        self._fullscreen = self._settings.fullscreen
        self._surface = self._set_display_mode(self._fullscreen)
        close_startup_splash()
        self._clock = pygame.time.Clock()
        self._fonts = FontManager()
        self._sounds = SoundManager(enabled=self._settings.sound, volume=self._settings.volume)
        Button.on_any_click = lambda: self._sounds.play(SoundEffect.MENU_CLICK)
        self._ctx = UiContext(
            fonts=self._fonts,
            sprites=sprites,
            tr=Translator(self._settings.language),
            navigate=self.navigate,
            debug=self._settings.debug,
            input_mode=self._settings.input_mode,
            one_hand=self._settings.one_hand,
            computer_level=self._settings.computer,
            human_side=self._settings.human_side,
            sounds=self._sounds,
        )
        self._engine = GameEngine()
        self._camera = camera if camera is not None else Camera()
        self._camera.set_index(self._settings.camera_index)
        self._vision = (VisionPipeline(self._camera, detector_factory) if detector_factory
                        else VisionPipeline(self._camera))
        self._vision.set_gesture_tuning(self._gesture_tuning(self._settings))
        self._mapper = BoardCoordinateMapper(load_corners())
        system_check = SystemCheckScreen(self._ctx, check_dependencies())
        self._screens: dict[ScreenId, Screen] = {
            ScreenId.SYSTEM_CHECK: system_check,
            ScreenId.MENU: MainMenu(self._ctx, self._vision),
            ScreenId.GAME: GameScreen(self._ctx, self._engine, self._vision, self._mapper),
            ScreenId.READY: ReadyScreen(self._ctx, self._vision),
            ScreenId.GAME_OVER: GameOverScreen(self._ctx, self._engine, self._vision),
            ScreenId.HOW_TO_PLAY: HowToPlayScreen(self._ctx, self._vision),
            ScreenId.CAMERA_CHECK: CameraCheckScreen(self._ctx, self._vision),
            ScreenId.CALIBRATION: CalibrationScreen(self._ctx, self._vision, self._mapper),
            ScreenId.SETTINGS: SettingsScreen(self._ctx, self._vision, lambda: self._settings,
                                              self.update_settings),
        }
        self._current_id: ScreenId | None = None
        self._running = True
        start = options.start_screen or (
            ScreenId.MENU if system_check.all_ok else ScreenId.SYSTEM_CHECK
        )
        self.navigate(start)

    # ------------------------------------------------------------ properties
    @property
    def current_screen_id(self) -> ScreenId | None:
        return self._current_id

    @property
    def settings(self) -> Settings:
        return self._settings

    @property
    def camera(self) -> Camera:
        return self._camera

    @property
    def vision(self) -> VisionPipeline:
        return self._vision

    @property
    def sounds(self) -> SoundManager:
        return self._sounds

    @property
    def engine(self) -> GameEngine:
        return self._engine

    @property
    def running(self) -> bool:
        return self._running

    # -------------------------------------------------------------- settings
    @staticmethod
    def _gesture_tuning(settings: Settings) -> GestureTuning:
        close, release = settings.pinch_thresholds
        return GestureTuning(close, release, settings.smoothing_value)

    @staticmethod
    def _set_display_mode(fullscreen: bool) -> pygame.Surface:
        flags = WINDOW_FLAGS | (pygame.FULLSCREEN if fullscreen else 0)
        return pygame.display.set_mode((config.WINDOW_WIDTH, config.WINDOW_HEIGHT), flags)

    def update_settings(self, new: Settings, save: bool = True) -> None:
        """Apply settings immediately and (by default) save the changed ones.

        Only fields that actually changed are written, so a command-line
        override such as ``--input mouse`` never becomes permanent.
        """
        if new.fullscreen != self._fullscreen and not self._toggle_fullscreen():
            new = new.with_changes(fullscreen=self._fullscreen)  # Not supported: keep as is.
        changed = {f.name: getattr(new, f.name) for f in fields(Settings)
                   if getattr(new, f.name) != getattr(self._settings, f.name)}
        self._settings = new
        self._ctx.tr.language = new.language
        self._ctx.debug = new.debug
        self._ctx.input_mode = new.input_mode
        self._ctx.one_hand = new.one_hand
        self._ctx.computer_level = new.computer
        self._ctx.human_side = new.human_side
        self._sounds.set_enabled(new.sound)
        self._sounds.set_volume(new.volume)
        self._vision.set_gesture_tuning(self._gesture_tuning(new))
        self._camera.set_index(new.camera_index)
        self._sync_vision()
        if save and changed:
            self._saved_settings = self._saved_settings.with_changes(**changed)
            try:
                save_settings(self._saved_settings)
            except OSError:
                pass  # Settings still apply for this session.

    def _toggle_fullscreen(self) -> bool:
        """Switch fullscreen on/off; return False if the video driver cannot.

        Deliberately no fallback to ``pygame.display.set_mode``: calling it again
        on an existing SCALED window crashes pygame-ce (access violation) with
        drivers that cannot toggle (found by the Phase 15 monkey test).
        """
        try:
            pygame.display.toggle_fullscreen()
        except pygame.error:
            return False
        self._fullscreen = not self._fullscreen
        return True

    def _sync_vision(self) -> None:
        """Run the camera only while the current screen needs it."""
        if self._current_id is None:
            return
        if self._screens[self._current_id].uses_vision:
            self._vision.start()
        else:
            self._vision.stop()

    # ------------------------------------------------------------ navigation
    def navigate(self, screen_id: ScreenId) -> None:
        """Switch to another screen (EXIT stops the main loop)."""
        if self._current_id is not None:
            self._screens[self._current_id].on_exit()
        if screen_id is ScreenId.EXIT:
            self._current_id = None
            self._running = False
            return
        self._current_id = screen_id
        screen = self._screens[screen_id]
        self._sync_vision()  # Saves CPU and turns the camera light off when unused.
        screen.on_enter()
        screen.on_pointer_move(pygame.mouse.get_pos())

    # ------------------------------------------------------------ main loop
    def run(self) -> int:
        """Run until the window is closed; return a process exit code."""
        frame_count = 0
        try:
            while self._running:
                dt = self._clock.tick(config.TARGET_FPS) / 1000.0
                self.handle_events(pygame.event.get())
                if not self._running:
                    break
                self.render_frame(dt)
                pygame.display.flip()
                frame_count += 1
                if self._options.max_frames and frame_count >= self._options.max_frames:
                    self._running = False
            self.save_screenshot(self._options.screenshot_path)
        finally:
            self.shutdown()
        return 0

    def shutdown(self) -> None:
        """Release the camera and close Pygame (safe to call more than once)."""
        self._vision.stop()
        pygame.quit()

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        """Translate Pygame events into screen pointer callbacks."""
        for event in events:
            if not self._running:
                return
            screen = self._screens[self._current_id]
            if event.type == pygame.QUIT:
                self._running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                screen.on_back()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                self.update_settings(self._settings.with_changes(
                    fullscreen=not self._settings.fullscreen))
            elif event.type == pygame.MOUSEMOTION:
                screen.on_pointer_move(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == MOUSE_LEFT_BUTTON:
                screen.on_select(event.pos)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == MOUSE_RIGHT_BUTTON:
                screen.on_cancel()

    def render_frame(self, dt: float) -> None:
        """Update and draw the active screen (plus debug info) without flipping."""
        if self._current_id is None:  # The app is exiting.
            return
        screen = self._screens[self._current_id]
        screen.update(dt)
        if self._current_id is None:  # The update navigated to EXIT.
            return
        self._screens[self._current_id].draw(self._surface)
        if self._settings.debug:
            self._draw_debug()

    def _draw_debug(self) -> None:
        text = f"FPS {self._clock.get_fps():3.0f}  |  {self._current_id.name}"
        rendered = self._fonts.render(text, config.FONT_SIZE_SMALL, config.COLOR_TEXT_MUTED)
        self._surface.blit(rendered, DEBUG_TEXT_POS)

    def save_screenshot(self, path: Path | None) -> None:
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            pygame.image.save(self._surface, str(path))
