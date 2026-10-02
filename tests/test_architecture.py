"""Architecture guard: the game layer must not depend on vision or UI libraries."""

from __future__ import annotations

import ast
import unittest

import config

FORBIDDEN_IN_GAME = {"cv2", "mediapipe", "pygame", "numpy", "ui", "vision", "camera", "audio",
                     "app"}


class GameLayerIsolationTests(unittest.TestCase):
    def test_game_imports_nothing_forbidden(self) -> None:
        game_dir = config.PROJECT_ROOT / "game"
        for path in sorted(game_dir.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    with self.subTest(file=path.name, module=name):
                        self.assertNotIn(name.split(".")[0], FORBIDDEN_IN_GAME)


def top_level_imports(folder: str) -> list[tuple[str, str]]:
    """(file name, imported top-level package) for every import in a folder."""
    found = []
    for path in sorted((config.PROJECT_ROOT / folder).glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found += [(path.name, alias.name.split(".")[0]) for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.append((path.name, node.module.split(".")[0]))
    return found


class LayeringTests(unittest.TestCase):
    """Vision -> Input -> Game -> UI separation (spec section 44)."""

    def assert_layer_avoids(self, folder: str, forbidden: set[str]) -> None:
        for file_name, module in top_level_imports(folder):
            with self.subTest(file=f"{folder}/{file_name}", module=module):
                self.assertNotIn(module, forbidden)

    def test_vision_does_not_depend_on_ui_or_app(self) -> None:
        self.assert_layer_avoids("vision", {"pygame", "ui", "app", "audio"})

    def test_only_camera_and_vision_use_opencv_or_mediapipe(self) -> None:
        for folder in ("ui", "app", "game", "audio"):
            self.assert_layer_avoids(folder, {"cv2", "mediapipe"})

    def test_camera_layer_is_independent(self) -> None:
        self.assert_layer_avoids("camera", {"pygame", "ui", "app", "game", "vision", "audio"})


if __name__ == "__main__":
    unittest.main()
