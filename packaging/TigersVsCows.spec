# PyInstaller build definition for Tigers vs Cows (run via packaging/build.py).
#
# Default: dist/TigersVsCows/ with two programs sharing one set of files:
#   TigersVsCows.exe          the game (no console window)
#   TigersVsCows-console.exe  same program with a console, for `--check` diagnostics
# With TIGER_COW_ONEFILE=1 (python packaging/build.py --onefile):
#   dist/TigersVsCows-<version>.exe, everything in one file (unpacks itself on start)
# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (FixedFileInfo, StringFileInfo, StringStruct,
                                                  StringTable, VarFileInfo, VarStruct,
                                                  VSVersionInfo)

ROOT = Path(SPECPATH).parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402  (version number and app name)

ICON = str(ROOT / "packaging" / "TigersVsCows.ico")
VERSION = tuple(int(part) for part in config.APP_VERSION.split(".")) + (0,)

# Development-only packages, plus two MediaPipe extras the game never uses.
# Note: matplotlib and Pillow must NOT be excluded: mediapipe.tasks.python.vision
# imports its drawing helper (and so matplotlib) unconditionally. sounddevice is
# safe to drop because MediaPipe guards that import (ImportError/OSError).
EXCLUDES = [
    "sounddevice", "tkinter", "IPython", "pytest",
    "coverage", "pyflakes", "pycodestyle", "tests",
]

version_info = VSVersionInfo(
    ffi=FixedFileInfo(filevers=VERSION, prodvers=VERSION),
    kids=[
        StringFileInfo([StringTable("040904B0", [
            StringStruct("ProductName", "Tigers vs Cows (Khla Si Ko)"),
            StringStruct("FileDescription", "Tigers vs Cows - Computer Vision Edition"),
            StringStruct("ProductVersion", config.APP_VERSION),
            StringStruct("FileVersion", config.APP_VERSION),
            StringStruct("OriginalFilename", "TigersVsCows.exe"),
        ])]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)

# MediaPipe 1.x loads its engine (mediapipe/tasks/c/libmediapipe.dll) by path at
# runtime, which PyInstaller cannot detect, so the whole package is collected:
# code, the DLL and data files, keeping the package layout it expects.
mediapipe_datas, mediapipe_binaries, mediapipe_modules = collect_all("mediapipe")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    datas=[(str(ROOT / "assets"), "assets"), *mediapipe_datas],
    binaries=mediapipe_binaries,
    hiddenimports=mediapipe_modules,
    excludes=EXCLUDES,
    noarchive=False,
)
pyz = PYZ(a.pure)


def program(name: str, console: bool):
    return EXE(pyz, a.scripts, [], exclude_binaries=True, name=name, console=console,
               icon=ICON, version=version_info, upx=False)


if os.environ.get("TIGER_COW_ONEFILE") == "1":
    # The one-file program unpacks ~300 MB before Python starts (~5 s): show a splash
    # at once so players don't think it failed and start it twice. The game closes
    # it (pyi_splash) as soon as its window is open.
    splash = Splash(str(ROOT / "packaging" / "splash.png"), binaries=a.binaries,
                    datas=a.datas)
    EXE(pyz, a.scripts, splash, splash.binaries, a.binaries, a.datas, [],
        name=f"TigersVsCows-{config.APP_VERSION}", console=False, icon=ICON,
        version=version_info, upx=False)
else:
    game = program("TigersVsCows", console=False)
    console = program("TigersVsCows-console", console=True)
    COLLECT(game, console, a.binaries, a.datas, name="TigersVsCows", upx=False)
