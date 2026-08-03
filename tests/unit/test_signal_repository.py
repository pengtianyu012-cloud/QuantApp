import unittest
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import APP_TIME_ZONE
from app.database import (
    AccountRepository,
    SignalDispatchStatus,
    SignalRepository,
    build_signal_id,
)
from app.models import OrderSide, OrderType
from app.portfolio import SimulatedAccount
from app.strategies import SignalDirection, StrategySignal


class SignalRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "signals.sqlite3"
        self.repository = SignalRepository(self.db_path)
        self.now = datetime(2030, 8, 6, 15, 5, tzinfo=APP_TIME_ZONE)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def signal(self, reason: str = "收盘趋势信号") -> StrategySignal:
        market_time = self.now.replace(hour=15, minute=0)
        return StrategySignal(
            signal_time=market_time,
            market_time=market_time,
            source="测试日线",
            symbol="000001.SZ",
            direction=SignalDirection.BUY,
            strength=Decimal("0.7000"),
            strategy_name="均线趋势",
            reason=reason,
            suggested_position_pct=Decimal("0.20"),
        )

    def test_duplicate_signal_is_inserted_once_with_deterministic_id(self) -> None:
        signal = self.signal()

        first = self.repository.persist_for_next_open(
            [signal],
            "SIM-001",
            date(2030, 8, 7),
            self.now,
        )
        second = self.repository.persist_for_next_open(
            [self.signal(reason="描述变化不应复制同一市场时点信号")],
            "SIM-001",
            date(2030, 8, 7),
            self.now,
        )

        self.assertEqual(first.inserted_count, 1)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(len(self.repository.list_for_account("SIM-001")), 1)
        self.assertEqual(first.records[0].signal_id, build_signal_id("SIM-001", signal))
        self.assertEqual(first.records[0].dispatch_status, SignalDispatchStatus.PENDING)

    def test_dispatch_status_and_signal_linked_order_survive_restart(self) -> None:
        signal = self.signal()
        record = self.repository.persist_for_next_open(
            [signal],
            "SIM-001",
            date(2030, 8, 7),
            self.now,
        ).records[0]
        account = SimulatedAccount()
        account.submit_order(
            signal.symbol,
            OrderSide.BUY,
            100,
            self.now,
            order_type=OrderType.NEXT_OPEN,
            eligible_at=datetime(2030, 8, 7, 9, 30, tzinfo=APP_TIME_ZONE),
            order_id="O-SIGNAL-TEST",
            signal_id=record.signal_id,
        )
        AccountRepository(self.db_path).save(account)
        self.repository.mark_dispatch(
            record.signal_id,
            SignalDispatchStatus.ORDER_CREATED,
            self.now,
            "NEXT_OPEN订单已创建",
            order_id="O-SIGNAL-TEST",
        )

        restored_signal = SignalRepository(self.db_path).list_for_account("SIM-001")[0]
        restored_account = AccountRepository(self.db_path).load("SIM-001")

        assert restored_account is not None
        self.assertEqual(
            restored_signal.dispatch_status,
            SignalDispatchStatus.ORDER_CREATED,
        )
        self.assertEqual(restored_signal.order_id, "O-SIGNAL-TEST")
        self.assertEqual(restored_account.orders[0].signal_id, record.signal_id)
        self.assertEqual(restored_account.orders[0].order_id, "O-SIGNAL-TEST")


if __name__ == "__main__":
    unittest.main()
