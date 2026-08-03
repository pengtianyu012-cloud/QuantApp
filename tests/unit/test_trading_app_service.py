import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from app.config import APP_TIME_ZONE
from app.data.providers import MockMarketDataProvider
from app.models import OrderSide, OrderStatus, OrderType
from app.services import TradingAppService
from app.utils import FrozenClock


class TradingAppServiceTests(unittest.TestCase):
    def test_manual_buy_updates_account_position_order_and_fill(self) -> None:
        clock = FrozenClock(datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE))
        service = TradingAppService(persist_account=False, clock=clock)

        result = service.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            100,
            Decimal("10.81"),
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.order)
        self.assertIsNotNone(result.fill)
        self.assertIn("000001.SZ", service.account.positions)
        self.assertEqual(service.account.orders[-1].status, OrderStatus.FILLED)
        self.assertEqual(len(service.account.fills), 1)

    def test_risk_rejects_oversized_single_position_before_order_creation(self) -> None:
        clock = FrozenClock(datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE))
        service = TradingAppService(persist_account=False, clock=clock)

        result = service.place_manual_order(
            OrderSide.BUY,
            "600519.SH",
            100,
            Decimal("1688.00"),
        )

        self.assertFalse(result.ok)
        self.assertIsNone(result.order)
        self.assertIn("单股", result.message)
        self.assertEqual(len(service.account.orders), 0)

    def test_invalid_buy_lot_is_rejected(self) -> None:
        clock = FrozenClock(datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE))
        service = TradingAppService(persist_account=False, clock=clock)

        result = service.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            150,
            Decimal("10.80"),
        )

        self.assertFalse(result.ok)
        self.assertIn("100股整数倍", result.message)

    def test_background_provider_reads_snapshots_without_network_on_getters(self) -> None:
        service = TradingAppService(
            market_data=MockMarketDataProvider(),
            persist_account=False,
            background_market_data=True,
        )

        self.assertEqual(service.get_watchlist_quotes(), [])
        self.assertEqual(service.get_instruments(), [])

        service.refresh_watchlist_market_data()
        service.refresh_instruments()

        self.assertEqual(len(service.get_watchlist_quotes()), 4)
        self.assertGreater(len(service.get_instruments()), 4)
        self.assertIsNotNone(service.provider_health())

    def test_next_open_order_is_pending_same_day_and_fills_next_trading_day(self) -> None:
        clock = FrozenClock(datetime(2030, 8, 5, 14, 0, tzinfo=APP_TIME_ZONE))
        service = TradingAppService(persist_account=False, clock=clock)

        submitted = service.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            100,
            order_type=OrderType.NEXT_OPEN,
        )

        self.assertTrue(submitted.ok)
        self.assertIsNone(submitted.fill)
        self.assertEqual(submitted.order.status, OrderStatus.PENDING_NEXT_OPEN)

        clock.advance(timedelta(days=1, hours=-4, minutes=-30))
        assert isinstance(service.market_data, MockMarketDataProvider)
        service.market_data.quote_cache.clear()
        filled = service.process_pending_order(submitted.order.order_id)

        self.assertTrue(filled.ok)
        self.assertIsNotNone(filled.fill)
        self.assertEqual(filled.order.status, OrderStatus.FILLED)


if __name__ == "__main__":
    unittest.main()
