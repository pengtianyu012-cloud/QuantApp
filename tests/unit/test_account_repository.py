import unittest
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import APP_TIME_ZONE
from app.database import AccountRepository, AccountRepositoryError, connect_database
from app.models import OrderSide, OrderStatus
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
            Decimal("10.80"),
        )
        self.assertTrue(result.ok)

        restarted = TradingAppService(db_path=self.db_path)

        self.assertEqual(restarted.account.cash, first.account.cash)
        self.assertIn("000001.SZ", restarted.account.positions)
        self.assertEqual(len(restarted.account.orders), 1)
        self.assertEqual(len(restarted.account.fills), 1)


if __name__ == "__main__":
    unittest.main()
