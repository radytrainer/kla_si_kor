"""Build the Windows program.

Usage (from the project root, with the venv active):
    pip install pyinstaller
    python packaging/build.py              folder + zip: dist/TigersVsCows/ and
                                           dist/TigersVsCows-<version>-win64.zip
    python packaging/build.py --onefile    one file: dist/TigersVsCows-<version>.exe

Build tools are not game dependencies, so they are not in requirements.txt.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

PACKAGING = ROOT / "packaging"
DIST = ROOT / "dist"
APP_DIR = DIST / "TigersVsCows"
ONEFILE_EXE = DIST / f"TigersVsCows-{config.APP_VERSION}.exe"
REQUIRED = ("TigersVsCows.exe", "TigersVsCows-console.exe",
            "_internal/assets/models/hand_landmarker.task",
            "_internal/mediapipe/tasks/c/libmediapipe.dll")
MEGABYTE = 1e6


def run_pyinstaller(onefile: bool) -> None:
    env = {**os.environ, "TIGER_COW_ONEFILE": "1" if onefile else "0"}
    work = ROOT / "build" / ("onefile" if onefile else "folder")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--distpath", str(DIST), "--workpath", str(work),
                    str(PACKAGING / "TigersVsCows.spec")], check=True, cwd=ROOT, env=env)


def build_folder() -> int:
    run_pyinstaller(onefile=False)
    missing = [name for name in REQUIRED if not (APP_DIR / name).exists()]
    if missing:
        print(f"Build incomplete, missing: {missing}")
        return 1
    shutil.copy(PACKAGING / "README.txt", APP_DIR / "README.txt")
    archive = DIST / f"TigersVsCows-{config.APP_VERSION}-win64"
    shutil.make_archive(str(archive), "zip", root_dir=DIST, base_dir=APP_DIR.name)
    size = sum(f.stat().st_size for f in APP_DIR.rglob("*") if f.is_file()) / MEGABYTE
    print(f"\nBuilt {APP_DIR} ({size:.0f} MB)\nZip:  {archive}.zip "
          f"({Path(f'{archive}.zip').stat().st_size / MEGABYTE:.0f} MB)")
    return 0


def build_onefile() -> int:
    run_pyinstaller(onefile=True)
    if not ONEFILE_EXE.is_file():
        print(f"Build incomplete, missing: {ONEFILE_EXE}")
        return 1
    print(f"\nBuilt {ONEFILE_EXE} ({ONEFILE_EXE.stat().st_size / MEGABYTE:.0f} MB)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the Windows program")
    parser.add_argument("--onefile", action="store_true",
                        help="build one self-contained .exe instead of a folder + zip")
    args = parser.parse_args()
    if not config.HAND_MODEL_FILE.is_file():
        print("Hand model missing: run  python main.py --download-model  first.")
        return 1
    return build_onefile() if args.onefile else build_folder()


if __name__ == "__main__":
    sys.exit(main())
