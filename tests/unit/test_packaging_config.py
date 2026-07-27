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


if __name__ == "__main__":
    unittest.main()
