import unittest
from datetime import date
from decimal import Decimal

from app.data.providers import MockMarketDataProvider
from app.strategies import (
    LowValuationFactorStrategy,
    MomentumSelectionStrategy,
    MovingAverageTrendStrategy,
    OrderBookVolumePriceDemoStrategy,
    SignalDirection,
)


class BuiltinStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockMarketDataProvider()
        self.bars = self.provider.get_daily_bars("000001.SZ", date(2026, 4, 1), date(2026, 7, 27))

    def test_moving_average_strategy_generates_buy_signal(self) -> None:
        strategy = MovingAverageTrendStrategy()
        signals = strategy.generate_from_bars("000001.SZ", self.bars)

        self.assertTrue(signals)
        self.assertEqual(signals[0].direction, SignalDirection.BUY)
        self.assertEqual(signals[0].strategy_name, "均线趋势")

    def test_momentum_strategy_generates_buy_signal(self) -> None:
        strategy = MomentumSelectionStrategy({"lookback": 20, "threshold": "0.01"})
        signals = strategy.generate_from_bars("000001.SZ", self.bars)

        self.assertTrue(signals)
        self.assertIn("动量", signals[0].reason)

    def test_low_valuation_signal_includes_mock_warning(self) -> None:
        strategy = LowValuationFactorStrategy()
        indicators = self.provider.get_financial_indicators(["000001.SZ"], date(2026, 6, 30))["000001.SZ"]
        signals = strategy.generate_from_financials("000001.SZ", indicators, self.bars[-1].bar_time, self.provider.name)

        self.assertTrue(signals)
        self.assertIn("Mock数据", signals[0].reason)

    def test_order_book_demo_requires_minimum_samples(self) -> None:
        strategy = OrderBookVolumePriceDemoStrategy({"min_samples": 2})
        quote = self.provider.get_latest_quotes(["000001.SZ"])[0]
        book = self.provider.get_order_book("000001.SZ")

        strategy.on_market_data(quote, book)
        self.assertEqual(strategy.generate_signals(), [])

        moved_quote = type(quote)(**{**quote.__dict__, "last_price": quote.last_price + Decimal("0.01")})
        strategy.on_market_data(moved_quote, book)
        self.assertTrue(strategy.generate_signals())


if __name__ == "__main__":
    unittest.main()
