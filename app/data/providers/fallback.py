from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any, TypeVar

from app.data.providers.base import (
    Bar,
    Instrument,
    MarketDataError,
    MarketDataProvider,
    OrderBook,
    ProviderHealth,
    Quote,
    TradingDay,
)

T = TypeVar("T")


class FallbackMarketDataProvider(MarketDataProvider):
    """主备数据源包装器，主源失败时尝试备用源。"""

    name = "主备行情路由"

    def __init__(self, providers: list[MarketDataProvider]) -> None:
        if not providers:
            raise ValueError("至少需要一个行情数据源")
        self.providers = providers
        self.last_provider_name: str | None = None
        self.last_error: str | None = None

    def get_stock_list(self) -> list[Instrument]:
        return self._call(lambda provider: provider.get_stock_list())

    def get_latest_quotes(self, symbols: list[str]) -> list[Quote]:
        return self._call(lambda provider: provider.get_latest_quotes(symbols))

    def get_order_book(self, symbol: str) -> OrderBook:
        return self._call(lambda provider: provider.get_order_book(symbol))

    def get_intraday_bars(self, symbol: str, interval: str) -> list[Bar]:
        return self._call(lambda provider: provider.get_intraday_bars(symbol, interval))

    def get_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[Bar]:
        return self._call(lambda provider: provider.get_daily_bars(symbol, start_date, end_date))

    def get_trading_calendar(self, start_date: date, end_date: date) -> list[TradingDay]:
        return self._call(lambda provider: provider.get_trading_calendar(start_date, end_date))

    def get_financial_indicators(
        self,
        symbols: list[str],
        report_date: date,
    ) -> dict[str, dict[str, Any]]:
        return self._call(lambda provider: provider.get_financial_indicators(symbols, report_date))

    def health_check(self) -> ProviderHealth:
        checks = [provider.health_check() for provider in self.providers]
        ok = any(check.ok for check in checks)
        message = "; ".join(f"{check.provider}:{check.message}" for check in checks)
        return ProviderHealth(
            provider=self.name,
            ok=ok,
            message=message,
            checked_at=checks[0].checked_at,
            latency_ms=sum(check.latency_ms or 0 for check in checks),
        )

    def _call(self, operation: Callable[[MarketDataProvider], T]) -> T:
        errors: list[str] = []
        for provider in self.providers:
            try:
                result = operation(provider)
            except MarketDataError as exc:
                errors.append(f"{provider.name}: {exc}")
                continue
            self.last_provider_name = provider.name
            self.last_error = None
            return result
        self.last_provider_name = None
        self.last_error = " | ".join(errors)
        raise MarketDataError(f"所有行情数据源均失败：{self.last_error}")
