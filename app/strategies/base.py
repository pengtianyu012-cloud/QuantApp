from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from app.data.providers import Bar, OrderBook, Quote
from app.models import Fill, Order


class StrategyState(StrEnum):
    STOPPED = "已停止"
    RUNNING = "运行中"
    PAUSED = "已暂停"


class SignalDirection(StrEnum):
    BUY = "买入"
    SELL = "卖出"
    HOLD = "观察"


@dataclass(frozen=True)
class StrategySignal:
    signal_time: datetime
    market_time: datetime
    source: str
    symbol: str
    direction: SignalDirection
    strength: Decimal
    strategy_name: str
    reason: str
    suggested_position_pct: Decimal = Decimal("0")


@dataclass
class StrategyContext:
    logs: list[str] = field(default_factory=list)
    last_run_at: datetime | None = None


class Strategy:
    name = "Strategy"

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        self.parameters = parameters or {}
        self.state = StrategyState.STOPPED
        self.context = StrategyContext()

    def initialize(self) -> None:
        self.state = StrategyState.RUNNING

    def pause(self) -> None:
        self.state = StrategyState.PAUSED

    def stop(self) -> None:
        self.state = StrategyState.STOPPED

    def on_market_data(self, quote: Quote, order_book: OrderBook | None = None) -> None:
        self.context.last_run_at = quote.quote_time

    def generate_signals(self) -> list[StrategySignal]:
        return []

    def generate_from_bars(self, symbol: str, bars: list[Bar]) -> list[StrategySignal]:
        return []

    def on_order_update(self, order: Order) -> None:
        self.context.logs.append(f"订单更新：{order.order_id} {order.status.value}")

    def on_fill(self, fill: Fill) -> None:
        self.context.logs.append(f"成交：{fill.fill_id} {fill.quantity}")

    def reset(self) -> None:
        self.state = StrategyState.STOPPED
        self.context = StrategyContext()
