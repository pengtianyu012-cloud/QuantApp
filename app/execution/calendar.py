from __future__ import annotations

from datetime import date, timedelta
from typing import Protocol

from app.data.providers.base import MarketDataProvider


class TradingCalendar(Protocol):
    def is_trading_day(self, trade_date: date) -> bool: ...

    def next_trading_day(self, after: date) -> date: ...


class ProviderTradingCalendar:
    """以当前行情源的交易日历为唯一事实来源。"""

    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def is_trading_day(self, trade_date: date) -> bool:
        rows = self.provider.get_trading_calendar(trade_date, trade_date)
        return any(row.trade_date == trade_date and row.is_open for row in rows)

    def next_trading_day(self, after: date) -> date:
        start = after + timedelta(days=1)
        end = start + timedelta(days=370)
        for row in self.provider.get_trading_calendar(start, end):
            if row.trade_date > after and row.is_open:
                return row.trade_date
        raise RuntimeError(f"行情源未返回 {after.isoformat()} 之后的交易日")
