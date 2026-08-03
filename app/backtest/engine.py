from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.data.providers import Bar, MarketDataProvider
from app.execution.costs import calculate_trade_cost
from app.models import OrderSide
from app.strategies import Strategy, StrategySignal


@dataclass(frozen=True)
class BacktestTrade:
    symbol: str
    signal_time: datetime
    fill_time: datetime
    side: OrderSide
    quantity: int
    signal_price: Decimal
    fill_price: Decimal
    reason: str


@dataclass(frozen=True)
class BacktestResult:
    strategy_name: str
    symbol: str
    start_date: date
    end_date: date
    initial_cash: Decimal
    final_cash: Decimal
    position_quantity: int
    trades: tuple[BacktestTrade, ...]

    @property
    def total_return(self) -> Decimal:
        return (self.final_cash - self.initial_cash) / self.initial_cash


class DailyBacktestEngine:
    """日线回测骨架：T日收盘后信号，T+1开盘成交。"""

    def __init__(self, market_data: MarketDataProvider) -> None:
        self.market_data = market_data

    def run(
        self,
        strategy: Strategy,
        symbol: str,
        start_date: date,
        end_date: date,
        initial_cash: Decimal = Decimal("100000"),
        quantity: int = 100,
    ) -> BacktestResult:
        bars = self.market_data.get_daily_bars(symbol, start_date, end_date)
        cash = initial_cash
        position_quantity = 0
        trades: list[BacktestTrade] = []
        if len(bars) < 2:
            return BacktestResult(
                strategy.name,
                symbol,
                start_date,
                end_date,
                initial_cash,
                cash,
                position_quantity,
                tuple(),
            )

        for index in range(1, len(bars) - 1):
            visible_bars = bars[: index + 1]
            signals = strategy.generate_from_bars(symbol, visible_bars)
            if not signals:
                continue
            signal = signals[0]
            next_bar = bars[index + 1]
            cost = calculate_trade_cost(OrderSide.BUY, next_bar.open_price, quantity)
            cash_required = cost.notional + cost.total
            if cash_required > cash:
                continue
            cash -= cash_required
            position_quantity += quantity
            trades.append(
                self._trade_from_signal(symbol, signal, visible_bars[-1], next_bar, quantity)
            )
            break
        final_cash = cash + Decimal(position_quantity) * bars[-1].close_price
        return BacktestResult(
            strategy.name,
            symbol,
            start_date,
            end_date,
            initial_cash,
            final_cash,
            position_quantity,
            tuple(trades),
        )

    @staticmethod
    def _trade_from_signal(
        symbol: str,
        signal: StrategySignal,
        signal_bar: Bar,
        fill_bar: Bar,
        quantity: int,
    ) -> BacktestTrade:
        return BacktestTrade(
            symbol=symbol,
            signal_time=signal.signal_time,
            fill_time=fill_bar.bar_time,
            side=OrderSide.BUY,
            quantity=quantity,
            signal_price=signal_bar.close_price,
            fill_price=fill_bar.open_price,
            reason=signal.reason,
        )
