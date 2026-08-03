import unittest
from datetime import date
from decimal import Decimal

from app.backtest import DailyBacktestEngine
from app.data.providers import MockMarketDataProvider
from app.strategies import MovingAverageTrendStrategy


class BacktestEngineTests(unittest.TestCase):
    def test_daily_backtest_fills_after_signal_day(self) -> None:
        provider = MockMarketDataProvider()
        engine = DailyBacktestEngine(provider)
        strategy = MovingAverageTrendStrategy({"short_window": 3, "long_window": 5})

        result = engine.run(
            strategy,
            "000001.SZ",
            date(2030, 4, 1),
            date(2030, 8, 6),
            initial_cash=Decimal("100000"),
            quantity=100,
        )

        self.assertTrue(result.trades)
        trade = result.trades[0]
        self.assertLess(trade.signal_time, trade.fill_time)
        self.assertGreater(result.final_cash, Decimal("0"))


if __name__ == "__main__":
    unittest.main()
