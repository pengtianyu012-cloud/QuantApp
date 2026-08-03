import os
import unittest
from datetime import datetime
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.config import APP_TIME_ZONE
from app.models import OrderSide
from app.services import TradingAppService
from app.ui.main_window import QuantMainWindow
from app.utils import FrozenClock


class UiManualOrderTests(unittest.TestCase):
    def test_manual_buy_updates_trading_tables(self) -> None:
        app = QApplication.instance() or QApplication([])
        clock = FrozenClock(datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE))
        window = QuantMainWindow(TradingAppService(persist_account=False, clock=clock))

        result = window.execute_manual_order(
            OrderSide.BUY,
            symbol="000001.SZ",
            quantity=100,
            limit_price=Decimal("10.81"),
            confirm=False,
        )

        self.assertTrue(result.ok)
        self.assertEqual(window.positions_table.item(0, 0).text(), "000001.SZ")
        self.assertEqual(window.orders_table.item(0, 5).text(), "已成交")
        self.assertNotEqual(window.fills_table.item(0, 0).text(), "-")

        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
