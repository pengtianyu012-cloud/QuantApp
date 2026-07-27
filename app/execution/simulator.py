from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal

from app.config import TradingCostSettings, TradingRules
from app.data.providers.base import Instrument, Quote
from app.execution.costs import execution_price_with_slippage
from app.execution.trading_rules import calculate_price_limits, is_at_limit_down, is_at_limit_up
from app.models import Order, OrderSide, OrderStatus


@dataclass(frozen=True)
class ExecutionConfig:
    max_quote_age_seconds: int = 30
    max_volume_participation: Decimal = TradingCostSettings().max_volume_participation


@dataclass(frozen=True)
class ExecutionResult:
    status: OrderStatus
    fill_quantity: int
    fill_price: Decimal | None
    reason: str
    degraded_model: bool = False


class SimulatedMatcher:
    def __init__(self, config: ExecutionConfig | None = None) -> None:
        self.config = config or ExecutionConfig()

    def evaluate(
        self,
        order: Order,
        quote: Quote,
        instrument: Instrument,
        current_time: datetime,
        interval_volume: int | None = None,
        listing_days: int | None = None,
        has_order_book: bool = True,
    ) -> ExecutionResult:
        if instrument.is_suspended:
            return self._defer("股票停牌，订单顺延到下一交易日")
        if quote.delay_seconds > self.config.max_quote_age_seconds:
            return self._defer("行情数据过期，暂停撮合")

        limit = calculate_price_limits(
            prev_close=quote.prev_close,
            board=instrument.board,
            is_st=instrument.is_st,
            listing_days=listing_days,
        )
        if limit.uncertain:
            return ExecutionResult(OrderStatus.REJECTED, 0, None, limit.reason)
        if order.side is OrderSide.BUY and is_at_limit_up(quote.last_price, limit.limit_up):
            return self._defer("开盘涨停无法买入，订单顺延")
        if order.side is OrderSide.SELL and is_at_limit_down(quote.last_price, limit.limit_down):
            return self._defer("开盘跌停无法卖出，订单顺延")

        fill_quantity = self._participation_quantity(order.quantity, interval_volume)
        if fill_quantity <= 0:
            return self._defer("可参与成交量不足，订单顺延")
        fill_price = execution_price_with_slippage(order.side, quote.last_price)
        status = (
            OrderStatus.FILLED if fill_quantity == order.quantity else OrderStatus.PARTIALLY_FILLED
        )
        reason = "按盘口模拟成交" if has_order_book else "无盘口数据，使用最新价加滑点降级撮合"
        return ExecutionResult(
            status, fill_quantity, fill_price, reason, degraded_model=not has_order_book
        )

    def _participation_quantity(self, order_quantity: int, interval_volume: int | None) -> int:
        if interval_volume is None:
            return order_quantity
        allowed = int(
            (Decimal(interval_volume) * self.config.max_volume_participation).to_integral_value(
                ROUND_FLOOR
            )
        )
        if allowed <= 0:
            return 0
        if order_quantity >= TradingRules().buy_lot_size:
            allowed = allowed - allowed % TradingRules().buy_lot_size
        return min(order_quantity, allowed)

    @staticmethod
    def _defer(reason: str) -> ExecutionResult:
        return ExecutionResult(OrderStatus.DEFERRED, 0, None, reason)
