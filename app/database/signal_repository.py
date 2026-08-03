from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from app.config import APP_TIME_ZONE
from app.database.connection import connect_database, initialize_database
from app.strategies import SignalDirection, StrategySignal


class SignalRepositoryError(RuntimeError):
    """信号账本无法可靠保存或恢复。"""


class SignalDispatchStatus(StrEnum):
    NOT_SCHEDULED = "not_scheduled"
    PENDING = "pending"
    ORDER_CREATED = "order_created"
    SKIPPED = "skipped"
    REJECTED = "rejected"


@dataclass(frozen=True)
class PersistedSignal:
    signal_id: str
    account_id: str
    strategy_name: str
    symbol: str
    signal_time: datetime
    market_time: datetime
    source: str
    direction: SignalDirection
    strength: Decimal
    reason: str
    suggested_position_pct: Decimal
    scheduled_for: date
    dispatch_status: SignalDispatchStatus
    order_id: str | None
    dispatch_message: str
    processed_at: datetime | None
    created_at: datetime

    def to_strategy_signal(self) -> StrategySignal:
        return StrategySignal(
            signal_time=self.signal_time,
            market_time=self.market_time,
            source=self.source,
            symbol=self.symbol,
            direction=self.direction,
            strength=self.strength,
            strategy_name=self.strategy_name,
            reason=self.reason,
            suggested_position_pct=self.suggested_position_pct,
        )


@dataclass(frozen=True)
class PersistSignalsResult:
    records: tuple[PersistedSignal, ...]
    inserted_count: int


class SignalRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        try:
            self.db_path = initialize_database(db_path)
        except (sqlite3.Error, RuntimeError) as exc:
            raise SignalRepositoryError(f"信号数据库初始化失败：{exc}") from exc

    def persist_for_next_open(
        self,
        signals: list[StrategySignal],
        account_id: str,
        scheduled_for: date,
        created_at: datetime,
    ) -> PersistSignalsResult:
        if not signals:
            return PersistSignalsResult((), 0)
        signal_ids = [
            build_signal_id(account_id, signal)
            for signal in signals
        ]
        try:
            with connect_database(self.db_path) as connection:
                before = connection.total_changes
                connection.executemany(
                    """
                    INSERT INTO signals (
                        signal_id, strategy_id, symbol, signal_time, market_time,
                        source, direction, strength, reason, suggested_position_pct,
                        account_id, scheduled_for, dispatch_status, order_id,
                        dispatch_message, processed_at, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '', NULL, ?)
                    ON CONFLICT(signal_id) DO NOTHING
                    """,
                    [
                        (
                            signal_id,
                            signal.strategy_name,
                            signal.symbol,
                            datetime_to_iso(signal.signal_time),
                            datetime_to_iso(signal.market_time),
                            signal.source,
                            signal.direction.value,
                            str(signal.strength),
                            signal.reason,
                            str(signal.suggested_position_pct),
                            account_id,
                            scheduled_for.isoformat(),
                            SignalDispatchStatus.PENDING.value,
                            datetime_to_iso(created_at),
                        )
                        for signal_id, signal in zip(signal_ids, signals, strict=True)
                    ],
                )
                inserted_count = connection.total_changes - before
                records = tuple(self._load_by_ids(connection, signal_ids))
            return PersistSignalsResult(records, inserted_count)
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise SignalRepositoryError(f"信号持久化失败：{exc}") from exc

    def list_pending(self, account_id: str) -> list[PersistedSignal]:
        try:
            with connect_database(self.db_path) as connection:
                rows = connection.execute(
                    "SELECT * FROM signals "
                    "WHERE account_id = ? AND dispatch_status = ? "
                    "ORDER BY signal_time, signal_id",
                    (account_id, SignalDispatchStatus.PENDING.value),
                ).fetchall()
            return [self._row_to_signal(row) for row in rows]
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise SignalRepositoryError(f"待编排信号读取失败：{exc}") from exc

    def list_for_account(self, account_id: str) -> list[PersistedSignal]:
        try:
            with connect_database(self.db_path) as connection:
                rows = connection.execute(
                    "SELECT * FROM signals WHERE account_id = ? "
                    "ORDER BY signal_time, signal_id",
                    (account_id,),
                ).fetchall()
            return [self._row_to_signal(row) for row in rows]
        except (sqlite3.Error, ValueError, TypeError) as exc:
            raise SignalRepositoryError(f"信号账本读取失败：{exc}") from exc

    def mark_dispatch(
        self,
        signal_id: str,
        status: SignalDispatchStatus,
        processed_at: datetime,
        message: str,
        order_id: str | None = None,
    ) -> None:
        if status in {
            SignalDispatchStatus.NOT_SCHEDULED,
            SignalDispatchStatus.PENDING,
        }:
            raise ValueError(f"不能将已处理信号标记为 {status.value}")
        try:
            with connect_database(self.db_path) as connection:
                cursor = connection.execute(
                    """
                    UPDATE signals
                    SET dispatch_status = ?, order_id = ?,
                        dispatch_message = ?, processed_at = ?
                    WHERE signal_id = ?
                    """,
                    (
                        status.value,
                        order_id,
                        message,
                        datetime_to_iso(processed_at),
                        signal_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise SignalRepositoryError(f"未知信号：{signal_id}")
        except sqlite3.Error as exc:
            raise SignalRepositoryError(f"信号状态保存失败：{exc}") from exc

    def _load_by_ids(
        self,
        connection: sqlite3.Connection,
        signal_ids: list[str],
    ) -> list[PersistedSignal]:
        placeholders = ",".join("?" for _ in signal_ids)
        rows = connection.execute(
            f"SELECT * FROM signals WHERE signal_id IN ({placeholders}) "
            "ORDER BY signal_time, signal_id",
            signal_ids,
        ).fetchall()
        return [self._row_to_signal(row) for row in rows]

    @staticmethod
    def _row_to_signal(row: sqlite3.Row) -> PersistedSignal:
        scheduled_for = row["scheduled_for"]
        account_id = row["account_id"]
        if scheduled_for is None or account_id is None:
            raise ValueError("旧信号没有 NEXT_OPEN 编排信息")
        return PersistedSignal(
            signal_id=str(row["signal_id"]),
            account_id=str(account_id),
            strategy_name=str(row["strategy_id"]),
            symbol=str(row["symbol"]),
            signal_time=parse_datetime(str(row["signal_time"])),
            market_time=parse_datetime(str(row["market_time"])),
            source=str(row["source"]),
            direction=SignalDirection(str(row["direction"])),
            strength=Decimal(str(row["strength"])),
            reason=str(row["reason"]),
            suggested_position_pct=Decimal(str(row["suggested_position_pct"])),
            scheduled_for=date.fromisoformat(str(scheduled_for)),
            dispatch_status=SignalDispatchStatus(str(row["dispatch_status"])),
            order_id=str(row["order_id"]) if row["order_id"] is not None else None,
            dispatch_message=str(row["dispatch_message"] or ""),
            processed_at=(
                parse_datetime(str(row["processed_at"]))
                if row["processed_at"] is not None
                else None
            ),
            created_at=parse_datetime(str(row["created_at"])),
        )


def build_signal_id(account_id: str, signal: StrategySignal) -> str:
    identity = "\x1f".join(
        (
            account_id,
            signal.strategy_name,
            signal.symbol,
            signal.direction.value,
            datetime_to_iso(signal.signal_time),
            datetime_to_iso(signal.market_time),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return f"S-{digest}"


def datetime_to_iso(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=APP_TIME_ZONE)
    return value.astimezone(APP_TIME_ZONE).isoformat()


def parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return parsed.replace(tzinfo=APP_TIME_ZONE)
    return parsed.astimezone(APP_TIME_ZONE)
