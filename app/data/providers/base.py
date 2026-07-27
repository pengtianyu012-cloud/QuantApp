from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any


class MarketDataError(RuntimeError):
    """行情数据源异常，调用方应降级而不是崩溃。"""


@dataclass(frozen=True)
class ProviderHealth:
    provider: str
    ok: bool
    message: str
    checked_at: datetime
    latency_ms: int | None = None


@dataclass(frozen=True)
class Instrument:
    symbol: str
    code: str
    exchange: str
    name: str
    board: str
    listed_date: date
    industry: str | None = None
    is_st: bool = False
    is_delisting: bool = False
    is_delisted: bool = False
    is_suspended: bool = False

    @property
    def eligible(self) -> bool:
        return not (self.is_st or self.is_delisting or self.is_delisted)


@dataclass(frozen=True)
class Quote:
    symbol: str
    name: str
    quote_time: datetime
    last_price: Decimal
    change_amount: Decimal
    pct_change: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    prev_close: Decimal
    volume: int
    amount: Decimal
    source: str
    delay_seconds: int
    turnover_rate: Decimal | None = None
    unsupported_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class OrderBookLevel:
    price: Decimal | None
    quantity: int | None


@dataclass(frozen=True)
class OrderBook:
    symbol: str
    quote_time: datetime
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    source: str
    inner_volume: int | None = None
    outer_volume: int | None = None
    commission_ratio: Decimal | None = None
    commission_diff: int | None = None
    unsupported_fields: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Bar:
    symbol: str
    bar_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int
    amount: Decimal
    source: str


@dataclass(frozen=True)
class TradingDay:
    trade_date: date
    is_open: bool
    market_phase: str


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def get_stock_list(self) -> list[Instrument]:
        raise NotImplementedError

    @abstractmethod
    def get_latest_quotes(self, symbols: list[str]) -> list[Quote]:
        raise NotImplementedError

    @abstractmethod
    def get_order_book(self, symbol: str) -> OrderBook:
        raise NotImplementedError

    @abstractmethod
    def get_intraday_bars(self, symbol: str, interval: str) -> list[Bar]:
        raise NotImplementedError

    @abstractmethod
    def get_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[Bar]:
        raise NotImplementedError

    @abstractmethod
    def get_trading_calendar(self, start_date: date, end_date: date) -> list[TradingDay]:
        raise NotImplementedError

    @abstractmethod
    def get_financial_indicators(
        self,
        symbols: list[str],
        report_date: date,
    ) -> dict[str, dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> ProviderHealth:
        raise NotImplementedError
