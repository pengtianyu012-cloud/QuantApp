import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.ui.main_window import QuantMainWindow


class UiStrategyPreviewTests(unittest.TestCase):
    def test_generate_signal_preview_updates_selection_table(self) -> None:
        app = QApplication.instance() or QApplication([])
        window = QuantMainWindow()

        window.generate_signal_preview()

        self.assertNotEqual(window.selection_table.item(0, 0).text(), "尚未实现")
        self.assertGreaterEqual(len(window.service.strategy_service.latest_signals), 1)

        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
