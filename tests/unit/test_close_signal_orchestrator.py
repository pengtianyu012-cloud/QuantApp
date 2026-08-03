import sqlite3
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.config import APP_TIME_ZONE, RuntimeMode
from app.data.providers import MockMarketDataProvider
from app.database import (
    AccountRepository,
    AccountRepositoryError,
    SignalDispatchStatus,
    SignalRepository,
    build_signal_id,
)
from app.database.connection import connect_database
from app.execution import ProviderTradingCalendar
from app.models import OrderSide, OrderStatus, OrderType, Position
from app.portfolio import SimulatedAccount
from app.risk import RiskManager
from app.services.close_signal_orchestrator import (
    CloseSignalOrchestrationError,
    CloseSignalOrchestrator,
    build_signal_order_id,
)
from app.strategies import SignalDirection, StrategySignal
from app.utils import FrozenClock


class CloseSignalOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.db_path = Path(self.temp_dir.name) / "close-cycle.sqlite3"
        self.now = datetime(2030, 8, 6, 15, 30, tzinfo=APP_TIME_ZONE)
        self.clock = FrozenClock(self.now)
        self.provider = MockMarketDataProvider(clock=self.clock)
        self.calendar = ProviderTradingCalendar(self.provider)
        self.account_repository = AccountRepository(self.db_path)
        self.signal_repository = SignalRepository(self.db_path)
        self.account = SimulatedAccount()
        self.account_repository.save(self.account)

    def orchestrator(
        self,
        mode: RuntimeMode = RuntimeMode.MOCK,
    ) -> CloseSignalOrchestrator:
        return CloseSignalOrchestrator(
            mode=mode,
            market_data=self.provider,
            account_repository=self.account_repository,
            signal_repository=self.signal_repository,
            trading_calendar=self.calendar,
            risk_manager=RiskManager(),
        )

    def signal(
        self,
        *,
        strategy_name: str = "均线趋势",
        symbol: str = "000001.SZ",
        direction: SignalDirection = SignalDirection.BUY,
        target: str = "0.20",
        minute: int = 0,
    ) -> StrategySignal:
        market_time = self.now.replace(hour=15, minute=minute)
        return StrategySignal(
            signal_time=market_time,
            market_time=market_time,
            source=self.provider.name,
            symbol=symbol,
            direction=direction,
            strength=Decimal("0.8"),
            strategy_name=strategy_name,
            reason="测试收盘信号",
            suggested_position_pct=Decimal(target),
        )

    def test_rejects_non_trading_day_and_pre_close_without_persisting(self) -> None:
        before_close = self.now.replace(hour=14, minute=59)
        saturday = self.now + timedelta(days=4)

        with self.assertRaisesRegex(CloseSignalOrchestrationError, "15:00"):
            self.orchestrator().run([self.signal()], self.account, before_close)
        with self.assertRaisesRegex(CloseSignalOrchestrationError, "不是交易日"):
            self.orchestrator().run([self.signal()], self.account, saturday)

        self.assertEqual(self.signal_repository.list_for_account(self.account.account_id), [])

    def test_creates_target_sized_next_open_order_and_persists_link(self) -> None:
        signal = self.signal()

        result = self.orchestrator().run([signal], self.account, self.now)

        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        self.assertEqual(result.inserted_count, 1)
        self.assertEqual(result.orders_created_count, 1)
        self.assertTrue(result.account_saved)
        self.assertEqual(len(restored.orders), 1)
        order = restored.orders[0]
        expected_signal_id = build_signal_id(self.account.account_id, signal)
        self.assertEqual(order.order_id, build_signal_order_id(expected_signal_id))
        self.assertEqual(order.signal_id, expected_signal_id)
        self.assertEqual(order.quantity, 1800)
        self.assertEqual(order.order_type, OrderType.NEXT_OPEN)
        self.assertEqual(order.status, OrderStatus.PENDING_NEXT_OPEN)
        self.assertEqual(order.eligible_at, result.scheduled_for)
        self.assertEqual(order.eligible_at.date().isoformat(), "2030-08-07")
        record = self.signal_repository.list_for_account(self.account.account_id)[0]
        self.assertEqual(record.dispatch_status, SignalDispatchStatus.ORDER_CREATED)
        self.assertEqual(record.order_id, order.order_id)

    def test_duplicate_run_and_restart_reconcile_without_duplicate_order(self) -> None:
        signal = self.signal()
        first = self.orchestrator().run([signal], self.account, self.now)
        signal_id = build_signal_id(self.account.account_id, signal)
        with connect_database(self.db_path) as connection:
            connection.execute(
                "UPDATE signals SET dispatch_status = ?, order_id = NULL, "
                "dispatch_message = '', processed_at = NULL WHERE signal_id = ?",
                (SignalDispatchStatus.PENDING.value, signal_id),
            )
        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None

        second = self.orchestrator().run([signal], restored, self.now)

        restarted = self.account_repository.load(self.account.account_id)
        assert restarted is not None
        self.assertEqual(first.orders_created_count, 1)
        self.assertEqual(second.inserted_count, 0)
        self.assertEqual(second.orders_created_count, 0)
        self.assertEqual(len(restarted.orders), 1)
        self.assertEqual(second.outcomes[0].status, SignalDispatchStatus.ORDER_CREATED)
        self.assertIn("恢复", second.outcomes[0].message)

    def test_research_mode_persists_signal_without_reading_market_or_ordering(self) -> None:
        signal = self.signal()
        with patch.object(
            self.provider,
            "get_latest_quotes",
            side_effect=AssertionError("research模式不应为派单读取行情"),
        ):
            result = self.orchestrator(RuntimeMode.RESEARCH).run(
                [signal],
                self.account,
                self.now,
            )

        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        self.assertFalse(result.account_saved)
        self.assertEqual(result.orders_created_count, 0)
        self.assertEqual(restored.orders, [])
        self.assertEqual(result.outcomes[0].status, SignalDispatchStatus.SKIPPED)
        self.assertIn("research", result.outcomes[0].message)

    def test_pending_buy_reservation_prevents_duplicate_target_exposure(self) -> None:
        first = self.signal(strategy_name="均线趋势", target="0.20", minute=0)
        second = self.signal(strategy_name="动量选股", target="0.18", minute=1)

        result = self.orchestrator().run([first, second], self.account, self.now)

        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        statuses = {item.signal_id: item.status for item in result.outcomes}
        self.assertEqual(len(restored.orders), 1)
        self.assertEqual(restored.orders[0].quantity, 1800)
        self.assertEqual(
            statuses[build_signal_id(self.account.account_id, first)],
            SignalDispatchStatus.ORDER_CREATED,
        )
        self.assertEqual(
            statuses[build_signal_id(self.account.account_id, second)],
            SignalDispatchStatus.SKIPPED,
        )

    def test_drawdown_blocks_buy_but_sell_signal_still_creates_order(self) -> None:
        self.account.cash = Decimal("70000")
        self.account.positions["000001.SZ"] = Position(
            symbol="000001.SZ",
            name="平安银行",
            quantity=1000,
            available_quantity=1000,
            cost_price=Decimal("10.80"),
            last_buy_date=self.now.date() - timedelta(days=1),
        )
        self.account_repository.save(self.account)
        buy_signal = self.signal(
            strategy_name="均线趋势",
            direction=SignalDirection.BUY,
            target="0.30",
            minute=0,
        )
        sell_signal = self.signal(
            strategy_name="风险退出",
            direction=SignalDirection.SELL,
            target="0",
            minute=1,
        )

        result = self.orchestrator().run(
            [buy_signal, sell_signal],
            self.account,
            self.now,
        )

        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        outcomes = {item.signal_id: item for item in result.outcomes}
        self.assertGreaterEqual(restored.current_drawdown, Decimal("0.15"))
        self.assertEqual(len(restored.orders), 1)
        self.assertEqual(restored.orders[0].side, OrderSide.SELL)
        self.assertEqual(restored.orders[0].quantity, 1000)
        self.assertEqual(
            outcomes[build_signal_id(self.account.account_id, buy_signal)].status,
            SignalDispatchStatus.REJECTED,
        )
        self.assertIn(
            "最大回撤",
            outcomes[build_signal_id(self.account.account_id, buy_signal)].message,
        )
        self.assertEqual(
            outcomes[build_signal_id(self.account.account_id, sell_signal)].status,
            SignalDispatchStatus.ORDER_CREATED,
        )

    def test_sell_target_is_percentage_of_total_assets(self) -> None:
        self.account.cash = Decimal("89200")
        self.account.positions["000001.SZ"] = Position(
            symbol="000001.SZ",
            name="平安银行",
            quantity=1000,
            available_quantity=1000,
            cost_price=Decimal("10.80"),
            last_buy_date=self.now.date() - timedelta(days=1),
        )
        self.account_repository.save(self.account)
        sell_signal = self.signal(
            direction=SignalDirection.SELL,
            target="0.05",
        )

        self.orchestrator().run([sell_signal], self.account, self.now)

        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        self.assertEqual(len(restored.orders), 1)
        self.assertEqual(restored.orders[0].side, OrderSide.SELL)
        self.assertEqual(restored.orders[0].quantity, 538)

    def test_account_save_failure_leaves_signal_pending_for_retry(self) -> None:
        signal = self.signal()
        with patch.object(
            self.account_repository,
            "save",
            side_effect=AccountRepositoryError("模拟写盘失败"),
        ):
            with self.assertRaisesRegex(CloseSignalOrchestrationError, "保持 pending"):
                self.orchestrator().run([signal], self.account, self.now)

        records = self.signal_repository.list_for_account(self.account.account_id)
        self.assertEqual(records[0].dispatch_status, SignalDispatchStatus.PENDING)
        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        self.assertEqual(restored.orders, [])

        retry = self.orchestrator().run([signal], restored, self.now)
        self.assertEqual(retry.inserted_count, 0)
        self.assertEqual(retry.orders_created_count, 1)

    def test_database_unique_signal_link_is_last_line_of_defense(self) -> None:
        signal = self.signal()
        self.orchestrator().run([signal], self.account, self.now)
        restored = self.account_repository.load(self.account.account_id)
        assert restored is not None
        duplicate = restored.orders[0]
        restored.orders.append(
            type(duplicate)(
                **{
                    **duplicate.__dict__,
                    "order_id": "O-DUPLICATE",
                }
            )
        )

        with self.assertRaises((AccountRepositoryError, sqlite3.IntegrityError)):
            self.account_repository.save(restored)


if __name__ == "__main__":
    unittest.main()
