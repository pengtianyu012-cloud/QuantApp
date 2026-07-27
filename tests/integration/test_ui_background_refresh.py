import os
import threading
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from app.data.providers import MockMarketDataProvider
from app.services import TradingAppService
from app.ui.main_window import QuantMainWindow


class RecordingProvider(MockMarketDataProvider):
    def __init__(self) -> None:
        super().__init__()
        self.thread_ids: list[int] = []

    def _record(self) -> None:
        self.thread_ids.append(threading.get_ident())

    def get_stock_list(self):
        self._record()
        return super().get_stock_list()

    def get_latest_quotes(self, symbols):
        self._record()
        return super().get_latest_quotes(symbols)

    def get_order_book(self, symbol):
        self._record()
        return super().get_order_book(symbol)

    def health_check(self):
        self._record()
        return super().health_check()


class UiBackgroundRefreshTests(unittest.TestCase):
    def test_market_requests_run_outside_qt_main_thread(self) -> None:
        app = QApplication.instance() or QApplication([])
        main_thread_id = threading.get_ident()
        provider = RecordingProvider()
        service = TradingAppService(
            market_data=provider,
            persist_account=False,
            background_market_data=True,
        )
        window = QuantMainWindow(service)

        window.refresh_quote_table()
        window.refresh_instruments_async()
        deadline = time.monotonic() + 3
        while (
            window.quote_table.item(0, 0).text() == "-"
            or window.instrument_table.item(0, 0).text() == "-"
        ) and time.monotonic() < deadline:
            app.processEvents()
            QTest.qWait(10)

        self.assertEqual(window.quote_table.item(0, 0).text(), "600519.SH")
        self.assertNotEqual(window.instrument_table.item(0, 0).text(), "-")
        self.assertEqual(window.metric_detail_labels["数据源连接"].text(), "正常")
        self.assertTrue(provider.thread_ids)
        self.assertTrue(all(thread_id != main_thread_id for thread_id in provider.thread_ids))

        window.market_refresh_timer.stop()
        window.market_thread_pool.waitForDone(3000)
        window.close()
        app.processEvents()


if __name__ == "__main__":
    unittest.main()
