import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.config import APP_NAME
from app.ui.main_window import QuantMainWindow


class UiStartupTests(unittest.TestCase):
    def test_main_window_builds_core_pages(self) -> None:
        app = QApplication.instance() or QApplication([])
        window = QuantMainWindow()

        self.assertEqual(window.windowTitle(), APP_NAME)
        self.assertEqual(window.tabs.count(), 10)
        self.assertEqual(window.tabs.tabText(0), "总览仪表盘")
        self.assertEqual(window.tabs.tabText(9), "日志与诊断")

        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
