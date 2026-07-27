from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from app.config import APP_TIME_ZONE
from app.database.connection import connect_database, initialize_database
from app.models import Fill, Order, OrderSide, OrderStatus, OrderType, Position
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
            return SimulatedAccount(
                account_id=str(account_row["account_id"]),
                name=str(account_row["name"]),
                initial_cash=Decimal(str(account_row["initial_cash"])),
                cash=Decimal(str(account_row["cash"])),
                positions=positions,
                orders=orders,
                fills=fills,
            )
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise AccountRepositoryError(f"账户恢复失败：{exc}") from exc

    def save(self, account: SimulatedAccount) -> None:
        now = datetime.now(UTC).isoformat()
        try:
            with connect_database(self.db_path) as connection:
                connection.execute(
                    """
                    INSERT INTO accounts (
                        account_id, name, initial_cash, cash, total_assets,
                        max_drawdown, risk_status, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, '0', '允许交易', ?, ?)
                    ON CONFLICT(account_id) DO UPDATE SET
                        name = excluded.name,
                        initial_cash = excluded.initial_cash,
                        cash = excluded.cash,
                        total_assets = excluded.total_assets,
                        updated_at = excluded.updated_at
                    """,
                    (
                        account.account_id,
                        account.name,
                        str(account.initial_cash),
                        str(account.cash),
                        str(account.total_assets()),
                        now,
                        now,
                    ),
                )

                connection.execute(
                    "DELETE FROM positions WHERE account_id = ?", (account.account_id,)
                )
                connection.execute(
                    "DELETE FROM fills WHERE order_id IN "
                    "(SELECT order_id FROM orders WHERE account_id = ?)",
                    (account.account_id,),
                )
                connection.execute("DELETE FROM orders WHERE account_id = ?", (account.account_id,))

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
                        limit_price, status, reason, submitted_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            self._datetime_to_iso(order.submitted_at),
                            now,
                        )
                        for order in account.orders
                    ],
                )
                connection.executemany(
                    """
                    INSERT INTO fills (
                        fill_id, order_id, symbol, side, quantity, price,
                        commission, tax, transfer_fee, slippage,
                        degraded_model, filled_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                            int(fill.degraded_model),
                            self._datetime_to_iso(fill.filled_at),
                        )
                        for fill in account.fills
                    ],
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
            filled_at=cls._parse_datetime(str(row["filled_at"])),
            degraded_model=bool(row["degraded_model"]),
        )
