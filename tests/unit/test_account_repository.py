import unittest
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import APP_TIME_ZONE
from app.database import AccountRepository, AccountRepositoryError, connect_database
from app.models import OrderSide, OrderStatus, OrderType
from app.portfolio import SimulatedAccount
from app.services import TradingAppService
from app.utils import FrozenClock


class AccountRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "account.sqlite3"
        self.repository = AccountRepository(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_account_round_trip_preserves_cash_t_plus_one_orders_and_fills(self) -> None:
        account = SimulatedAccount()
        trade_time = datetime(2026, 7, 27, 9, 30, tzinfo=APP_TIME_ZONE)
        order = account.submit_order("000001.SZ", OrderSide.BUY, 100, trade_time)
        account.apply_fill(order, Decimal("10.80"), 100, trade_time, stock_name="平安银行")
        account.update_order_status(order, OrderStatus.FILLED, "测试成交")

        self.repository.save(account)
        restored = self.repository.load(account.account_id)

        self.assertIsNotNone(restored)
        assert restored is not None
        self.assertEqual(restored.cash, account.cash)
        self.assertEqual(restored.positions["000001.SZ"].name, "平安银行")
        self.assertEqual(restored.positions["000001.SZ"].available_quantity, 0)
        self.assertEqual(restored.positions["000001.SZ"].last_buy_date.isoformat(), "2026-07-27")
        self.assertEqual(restored.orders[0].status, OrderStatus.FILLED)
        self.assertEqual(restored.fills[0].price, Decimal("10.80"))
        self.assertIsNotNone(restored.orders[0].submitted_at.utcoffset())

    def test_repeated_save_is_idempotent_and_next_day_state_persists(self) -> None:
        account = SimulatedAccount()
        trade_time = datetime(2026, 7, 27, 9, 30, tzinfo=APP_TIME_ZONE)
        order = account.submit_order("000001.SZ", OrderSide.BUY, 100, trade_time)
        account.apply_fill(order, Decimal("10.80"), 100, trade_time)
        account.update_order_status(order, OrderStatus.FILLED)

        self.repository.save(account)
        account.advance_trading_day()
        self.repository.save(account)
        self.repository.save(account)

        restored = self.repository.load(account.account_id)
        assert restored is not None
        self.assertEqual(restored.positions["000001.SZ"].available_quantity, 100)
        with connect_database(self.db_path) as connection:
            order_count = connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
            fill_count = connection.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
        self.assertEqual(order_count, 1)
        self.assertEqual(fill_count, 1)

    def test_failed_snapshot_rolls_back_previous_state(self) -> None:
        account = SimulatedAccount()
        trade_time = datetime(2026, 7, 27, 9, 30, tzinfo=APP_TIME_ZONE)
        order = account.submit_order("000001.SZ", OrderSide.BUY, 100, trade_time)
        self.repository.save(account)
        account.orders.append(order)

        with self.assertRaises(AccountRepositoryError):
            self.repository.save(account)

        restored = self.repository.load(account.account_id)
        assert restored is not None
        self.assertEqual(len(restored.orders), 1)

    def test_service_restart_restores_persisted_account(self) -> None:
        clock = FrozenClock(datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE))
        first = TradingAppService(db_path=self.db_path, clock=clock)
        result = first.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            100,
            Decimal("10.81"),
        )
        self.assertTrue(result.ok)

        restarted = TradingAppService(db_path=self.db_path)

        self.assertEqual(restarted.account.cash, first.account.cash)
        self.assertIn("000001.SZ", restarted.account.positions)
        self.assertEqual(len(restarted.account.orders), 1)
        self.assertEqual(len(restarted.account.fills), 1)

    def test_restart_restores_partial_order_snapshots_drawdown_and_fees(self) -> None:
        account = SimulatedAccount()
        trade_time = datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE)
        order = account.submit_order(
            "000001.SZ",
            OrderSide.BUY,
            6000,
            trade_time,
            order_type=OrderType.MARKET,
        )
        account.apply_fill(
            order,
            Decimal("10.01"),
            5000,
            trade_time,
            reference_price=Decimal("10.00"),
        )
        account.record_snapshot(
            datetime(2030, 8, 6, 15, 0, tzinfo=APP_TIME_ZONE),
            {"000001.SZ": Decimal("7.00")},
        )

        self.repository.save(account)
        restored = self.repository.load(account.account_id)

        assert restored is not None
        restored_order = restored.orders[0]
        self.assertEqual(restored_order.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(restored_order.filled_quantity, 5000)
        self.assertEqual(restored_order.remaining_quantity, 1000)
        self.assertEqual(restored.peak_total_assets, account.peak_total_assets)
        self.assertEqual(restored.current_drawdown, account.current_drawdown)
        self.assertEqual(restored.max_drawdown, account.max_drawdown)
        self.assertGreaterEqual(restored.current_drawdown, Decimal("0.15"))
        self.assertEqual(restored.cumulative_fees, account.cumulative_fees)
        self.assertEqual(restored.snapshots, account.snapshots)
        self.assertEqual(restored.fills[0].market_impact, Decimal("30.00"))
        self.assertEqual(restored.fills[0].reference_price, Decimal("10.00"))

    def test_order_fill_and_event_history_is_append_only(self) -> None:
        account = SimulatedAccount()
        trade_time = datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE)
        order = account.submit_order(
            "000001.SZ",
            OrderSide.BUY,
            100,
            trade_time,
            order_type=OrderType.MARKET,
        )
        account.apply_fill(order, Decimal("10.01"), 100, trade_time)
        self.repository.save(account)
        expected_order_ids = {item.order_id for item in account.orders}
        expected_fill_ids = {item.fill_id for item in account.fills}
        expected_event_ids = {item.event_id for item in account.order_events}

        current_state_only = deepcopy(account)
        current_state_only.orders.clear()
        current_state_only.fills.clear()
        current_state_only.order_events.clear()
        self.repository.save(current_state_only)
        restored = self.repository.load(account.account_id)

        assert restored is not None
        self.assertEqual({item.order_id for item in restored.orders}, expected_order_ids)
        self.assertEqual({item.fill_id for item in restored.fills}, expected_fill_ids)
        self.assertEqual(
            {item.event_id for item in restored.order_events},
            expected_event_ids,
        )


if __name__ == "__main__":
    unittest.main()
