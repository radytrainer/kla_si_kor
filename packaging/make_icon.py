"""Create packaging/TigersVsCows.ico and packaging/splash.png from the game's art.

Run once (python packaging/make_icon.py); both files are kept in the repository.
The splash is shown by the one-file .exe while it unpacks itself.
Needs Pillow, which is a build-time tool only (not in requirements.txt).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402
from PIL import Image  # noqa: E402

from game.piece import Piece  # noqa: E402
from ui.piece_sprites import PieceSprites  # noqa: E402

ICON_PATH = Path(__file__).resolve().parent / "TigersVsCows.ico"
SPLASH_PATH = Path(__file__).resolve().parent / "splash.png"
SPLASH_SIZE = (560, 300)
SPLASH_PIECE = 110
SPLASH_BORDER = 4
SOURCE_SIZE = 256
ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    sprite = PieceSprites().get(Piece.TIGER, SOURCE_SIZE)
    raw = pygame.image.tobytes(sprite, "RGBA")
    Image.frombytes("RGBA", (SOURCE_SIZE, SOURCE_SIZE), raw).save(ICON_PATH, sizes=ICON_SIZES)
    print(f"saved {ICON_PATH}")
    make_splash()


def make_splash() -> None:
    """Title card shown while the one-file program unpacks (~5 seconds)."""
    import config
    from ui.fonts import FontManager
    from ui.widgets import draw_background

    width, height = SPLASH_SIZE
    card = pygame.Surface(SPLASH_SIZE)
    draw_background(card)
    pygame.draw.rect(card, config.COLOR_TIGER, card.get_rect(), SPLASH_BORDER)
    sprites, fonts = PieceSprites(), FontManager()
    card.blit(sprites.get(Piece.TIGER, SPLASH_PIECE), (40, 40))
    card.blit(sprites.get(Piece.COW, SPLASH_PIECE), (width - 40 - SPLASH_PIECE, 40))
    lines = ((config.APP_TITLE_KM, config.FONT_SIZE_LARGE, config.COLOR_TIGER, 60),
             (config.APP_TITLE_EN, config.FONT_SIZE_MEDIUM, config.COLOR_TEXT, 175),
             ("Loading...", config.FONT_SIZE_SMALL, config.COLOR_TEXT_MUTED, 235))
    for text, size, color, y in lines:
        rendered = fonts.render(text, size, color, bold=size != config.FONT_SIZE_SMALL)
        card.blit(rendered, rendered.get_rect(midtop=(width // 2, y)))
    pygame.image.save(card, str(SPLASH_PATH))
    print(f"saved {SPLASH_PATH}")


if __name__ == "__main__":
    main()
