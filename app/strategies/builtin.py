from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from app.data.providers import Bar, OrderBook, Quote
from app.strategies.base import SignalDirection, Strategy, StrategySignal


class MovingAverageTrendStrategy(Strategy):
    name = "均线趋势"

    def generate_from_bars(self, symbol: str, bars: list[Bar]) -> list[StrategySignal]:
        short_window = int(self.parameters.get("short_window", 5))
        long_window = int(self.parameters.get("long_window", 20))
        if len(bars) < long_window:
            return []
        short_avg = average_close(bars[-short_window:])
        long_avg = average_close(bars[-long_window:])
        latest = bars[-1]
        if short_avg > long_avg:
            strength = min((short_avg / long_avg - Decimal("1")) * Decimal("10"), Decimal("1"))
            return [
                StrategySignal(
                    signal_time=latest.bar_time,
                    market_time=latest.bar_time,
                    source=latest.source,
                    symbol=symbol,
                    direction=SignalDirection.BUY,
                    strength=strength.quantize(Decimal("0.0001")),
                    strategy_name=self.name,
                    reason=f"短均线{short_avg:.2f}高于长均线{long_avg:.2f}",
                    suggested_position_pct=Decimal("0.20"),
                )
            ]
        return []


class MomentumSelectionStrategy(Strategy):
    name = "动量选股"

    def generate_from_bars(self, symbol: str, bars: list[Bar]) -> list[StrategySignal]:
        lookback = int(self.parameters.get("lookback", 20))
        if len(bars) <= lookback:
            return []
        start = bars[-lookback - 1]
        latest = bars[-1]
        momentum = latest.close_price / start.close_price - Decimal("1")
        threshold = Decimal(str(self.parameters.get("threshold", "0.03")))
        if momentum >= threshold:
            strength = min(momentum * Decimal("5"), Decimal("1"))
            return [
                StrategySignal(
                    signal_time=latest.bar_time,
                    market_time=latest.bar_time,
                    source=latest.source,
                    symbol=symbol,
                    direction=SignalDirection.BUY,
                    strength=strength.quantize(Decimal("0.0001")),
                    strategy_name=self.name,
                    reason=f"{lookback}日动量{momentum:.2%}超过阈值{threshold:.2%}",
                    suggested_position_pct=Decimal("0.18"),
                )
            ]
        return []


class LowValuationFactorStrategy(Strategy):
    name = "低估值因子"

    def generate_from_financials(
        self,
        symbol: str,
        indicators: dict[str, Any],
        signal_time: datetime,
        source: str,
    ) -> list[StrategySignal]:
        pe = indicators.get("pe")
        pb = indicators.get("pb")
        roe = indicators.get("roe")
        warning = indicators.get("warning")
        if pe is None or pb is None or roe is None or pe <= 0 or pb <= 0:
            return []
        if pe < Decimal("25") and pb < Decimal("3") and roe > Decimal("0.08"):
            reason = f"PE={pe}, PB={pb}, ROE={roe}"
            if warning:
                reason += f"；{warning}"
            return [
                StrategySignal(
                    signal_time=signal_time,
                    market_time=signal_time,
                    source=source,
                    symbol=symbol,
                    direction=SignalDirection.BUY,
                    strength=Decimal("0.6500"),
                    strategy_name=self.name,
                    reason=reason,
                    suggested_position_pct=Decimal("0.15"),
                )
            ]
        return []


class OrderBookVolumePriceDemoStrategy(Strategy):
    name = "盘口与量价演示"

    def __init__(self, parameters: dict[str, Any] | None = None) -> None:
        super().__init__(parameters)
        self.samples: list[tuple[Quote, OrderBook]] = []

    def on_market_data(self, quote: Quote, order_book: OrderBook | None = None) -> None:
        super().on_market_data(quote, order_book)
        if order_book is not None:
            self.samples.append((quote, order_book))
            max_samples = int(self.parameters.get("max_samples", 20))
            self.samples = self.samples[-max_samples:]

    def generate_signals(self) -> list[StrategySignal]:
        min_samples = int(self.parameters.get("min_samples", 2))
        if len(self.samples) < min_samples:
            return []
        previous_quote, _ = self.samples[-2]
        latest_quote, latest_book = self.samples[-1]
        if latest_book.commission_diff is None or latest_book.commission_diff <= 0:
            return []
        if latest_quote.last_price <= previous_quote.last_price:
            return []
        return [
            StrategySignal(
                signal_time=latest_quote.quote_time,
                market_time=latest_quote.quote_time,
                source=latest_quote.source,
                symbol=latest_quote.symbol,
                direction=SignalDirection.BUY,
                strength=Decimal("0.5000"),
                strategy_name=self.name,
                reason="盘口委差为正且价格上行；仅用于验证实时引擎",
                suggested_position_pct=Decimal("0.05"),
            )
        ]


def average_close(bars: list[Bar]) -> Decimal:
    return sum((bar.close_price for bar in bars), Decimal("0")) / Decimal(len(bars))


def create_builtin_strategies() -> dict[str, Strategy]:
    return {
        MovingAverageTrendStrategy.name: MovingAverageTrendStrategy(),
        MomentumSelectionStrategy.name: MomentumSelectionStrategy(),
        LowValuationFactorStrategy.name: LowValuationFactorStrategy(),
        OrderBookVolumePriceDemoStrategy.name: OrderBookVolumePriceDemoStrategy(),
    }
