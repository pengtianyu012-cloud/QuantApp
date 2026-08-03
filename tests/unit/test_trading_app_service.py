import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.config import APP_TIME_ZONE
from app.data.providers import MockMarketDataProvider
from app.database import AccountRepository, SignalRepository
from app.models import OrderSide, OrderStatus, OrderType
from app.services import CloseSignalOrchestrationError, TradingAppService
from app.strategies import SignalDirection, StrategySignal
from app.utils import FrozenClock


class TradingAppServiceTests(unittest.TestCase):
    def test_dashboard_quote_delay_uses_injected_current_time(self) -> None:
        clock = FrozenClock(datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE))
        service = TradingAppService(persist_account=False, clock=clock)

        initial = service.get_dashboard_metrics()
        clock.advance(timedelta(seconds=31))
        aged = service.get_dashboard_metrics()

        self.assertEqual(initial["quote_delay"], "0秒")
        self.assertEqual(aged["quote_delay"], "31秒")

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

    def test_close_cycle_validates_time_before_running_strategies(self) -> None:
        with TemporaryDirectory() as temp_dir:
            clock = FrozenClock(datetime(2030, 8, 6, 14, 59, tzinfo=APP_TIME_ZONE))
            db_path = Path(temp_dir) / "service-close.sqlite3"
            service = TradingAppService(
                account_repository=AccountRepository(db_path),
                signal_repository=SignalRepository(db_path),
                clock=clock,
            )

            with patch.object(
                service.strategy_service,
                "run_daily_signals",
                side_effect=AssertionError("收盘前不应运行策略"),
            ):
                with self.assertRaises(CloseSignalOrchestrationError):
                    service.run_close_signal_cycle(["000001.SZ"])

    def test_dispatch_close_signals_refreshes_service_account_from_database(self) -> None:
        with TemporaryDirectory() as temp_dir:
            now = datetime(2030, 8, 6, 15, 30, tzinfo=APP_TIME_ZONE)
            clock = FrozenClock(now)
            db_path = Path(temp_dir) / "service-dispatch.sqlite3"
            service = TradingAppService(db_path=db_path, clock=clock)
            signal = StrategySignal(
                signal_time=now.replace(hour=15, minute=0),
                market_time=now.replace(hour=15, minute=0),
                source=service.market_data.name,
                symbol="000001.SZ",
                direction=SignalDirection.BUY,
                strength=Decimal("0.8"),
                strategy_name="均线趋势",
                reason="服务层收盘派发测试",
                suggested_position_pct=Decimal("0.20"),
            )

            result = service.dispatch_close_signals([signal])

            self.assertEqual(result.orders_created_count, 1)
            self.assertEqual(len(service.account.orders), 1)
            self.assertEqual(service.account.orders[0].status, OrderStatus.PENDING_NEXT_OPEN)
            self.assertIsNotNone(service.account.orders[0].signal_id)


if __name__ == "__main__":
    unittest.main()
