from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from app.config import APP_TIME_ZONE
from app.data.cache import TtlMemoryCache
from app.data.providers.base import (
    Bar,
    Instrument,
    MarketDataError,
    MarketDataProvider,
    OrderBook,
    OrderBookLevel,
    ProviderHealth,
    Quote,
    TradingDay,
)


class MockMarketDataProvider(MarketDataProvider):
    """可重复、无网络依赖的Mock行情源。"""

    name = "Mock行情"

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.quote_cache: TtlMemoryCache[list[Quote]] = TtlMemoryCache(ttl_seconds=3)
        self._now = datetime(2026, 7, 27, 10, 0, tzinfo=APP_TIME_ZONE)
        self._instruments = [
            Instrument(
                symbol="600519.SH",
                code="600519",
                exchange="SH",
                name="贵州茅台",
                board="主板",
                listed_date=date(2001, 8, 27),
                industry="食品饮料",
            ),
            Instrument(
                symbol="000001.SZ",
                code="000001",
                exchange="SZ",
                name="平安银行",
                board="主板",
                listed_date=date(1991, 4, 3),
                industry="银行",
            ),
            Instrument(
                symbol="300750.SZ",
                code="300750",
                exchange="SZ",
                name="宁德时代",
                board="创业板",
                listed_date=date(2018, 6, 11),
                industry="电力设备",
            ),
            Instrument(
                symbol="688001.SH",
                code="688001",
                exchange="SH",
                name="华兴源创",
                board="科创板",
                listed_date=date(2019, 7, 22),
                industry="机械设备",
            ),
            Instrument(
                symbol="000000.SZ",
                code="000000",
                exchange="SZ",
                name="示例ST股",
                board="主板",
                listed_date=date(2010, 1, 1),
                industry="示例",
                is_st=True,
            ),
        ]

    def get_stock_list(self) -> list[Instrument]:
        self._raise_if_failed()
        return list(self._instruments)

    def get_latest_quotes(self, symbols: list[str]) -> list[Quote]:
        self._raise_if_failed()
        cache_key = ",".join(sorted(symbols))
        cached = self.quote_cache.get(cache_key)
        if cached is not None:
            return cached

        quotes = [self._build_quote(symbol) for symbol in symbols if self._find_instrument(symbol)]
        self.quote_cache.set(cache_key, quotes)
        return quotes

    def get_order_book(self, symbol: str) -> OrderBook:
        self._raise_if_failed()
        if self._find_instrument(symbol) is None:
            raise MarketDataError(f"未知股票代码：{symbol}")

        quote = self._build_quote(symbol)
        bids = tuple(
            OrderBookLevel(price=quote.last_price - Decimal("0.01") * level, quantity=level * 1_000)
            for level in range(1, 6)
        )
        asks = tuple(
            OrderBookLevel(price=quote.last_price + Decimal("0.01") * level, quantity=level * 900)
            for level in range(1, 6)
        )
        return OrderBook(
            symbol=symbol,
            quote_time=quote.quote_time,
            bids=bids,
            asks=asks,
            source=self.name,
            inner_volume=12_000,
            outer_volume=15_000,
            commission_ratio=Decimal("0.1111"),
            commission_diff=3_000,
        )

    def get_intraday_bars(self, symbol: str, interval: str) -> list[Bar]:
        self._raise_if_failed()
        if interval not in {"1m", "5m", "15m"}:
            raise MarketDataError(f"Mock数据源不支持分时周期：{interval}")
        start = datetime.combine(self._now.date(), time(9, 30), tzinfo=APP_TIME_ZONE)
        return [
            self._build_bar(symbol, start + timedelta(minutes=index), index) for index in range(8)
        ]

    def get_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[Bar]:
        self._raise_if_failed()
        if start_date > end_date:
            raise MarketDataError("开始日期不能晚于结束日期")
        days: list[Bar] = []
        current = start_date
        index = 0
        while current <= end_date:
            if current.weekday() < 5:
                bar_time = datetime.combine(current, time(15, 0), tzinfo=APP_TIME_ZONE)
                days.append(self._build_bar(symbol, bar_time, index))
                index += 1
            current += timedelta(days=1)
        return days

    def get_trading_calendar(self, start_date: date, end_date: date) -> list[TradingDay]:
        self._raise_if_failed()
        if start_date > end_date:
            raise MarketDataError("开始日期不能晚于结束日期")
        days: list[TradingDay] = []
        current = start_date
        while current <= end_date:
            is_open = current.weekday() < 5
            days.append(
                TradingDay(
                    trade_date=current,
                    is_open=is_open,
                    market_phase="交易日" if is_open else "非交易日",
                )
            )
            current += timedelta(days=1)
        return days

    def get_financial_indicators(
        self,
        symbols: list[str],
        report_date: date,
    ) -> dict[str, dict[str, Any]]:
        self._raise_if_failed()
        return {
            symbol: {
                "pe": Decimal("18.5"),
                "pb": Decimal("2.1"),
                "roe": Decimal("0.13"),
                "report_date": report_date.isoformat(),
                "disclosure_date": None,
                "warning": "Mock数据不代表真实披露时点",
            }
            for symbol in symbols
        }

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            ok=not self.fail,
            message="Mock数据源可用" if not self.fail else "Mock数据源被设置为失败",
            checked_at=self._now,
            latency_ms=0,
        )

    def _raise_if_failed(self) -> None:
        if self.fail:
            raise MarketDataError("Mock数据源被设置为失败")

    def _find_instrument(self, symbol: str) -> Instrument | None:
        return next(
            (instrument for instrument in self._instruments if instrument.symbol == symbol), None
        )

    def _build_quote(self, symbol: str) -> Quote:
        instrument = self._find_instrument(symbol)
        if instrument is None:
            raise MarketDataError(f"未知股票代码：{symbol}")
        base_price = {
            "600519.SH": Decimal("1688.00"),
            "000001.SZ": Decimal("10.80"),
            "300750.SZ": Decimal("210.50"),
            "688001.SH": Decimal("31.25"),
            "000000.SZ": Decimal("2.35"),
        }[symbol]
        prev_close = (base_price * Decimal("0.99")).quantize(Decimal("0.01"))
        change = base_price - prev_close
        return Quote(
            symbol=symbol,
            name=instrument.name,
            quote_time=self._now,
            last_price=base_price,
            change_amount=change,
            pct_change=(change / prev_close).quantize(Decimal("0.0001")),
            open_price=prev_close + Decimal("0.20"),
            high_price=base_price + Decimal("2.30"),
            low_price=prev_close - Decimal("0.50"),
            prev_close=prev_close,
            volume=1_000_000,
            amount=base_price * Decimal("1000000"),
            turnover_rate=Decimal("0.0123"),
            source=self.name,
            delay_seconds=1,
        )

    def _build_bar(self, symbol: str, bar_time: datetime, index: int) -> Bar:
        quote = self._build_quote(symbol)
        open_price = quote.prev_close + Decimal(index) * Decimal("0.10")
        close_price = open_price + Decimal("0.05")
        return Bar(
            symbol=symbol,
            bar_time=bar_time,
            open_price=open_price,
            high_price=close_price + Decimal("0.20"),
            low_price=open_price - Decimal("0.15"),
            close_price=close_price,
            volume=10_000 + index * 100,
            amount=close_price * Decimal(10_000 + index * 100),
            source=self.name,
        )
