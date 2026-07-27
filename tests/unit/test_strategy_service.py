import unittest

from app.data.providers import MockMarketDataProvider
from app.services import StrategyService, StrategyServiceError
from app.strategies import StrategyState


class StrategyServiceTests(unittest.TestCase):
    def test_duplicate_start_is_rejected(self) -> None:
        service = StrategyService(MockMarketDataProvider())
        service.start("均线趋势")

        with self.assertRaises(StrategyServiceError):
            service.start("均线趋势")

    def test_run_daily_signals_updates_statuses(self) -> None:
        service = StrategyService(MockMarketDataProvider())

        signals = service.run_daily_signals(["000001.SZ"])
        statuses = {status.name: status for status in service.statuses()}

        self.assertTrue(signals)
        self.assertEqual(statuses["均线趋势"].state, StrategyState.RUNNING)
        self.assertGreater(statuses["均线趋势"].signal_count, 0)

    def test_realtime_demo_signal(self) -> None:
        service = StrategyService(MockMarketDataProvider())

        signals = service.run_realtime_demo_signal("000001.SZ")

        self.assertTrue(signals)
        self.assertEqual(signals[0].strategy_name, "盘口与量价演示")


if __name__ == "__main__":
    unittest.main()
