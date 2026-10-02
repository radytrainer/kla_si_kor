"""Falling confetti for the victory celebration."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

import config

COLORS: tuple[config.Color, ...] = (config.COLOR_TIGER, config.COLOR_COW, config.COLOR_SELECTED,
                                    config.COLOR_PLAYER_1_CURSOR, (236, 72, 153), (255, 255, 255))
FALL_SPEED = (120.0, 260.0)  # pixels per second
DRIFT_SPEED = 60.0
SPIN_SPEED = 6.0  # radians per second
SIZE = (6, 13)
SWAY_FREQUENCY = 2.0


@dataclass
class Particle:
    x: float
    y: float
    speed: float
    drift: float
    phase: float
    size: int
    color: config.Color


class Confetti:
    def __init__(self, width: int, height: int, count: int = config.CONFETTI_COUNT,
                 seed: int | None = None) -> None:
        self._width, self._height = width, height
        self._rng = random.Random(seed)
        # Start above the screen, spread out, so pieces rain in over time.
        self.particles = [self._spawn(self._rng.uniform(-height, 0)) for _ in range(count)]
        self._time = 0.0

    def _spawn(self, y: float) -> Particle:
        rng = self._rng
        return Particle(rng.uniform(0, self._width), y, rng.uniform(*FALL_SPEED),
                        rng.uniform(-DRIFT_SPEED, DRIFT_SPEED), rng.uniform(0, math.tau),
                        rng.randint(*SIZE), rng.choice(COLORS))

    def update(self, dt: float) -> None:
        self._time += dt
        for index, p in enumerate(self.particles):
            p.y += p.speed * dt
            p.x += p.drift * dt * math.sin(self._time * SWAY_FREQUENCY + p.phase)
            if p.y > self._height:  # Recycle at the top: the celebration keeps going.
                self.particles[index] = self._spawn(-SIZE[1])

    def draw(self, surface: pygame.Surface) -> None:
        for p in self.particles:
            # Fake 3D spin: the rectangle's width oscillates.
            width = max(1, round(p.size * abs(math.cos(self._time * SPIN_SPEED + p.phase))))
            pygame.draw.rect(surface, p.color, (round(p.x), round(p.y), width, p.size))
