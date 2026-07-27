from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.data.providers import MarketDataProvider
from app.strategies import (
    LowValuationFactorStrategy,
    OrderBookVolumePriceDemoStrategy,
    Strategy,
    StrategySignal,
    StrategyState,
    create_builtin_strategies,
)


class StrategyServiceError(RuntimeError):
    """策略服务异常。"""


@dataclass(frozen=True)
class StrategyStatus:
    name: str
    state: StrategyState
    last_run: str
    signal_count: int


class StrategyService:
    def __init__(self, market_data: MarketDataProvider) -> None:
        self.market_data = market_data
        self.strategies = create_builtin_strategies()
        self.latest_signals: list[StrategySignal] = []

    def start(self, name: str) -> None:
        strategy = self._strategy(name)
        if strategy.state is StrategyState.RUNNING:
            raise StrategyServiceError(f"策略已在运行：{name}")
        strategy.initialize()

    def pause(self, name: str) -> None:
        self._strategy(name).pause()

    def stop(self, name: str) -> None:
        self._strategy(name).stop()

    def statuses(self) -> list[StrategyStatus]:
        return [
            StrategyStatus(
                name=strategy.name,
                state=strategy.state,
                last_run=strategy.context.last_run_at.isoformat()
                if strategy.context.last_run_at
                else "-",
                signal_count=len(
                    [
                        signal
                        for signal in self.latest_signals
                        if signal.strategy_name == strategy.name
                    ]
                ),
            )
            for strategy in self.strategies.values()
        ]

    def run_daily_signals(self, symbols: list[str] | None = None) -> list[StrategySignal]:
        selected_symbols = symbols or [
            instrument.symbol
            for instrument in self.market_data.get_stock_list()
            if instrument.eligible
        ]
        signals: list[StrategySignal] = []
        end_date = date(2026, 7, 27)
        start_date = end_date - timedelta(days=90)
        for symbol in selected_symbols:
            bars = self.market_data.get_daily_bars(symbol, start_date, end_date)
            for name in ("均线趋势", "动量选股"):
                strategy = self._strategy(name)
                strategy.initialize()
                signals.extend(strategy.generate_from_bars(symbol, bars))
            low_value = self._strategy("低估值因子")
            low_value.initialize()
            if isinstance(low_value, LowValuationFactorStrategy):
                indicators = self.market_data.get_financial_indicators([symbol], end_date)[symbol]
                signals.extend(
                    low_value.generate_from_financials(
                        symbol, indicators, bars[-1].bar_time, self.market_data.name
                    )
                )
        self.latest_signals = signals
        return signals

    def run_realtime_demo_signal(self, symbol: str) -> list[StrategySignal]:
        strategy = self._strategy("盘口与量价演示")
        strategy.initialize()
        if not isinstance(strategy, OrderBookVolumePriceDemoStrategy):
            return []
        quote = self.market_data.get_latest_quotes([symbol])[0]
        order_book = self.market_data.get_order_book(symbol)
        strategy.on_market_data(quote, order_book)
        moved_quote = self.market_data.get_latest_quotes([symbol])[0]
        moved_quote = type(moved_quote)(
            **{
                **moved_quote.__dict__,
                "last_price": moved_quote.last_price + moved_quote.last_price * 0 + 1,
            }
        )
        strategy.on_market_data(moved_quote, order_book)
        signals = strategy.generate_signals()
        self.latest_signals.extend(signals)
        return signals

    def _strategy(self, name: str) -> Strategy:
        try:
            return self.strategies[name]
        except KeyError as exc:
            raise StrategyServiceError(f"未知策略：{name}") from exc
