import unittest
from datetime import date

from app.data.providers import MockMarketDataProvider
from app.data.validators import validate_order_book, validate_quote


class MockMarketDataProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockMarketDataProvider()

    def test_health_check_is_ok(self) -> None:
        health = self.provider.health_check()

        self.assertTrue(health.ok)
        self.assertEqual(health.provider, "Mock行情")

    def test_stock_list_contains_hs_a_shares_and_exclusion_flags(self) -> None:
        stocks = self.provider.get_stock_list()
        symbols = {stock.symbol for stock in stocks}

        self.assertIn("600519.SH", symbols)
        self.assertIn("000001.SZ", symbols)
        self.assertTrue(any(stock.is_st for stock in stocks))

    def test_latest_quote_is_valid(self) -> None:
        quotes = self.provider.get_latest_quotes(["600519.SH"])

        self.assertEqual(len(quotes), 1)
        self.assertTrue(validate_quote(quotes[0]).ok)
        self.assertEqual(quotes[0].source, "Mock行情")

    def test_order_book_has_five_levels(self) -> None:
        order_book = self.provider.get_order_book("600519.SH")

        self.assertEqual(len(order_book.bids), 5)
        self.assertEqual(len(order_book.asks), 5)
        self.assertTrue(validate_order_book(order_book).ok)

    def test_trading_calendar_marks_weekends_closed(self) -> None:
        calendar = self.provider.get_trading_calendar(date(2030, 8, 3), date(2030, 8, 5))

        self.assertFalse(calendar[0].is_open)
        self.assertFalse(calendar[1].is_open)
        self.assertTrue(calendar[2].is_open)

    def test_daily_bars_do_not_include_weekends(self) -> None:
        bars = self.provider.get_daily_bars("600519.SH", date(2030, 8, 2), date(2030, 8, 5))

        self.assertEqual(
            [bar.bar_time.date().isoformat() for bar in bars], ["2030-08-02", "2030-08-05"]
        )


if __name__ == "__main__":
    unittest.main()
