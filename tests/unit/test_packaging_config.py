import tomllib
import unittest
from pathlib import Path


class PackagingConfigTests(unittest.TestCase):
    def test_pyinstaller_spec_exists_and_targets_main(self) -> None:
        spec = Path("A股量化模拟交易系统.spec")

        self.assertTrue(spec.exists())
        text = spec.read_text(encoding="utf-8")
        self.assertIn("main.py", text)
        self.assertIn("docs", text)
        self.assertIn('collect_data_files("akshare")', text)

    def test_windows_scripts_exist(self) -> None:
        for script_name in ("run_dev.ps1", "test.ps1", "check.ps1", "build_windows.ps1"):
            self.assertTrue((Path("scripts") / script_name).exists())

    def test_python_3132_is_the_declared_build_baseline(self) -> None:
        metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        build_script = Path("scripts/build_windows.ps1").read_text(encoding="utf-8")

        self.assertEqual(Path(".python-version").read_text(encoding="utf-8").strip(), "3.13.2")
        self.assertEqual(metadata["project"]["requires-python"], ">=3.13.2,<3.14")
        self.assertEqual(metadata["tool"]["ruff"]["target-version"], "py313")
        self.assertIn('$RequiredPython = "3.13.2"', build_script)
        self.assertIn("$ActualPython -ne $RequiredPython", build_script)


if __name__ == "__main__":
    unittest.main()
