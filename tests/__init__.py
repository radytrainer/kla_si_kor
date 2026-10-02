"""Automated tests (run with: python -m unittest discover -s tests -t . -v).

Tests never open a real window, speaker or webcam, and never touch the player's
own settings or calibration: SDL uses dummy video/audio drivers, camera and
detector fakes are injected where needed, and data files go to a temporary
folder that is deleted afterwards.
"""

import atexit
import os
import shutil
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

_DATA_DIR = tempfile.mkdtemp(prefix="tiger_cow_tests_")
os.environ["TIGER_COW_DATA_DIR"] = _DATA_DIR
atexit.register(shutil.rmtree, _DATA_DIR, ignore_errors=True)
