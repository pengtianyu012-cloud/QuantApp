import unittest
from dataclasses import replace
from datetime import datetime
from decimal import Decimal

from app.data.providers import MockMarketDataProvider
from app.execution import SimulatedMatcher
from app.models import Order, OrderSide, OrderStatus, OrderType


class ExecutionSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = MockMarketDataProvider()
        self.instrument = self.provider.get_stock_list()[0]
        self.quote = self.provider.get_latest_quotes([self.instrument.symbol])[0]
        self.order = Order(
            order_id="O-TEST",
            account_id="SIM-001",
            symbol=self.instrument.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.NEXT_OPEN,
            quantity=1000,
            submitted_at=datetime(2026, 7, 27, 15, 1),
        )
        self.matcher = SimulatedMatcher()

    def test_suspended_stock_is_deferred(self) -> None:
        instrument = replace(self.instrument, is_suspended=True)

        result = self.matcher.evaluate(
            self.order, self.quote, instrument, datetime(2026, 7, 28, 9, 30)
        )

        self.assertEqual(result.status, OrderStatus.DEFERRED)
        self.assertIn("停牌", result.reason)

    def test_stale_quote_is_deferred(self) -> None:
        quote = replace(self.quote, delay_seconds=60)

        result = self.matcher.evaluate(
            self.order, quote, self.instrument, datetime(2026, 7, 28, 9, 30)
        )

        self.assertEqual(result.status, OrderStatus.DEFERRED)
        self.assertIn("过期", result.reason)

    def test_limit_up_blocks_buy(self) -> None:
        quote = replace(self.quote, last_price=Decimal("1855.48"), prev_close=Decimal("1686.80"))

        result = self.matcher.evaluate(
            self.order, quote, self.instrument, datetime(2026, 7, 28, 9, 30)
        )

        self.assertEqual(result.status, OrderStatus.DEFERRED)
        self.assertIn("涨停", result.reason)

    def test_limit_down_blocks_sell(self) -> None:
        sell_order = replace(self.order, side=OrderSide.SELL)
        quote = replace(self.quote, last_price=Decimal("1518.12"), prev_close=Decimal("1686.80"))

        result = self.matcher.evaluate(
            sell_order, quote, self.instrument, datetime(2026, 7, 28, 9, 30)
        )

        self.assertEqual(result.status, OrderStatus.DEFERRED)
        self.assertIn("跌停", result.reason)

    def test_volume_participation_can_partially_fill(self) -> None:
        result = self.matcher.evaluate(
            self.order,
            self.quote,
            self.instrument,
            datetime(2026, 7, 28, 9, 30),
            interval_volume=5_000,
        )

        self.assertEqual(result.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(result.fill_quantity, 500)
        self.assertIsNotNone(result.fill_price)

    def test_missing_order_book_marks_degraded_model(self) -> None:
        result = self.matcher.evaluate(
            self.order,
            self.quote,
            self.instrument,
            datetime(2026, 7, 28, 9, 30),
            has_order_book=False,
        )

        self.assertTrue(result.degraded_model)
        self.assertIn("降级", result.reason)


if __name__ == "__main__":
    unittest.main()
