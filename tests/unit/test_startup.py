import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import RuntimePaths
from app.services.startup import dependency_status, ensure_runtime_directories


class StartupTests(unittest.TestCase):
    def test_dependency_status_reports_pyside6(self) -> None:
        status = dependency_status()

        self.assertTrue(status["PySide6"])
        self.assertIn("pytest", status)
        self.assertIn("ruff", status)

    def test_ensure_runtime_directories(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = RuntimePaths(
                project_root=root,
                data_dir=root / "data",
                logs_dir=root / "logs",
                cache_dir=root / "data" / "cache",
                config_dir=root / "data" / "config",
            )

            ensure_runtime_directories(paths)

            self.assertTrue(paths.data_dir.is_dir())
            self.assertTrue(paths.logs_dir.is_dir())
            self.assertTrue(paths.cache_dir.is_dir())
            self.assertTrue(paths.config_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
