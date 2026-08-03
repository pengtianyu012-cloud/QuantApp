from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.config import APP_TIME_ZONE
from app.database.connection import connect_database, initialize_database
from app.models import (
    Fill,
    Order,
    OrderEvent,
    OrderSide,
    OrderStatus,
    OrderType,
    PortfolioSnapshot,
    Position,
)
from app.portfolio.account import SimulatedAccount


class AccountRepositoryError(RuntimeError):
    """账户快照无法可靠保存或恢复。"""


class AccountRepository:
    """使用单个 SQLite 事务保存和恢复完整模拟账户快照。"""

    def __init__(self, db_path: Path | None = None) -> None:
        try:
            self.db_path = initialize_database(db_path)
        except (sqlite3.Error, RuntimeError) as exc:
            raise AccountRepositoryError(f"数据库初始化失败：{exc}") from exc

    def load(self, account_id: str) -> SimulatedAccount | None:
        try:
            with connect_database(self.db_path) as connection:
                account_row = connection.execute(
                    "SELECT * FROM accounts WHERE account_id = ?", (account_id,)
                ).fetchone()
                if account_row is None:
                    return None

                position_rows = connection.execute(
                    "SELECT * FROM positions WHERE account_id = ? ORDER BY symbol",
                    (account_id,),
                ).fetchall()
                order_rows = connection.execute(
                    "SELECT * FROM orders WHERE account_id = ? ORDER BY submitted_at, order_id",
                    (account_id,),
                ).fetchall()
                fill_rows = connection.execute(
                    "SELECT fills.* FROM fills "
                    "JOIN orders ON orders.order_id = fills.order_id "
                    "WHERE orders.account_id = ? ORDER BY fills.filled_at, fills.fill_id",
                    (account_id,),
                ).fetchall()
                event_rows = connection.execute(
                    "SELECT order_events.* FROM order_events "
                    "JOIN orders ON orders.order_id = order_events.order_id "
                    "WHERE orders.account_id = ? "
                    "ORDER BY order_events.event_time, order_events.event_id",
                    (account_id,),
                ).fetchall()
                snapshot_rows = connection.execute(
                    "SELECT * FROM portfolio_snapshots WHERE account_id = ? "
                    "ORDER BY snapshot_time",
                    (account_id,),
                ).fetchall()

            positions = {
                str(row["symbol"]): Position(
                    symbol=str(row["symbol"]),
                    name=str(row["name"] or row["symbol"]),
                    quantity=int(row["quantity"]),
                    available_quantity=int(row["available_quantity"]),
                    cost_price=Decimal(str(row["cost_price"])),
                    last_buy_date=(
                        datetime.fromisoformat(str(row["last_buy_date"])).date()
                        if row["last_buy_date"]
                        else None
                    ),
                )
                for row in position_rows
            }
            orders = [self._row_to_order(row) for row in order_rows]
            fills = [self._row_to_fill(row) for row in fill_rows]
            order_events = [self._row_to_order_event(row) for row in event_rows]
            snapshots = [self._row_to_snapshot(row) for row in snapshot_rows]
            return SimulatedAccount(
                account_id=str(account_row["account_id"]),
                name=str(account_row["name"]),
                initial_cash=Decimal(str(account_row["initial_cash"])),
                cash=Decimal(str(account_row["cash"])),
                positions=positions,
                orders=orders,
                fills=fills,
                order_events=order_events,
                snapshots=snapshots,
                peak_total_assets=Decimal(str(account_row["peak_total_assets"])),
                current_drawdown=Decimal(str(account_row["current_drawdown"])),
                max_drawdown=Decimal(str(account_row["max_drawdown"])),
                cumulative_fees=Decimal(str(account_row["cumulative_fees"])),
            )
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise AccountRepositoryError(f"账户恢复失败：{exc}") from exc

    def save(self, account: SimulatedAccount) -> None:
        self._validate_unique_audit_ids(account)
        now = datetime.now(UTC).isoformat()
        try:
            with connect_database(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO accounts (
                        account_id, name, initial_cash, cash, total_assets,
                        peak_total_assets, current_drawdown, max_drawdown,
                        cumulative_fees, risk_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id) DO UPDATE SET
                        name = excluded.name,
                        initial_cash = excluded.initial_cash,
                        cash = excluded.cash,
                        total_assets = excluded.total_assets,
                        peak_total_assets = excluded.peak_total_assets,
                        current_drawdown = excluded.current_drawdown,
                        max_drawdown = excluded.max_drawdown,
                        cumulative_fees = excluded.cumulative_fees,
                        risk_status = excluded.risk_status,
                        updated_at = excluded.updated_at
                    """,
                    (
                        account.account_id,
                        account.name,
                        str(account.initial_cash),
                        str(account.cash),
                        str(account.current_total_assets),
                        str(account.peak_total_assets),
                        str(account.current_drawdown),
                        str(account.max_drawdown),
                        str(account.cumulative_fees),
                        account.risk_status,
                        now,
                        now,
                    ),
                )

                connection.execute(
                    "DELETE FROM positions WHERE account_id = ?", (account.account_id,)
                )
                connection.executemany(
                    """
                    INSERT INTO positions (
                        account_id, symbol, name, quantity, available_quantity,
                        cost_price, market_value, last_price, last_buy_date, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            account.account_id,
                            position.symbol,
                            position.name,
                            position.quantity,
                            position.available_quantity,
                            str(position.cost_price),
                            str(position.market_value(position.cost_price)),
                            str(position.cost_price),
                            position.last_buy_date.isoformat() if position.last_buy_date else None,
                            now,
                        )
                        for position in account.positions.values()
                    ],
                )
                connection.executemany(
                    """
                    INSERT INTO orders (
                        order_id, account_id, symbol, side, order_type, quantity,
                        limit_price, status, reason, eligible_at, filled_quantity,
                        remaining_quantity, submitted_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(order_id) DO UPDATE SET
                        account_id = excluded.account_id,
                        symbol = excluded.symbol,
                        side = excluded.side,
                        order_type = excluded.order_type,
                        quantity = excluded.quantity,
                        limit_price = excluded.limit_price,
                        status = excluded.status,
                        reason = excluded.reason,
                        eligible_at = excluded.eligible_at,
                        filled_quantity = excluded.filled_quantity,
                        remaining_quantity = excluded.remaining_quantity,
                        updated_at = excluded.updated_at
                    """,
                    [
                        (
                            order.order_id,
                            order.account_id,
                            order.symbol,
                            order.side.value,
                            order.order_type.value,
                            order.quantity,
                            str(order.limit_price) if order.limit_price is not None else None,
                            order.status.value,
                            order.reason,
                            self._datetime_to_iso(order.eligible_at)
                            if order.eligible_at is not None
                            else None,
                            order.filled_quantity,
                            order.remaining_quantity,
                            self._datetime_to_iso(order.submitted_at),
                            self._datetime_to_iso(
                                order.updated_at or order.submitted_at
                            ),
                        )
                        for order in account.orders
                    ],
                )
                connection.executemany(
                    """
                    INSERT INTO fills (
                        fill_id, order_id, symbol, side, quantity, price,
                        commission, tax, transfer_fee, slippage,
                        market_impact, reference_price, degraded_model, filled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(fill_id) DO NOTHING
                    """,
                    [
                        (
                            fill.fill_id,
                            fill.order_id,
                            fill.symbol,
                            fill.side.value,
                            fill.quantity,
                            str(fill.price),
                            str(fill.commission),
                            str(fill.tax),
                            str(fill.transfer_fee),
                            str(fill.slippage),
                            str(fill.market_impact),
                            str(fill.reference_price)
                            if fill.reference_price is not None
                            else None,
                            int(fill.degraded_model),
                            self._datetime_to_iso(fill.filled_at),
                        )
                        for fill in account.fills
                    ],
                )
                connection.executemany(
                    """
                    INSERT INTO order_events (
                        event_id, order_id, status, event_time, reason,
                        filled_quantity, remaining_quantity
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(event_id) DO NOTHING
                    """,
                    [
                        (
                            event.event_id,
                            event.order_id,
                            event.status.value,
                            self._datetime_to_iso(event.event_time),
                            event.reason,
                            event.filled_quantity,
                            event.remaining_quantity,
                        )
                        for event in account.order_events
                    ],
                )
                connection.executemany(
                    """
                    INSERT INTO portfolio_snapshots (
                        account_id, trade_date, snapshot_time, cash, market_value,
                        total_assets, net_value, peak_total_assets,
                        current_drawdown, daily_pnl, cumulative_return,
                        max_drawdown, cumulative_fees
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(account_id, trade_date) DO UPDATE SET
                        snapshot_time = excluded.snapshot_time,
                        cash = excluded.cash,
                        market_value = excluded.market_value,
                        total_assets = excluded.total_assets,
                        net_value = excluded.net_value,
                        peak_total_assets = excluded.peak_total_assets,
                        current_drawdown = excluded.current_drawdown,
                        daily_pnl = excluded.daily_pnl,
                        cumulative_return = excluded.cumulative_return,
                        max_drawdown = excluded.max_drawdown,
                        cumulative_fees = excluded.cumulative_fees
                    """,
                    self._snapshot_rows(account),
                )
        except sqlite3.Error as exc:
            raise AccountRepositoryError(f"账户保存失败：{exc}") from exc

    @staticmethod
    def _datetime_to_iso(value: datetime) -> str:
        if value.tzinfo is None or value.utcoffset() is None:
            value = value.replace(tzinfo=APP_TIME_ZONE)
        return value.isoformat()

    @staticmethod
    def _parse_datetime(value: str) -> datetime:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            return parsed.replace(tzinfo=APP_TIME_ZONE)
        return parsed

    @classmethod
    def _row_to_order(cls, row: sqlite3.Row) -> Order:
        return Order(
            order_id=str(row["order_id"]),
            account_id=str(row["account_id"]),
            symbol=str(row["symbol"]),
            side=OrderSide(str(row["side"])),
            order_type=OrderType(str(row["order_type"])),
            quantity=int(row["quantity"]),
            submitted_at=cls._parse_datetime(str(row["submitted_at"])),
            limit_price=Decimal(str(row["limit_price"]))
            if row["limit_price"] is not None
            else None,
            status=OrderStatus(str(row["status"])),
            reason=str(row["reason"] or ""),
            eligible_at=(
                cls._parse_datetime(str(row["eligible_at"]))
                if row["eligible_at"] is not None
                else None
            ),
            filled_quantity=int(row["filled_quantity"]),
            remaining_quantity=int(row["remaining_quantity"]),
            updated_at=cls._parse_datetime(str(row["updated_at"])),
        )

    @classmethod
    def _row_to_fill(cls, row: sqlite3.Row) -> Fill:
        return Fill(
            fill_id=str(row["fill_id"]),
            order_id=str(row["order_id"]),
            symbol=str(row["symbol"]),
            side=OrderSide(str(row["side"])),
            quantity=int(row["quantity"]),
            price=Decimal(str(row["price"])),
            commission=Decimal(str(row["commission"])),
            tax=Decimal(str(row["tax"])),
            transfer_fee=Decimal(str(row["transfer_fee"])),
            slippage=Decimal(str(row["slippage"])),
            market_impact=Decimal(str(row["market_impact"])),
            filled_at=cls._parse_datetime(str(row["filled_at"])),
            reference_price=(
                Decimal(str(row["reference_price"]))
                if row["reference_price"] is not None
                else None
            ),
            degraded_model=bool(row["degraded_model"]),
        )

    @classmethod
    def _row_to_order_event(cls, row: sqlite3.Row) -> OrderEvent:
        return OrderEvent(
            event_id=str(row["event_id"]),
            order_id=str(row["order_id"]),
            status=OrderStatus(str(row["status"])),
            event_time=cls._parse_datetime(str(row["event_time"])),
            reason=str(row["reason"] or ""),
            filled_quantity=int(row["filled_quantity"]),
            remaining_quantity=int(row["remaining_quantity"]),
        )

    @classmethod
    def _row_to_snapshot(cls, row: sqlite3.Row) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            account_id=str(row["account_id"]),
            snapshot_time=cls._parse_datetime(str(row["snapshot_time"])),
            cash=Decimal(str(row["cash"])),
            market_value=Decimal(str(row["market_value"])),
            total_assets=Decimal(str(row["total_assets"])),
            net_value=Decimal(str(row["net_value"])),
            peak_total_assets=Decimal(str(row["peak_total_assets"])),
            current_drawdown=Decimal(str(row["current_drawdown"])),
            max_drawdown=Decimal(str(row["max_drawdown"])),
            cumulative_fees=Decimal(str(row["cumulative_fees"])),
        )

    @classmethod
    def _snapshot_rows(cls, account: SimulatedAccount) -> list[tuple[object, ...]]:
        rows: list[tuple[object, ...]] = []
        previous_total = account.initial_cash
        for snapshot in sorted(account.snapshots, key=lambda item: item.snapshot_time):
            rows.append(
                (
                    snapshot.account_id,
                    snapshot.trade_date.isoformat(),
                    cls._datetime_to_iso(snapshot.snapshot_time),
                    str(snapshot.cash),
                    str(snapshot.market_value),
                    str(snapshot.total_assets),
                    str(snapshot.net_value),
                    str(snapshot.peak_total_assets),
                    str(snapshot.current_drawdown),
                    str(snapshot.total_assets - previous_total),
                    str(snapshot.net_value - Decimal("1")),
                    str(snapshot.max_drawdown),
                    str(snapshot.cumulative_fees),
                )
            )
            previous_total = snapshot.total_assets
        return rows

    @staticmethod
    def _validate_unique_audit_ids(account: SimulatedAccount) -> None:
        for label, values in (
            ("order", [item.order_id for item in account.orders]),
            ("fill", [item.fill_id for item in account.fills]),
            ("order event", [item.event_id for item in account.order_events]),
        ):
            if len(values) != len(set(values)):
                raise AccountRepositoryError(
                    f"Duplicate {label} identifier in account ledger"
                )
