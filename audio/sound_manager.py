"""Sound effects with optional asset files and generated fallbacks.

For every effect the manager first looks for ``assets/sounds/<name>.wav`` or
``.ogg``. If there is no file, a short tone is synthesised with NumPy, so the
game has sound out of the box. If the audio device cannot be opened (no sound
card, remote desktop, tests) the manager silently does nothing: sound can never
crash the game.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np
import pygame

import config

SAMPLE_RATE = 44100
MIXER_BUFFER = 512  # Small buffer = low latency for click sounds.
INT16_MAX = 32767
ATTACK_TIME = 0.005  # Seconds of fade-in to avoid clicks.
SOUND_EXTENSIONS = (".wav", ".ogg")


class SoundEffect(Enum):
    MENU_CLICK = "menu_click"
    PIECE_SELECT = "piece_select"
    PIECE_MOVE = "piece_move"
    COW_PLACE = "cow_place"
    TIGER_CAPTURE = "tiger_capture"
    INVALID_MOVE = "invalid_move"
    TURN_CHANGE = "turn_change"
    VICTORY = "victory"
    GAME_OVER = "game_over"


@dataclass(frozen=True)
class Tone:
    """One synthesised note: frequency sweep, length, waveform and loudness."""

    start_hz: float
    end_hz: float
    seconds: float
    wave: str = "sine"  # "sine", "square" or "noise"
    volume: float = 0.5


# Each effect is a sequence of tones played one after another.
GENERATED_SOUNDS: dict[SoundEffect, tuple[Tone, ...]] = {
    SoundEffect.MENU_CLICK: (Tone(1200, 1000, 0.04, volume=0.35),),
    SoundEffect.PIECE_SELECT: (Tone(660, 880, 0.08),),
    SoundEffect.PIECE_MOVE: (Tone(420, 380, 0.09, volume=0.4),),
    SoundEffect.COW_PLACE: (Tone(300, 220, 0.16, volume=0.55), Tone(220, 200, 0.06, volume=0.3)),
    SoundEffect.TIGER_CAPTURE: (Tone(0, 0, 0.07, "noise", 0.4), Tone(180, 90, 0.25, "square", 0.3)),
    SoundEffect.INVALID_MOVE: (Tone(200, 200, 0.08, "square", 0.25), Tone(0, 0, 0.04, volume=0),
                               Tone(160, 160, 0.1, "square", 0.25)),
    SoundEffect.TURN_CHANGE: (Tone(523, 523, 0.08, volume=0.35), Tone(784, 784, 0.12, volume=0.35)),
    SoundEffect.VICTORY: tuple(Tone(f, f, 0.14 if i < 3 else 0.4, volume=0.45)
                               for i, f in enumerate((523, 659, 784, 1047))),
    SoundEffect.GAME_OVER: (Tone(392, 330, 0.2, volume=0.4), Tone(330, 262, 0.35, volume=0.4)),
}


def synthesize(tones: tuple[Tone, ...], channels: int,
               sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Render tones to an int16 array shaped (samples, channels)."""
    rng = np.random.default_rng(0)  # Deterministic noise.
    parts = []
    for tone in tones:
        count = max(1, int(tone.seconds * sample_rate))
        t = np.arange(count) / sample_rate
        freq = np.linspace(tone.start_hz, tone.end_hz, count)
        phase = 2 * np.pi * np.cumsum(freq) / sample_rate
        if tone.wave == "noise":
            signal = rng.uniform(-1.0, 1.0, count)
        elif tone.wave == "square":
            signal = np.sign(np.sin(phase))
        else:
            signal = np.sin(phase)
        attack = np.clip(t / ATTACK_TIME, 0.0, 1.0)
        decay = np.exp(-3.0 * t / tone.seconds)  # Natural fade-out.
        parts.append(signal * attack * decay * tone.volume)
    mono = (np.concatenate(parts) * INT16_MAX).astype(np.int16)
    return np.ascontiguousarray(np.repeat(mono[:, None], channels, axis=1))


class SoundManager:
    """Plays named effects; never raises."""

    def __init__(self, enabled: bool = config.SOUND_ENABLED,
                 volume: float = config.SOUND_VOLUME,
                 sounds_dir: Path = config.SOUNDS_DIR) -> None:
        self._sounds: dict[SoundEffect, pygame.mixer.Sound] = {}
        self.sources: dict[SoundEffect, str] = {}  # "file" or "generated" (diagnostics)
        self.volume = volume
        self.enabled = enabled
        self._sounds_dir = sounds_dir
        self.available = False
        if enabled:
            self._start()

    def _start(self) -> None:
        self.available = self._init_mixer()
        if self.available and not self._sounds:
            self._load_all(self._sounds_dir)

    def set_enabled(self, enabled: bool) -> None:
        """Turn sound on/off at runtime (opens the audio device on first use)."""
        self.enabled = enabled
        if enabled and not self.available:
            self._start()

    @staticmethod
    def _init_mixer() -> bool:
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=2,
                                  buffer=MIXER_BUFFER)
            return pygame.mixer.get_init() is not None
        except pygame.error:
            return False  # No audio device: play silently.

    def _load_all(self, sounds_dir: Path) -> None:
        _, _, channels = pygame.mixer.get_init()
        for effect in SoundEffect:
            sound = self._load_file(sounds_dir, effect)
            if sound is not None:
                self.sources[effect] = "file"
            else:
                try:
                    sound = pygame.sndarray.make_sound(
                        synthesize(GENERATED_SOUNDS[effect], channels))
                except (pygame.error, ValueError):
                    continue
                self.sources[effect] = "generated"
            sound.set_volume(self.volume)
            self._sounds[effect] = sound

    @staticmethod
    def _load_file(sounds_dir: Path, effect: SoundEffect) -> pygame.mixer.Sound | None:
        for extension in SOUND_EXTENSIONS:
            path = sounds_dir / f"{effect.value}{extension}"
            if path.is_file():
                try:
                    return pygame.mixer.Sound(str(path))
                except pygame.error:
                    return None  # Broken file: fall back to the generated sound.
        return None

    def play(self, effect: SoundEffect) -> None:
        if not (self.enabled and self.available):
            return
        sound = self._sounds.get(effect)
        if sound is not None:
            try:
                sound.play()
            except pygame.error:
                pass

    def set_volume(self, volume: float) -> None:
        self.volume = min(1.0, max(0.0, volume))
        for sound in self._sounds.values():
            sound.set_volume(self.volume)
