"""Font loading with correct Khmer text shaping.

Khmer script needs complex shaping (stacked consonants such as ្ល). pygame-ce
exposes HarfBuzz shaping through ``Font.set_script("Khmr")``; without it the
title ខ្លាស៊ីគោ renders as disconnected glyphs. This module picks a Khmer-capable
font for Khmer text and a clean Latin font for everything else.
"""

from __future__ import annotations

from pathlib import Path

import pygame

import config

KHMER_BLOCK_START = 0x1780
KHMER_BLOCK_END = 0x17FF
KHMER_SCRIPT_TAG = "Khmr"


def contains_khmer(text: str) -> bool:
    """Return True if the text contains any Khmer character."""
    return any(KHMER_BLOCK_START <= ord(char) <= KHMER_BLOCK_END for char in text)


def _find_custom_khmer_font() -> str | None:
    """Return a Khmer .ttf/.otf from assets/fonts/, if the user supplied one."""
    if not config.FONTS_DIR.is_dir():
        return None
    for path in sorted(config.FONTS_DIR.iterdir()):
        name = path.name.lower()
        if path.suffix.lower() in (".ttf", ".otf") and any(
            hint in name for hint in config.KHMER_FONT_FILE_HINTS
        ):
            return str(path)
    return None


def _match_system_font(candidates: tuple[str, ...], bold: bool) -> str | None:
    """Return the path of the first installed system font among candidates."""
    for name in candidates:
        path = pygame.font.match_font(name, bold=bold)
        if path and Path(path).is_file():
            return path
    return None


class FontManager:
    """Caches fonts and renders text in the right typeface for its script."""

    def __init__(self) -> None:
        if not pygame.font.get_init():
            pygame.font.init()
        self._cache: dict[tuple[bool, int, bool], pygame.font.Font] = {}
        self._custom_khmer = _find_custom_khmer_font()
        self.khmer_available = bool(
            self._custom_khmer
            or _match_system_font(config.KHMER_FONT_CANDIDATES, bold=False)
        )

    def _font_path(self, khmer: bool, bold: bool) -> str | None:
        if khmer:
            return self._custom_khmer or _match_system_font(
                config.KHMER_FONT_CANDIDATES, bold
            )
        return _match_system_font(config.LATIN_FONT_CANDIDATES, bold)

    def get(self, size: int, bold: bool = False, khmer: bool = False) -> pygame.font.Font:
        """Return a cached font; falls back to pygame's bundled font."""
        key = (khmer, size, bold)
        font = self._cache.get(key)
        if font is None:
            font = pygame.font.Font(self._font_path(khmer, bold), size)
            if khmer and hasattr(font, "set_script"):
                font.set_script(KHMER_SCRIPT_TAG)
            self._cache[key] = font
        return font

    def render(
        self,
        text: str,
        size: int,
        color: config.Color,
        bold: bool = False,
    ) -> pygame.Surface:
        """Render text, automatically choosing a Khmer font when needed."""
        font = self.get(size, bold=bold, khmer=contains_khmer(text))
        return font.render(text, True, color)

    def render_wrapped(
        self,
        text: str,
        size: int,
        color: config.Color,
        max_width: int,
        bold: bool = False,
    ) -> list[pygame.Surface]:
        """Render text as several lines, breaking at spaces to fit max_width."""
        font = self.get(size, bold=bold, khmer=contains_khmer(text))
        lines: list[str] = []
        current = ""
        for word in text.split(" "):
            candidate = f"{current} {word}" if current else word
            if current and font.size(candidate)[0] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return [font.render(line, True, color) for line in lines]
