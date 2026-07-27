import os
import unittest
from datetime import date, timedelta

from app.data.providers import AkSharePublicMarketDataProvider
from app.data.validators import validate_order_book, validate_quote


@unittest.skipUnless(
    os.environ.get("RUN_REAL_MARKET_DATA_TESTS") == "1",
    "设置 RUN_REAL_MARKET_DATA_TESTS=1 后运行真实行情测试",
)
class RealMarketDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = AkSharePublicMarketDataProvider()

    def test_real_latest_quote_and_five_level_order_book(self) -> None:
        quote = self.provider.get_latest_quotes(["600519.SH"])[0]
        order_book = self.provider.get_order_book("600519.SH")

        self.assertTrue(validate_quote(quote).ok)
        self.assertTrue(validate_order_book(order_book).ok)
        self.assertEqual(len(order_book.bids), 5)
        self.assertEqual(len(order_book.asks), 5)

    def test_real_daily_calendar_and_full_stock_list(self) -> None:
        today = date.today()
        bars = self.provider.get_daily_bars("600519.SH", today - timedelta(days=14), today)
        calendar = self.provider.get_trading_calendar(today - timedelta(days=7), today)
        instruments = self.provider.get_stock_list()

        self.assertTrue(bars)
        self.assertEqual(len(calendar), 8)
        self.assertGreater(len(instruments), 5_000)
        self.assertIn("600519.SH", {instrument.symbol for instrument in instruments})


if __name__ == "__main__":
    unittest.main()
