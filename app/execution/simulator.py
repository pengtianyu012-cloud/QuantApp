from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from decimal import ROUND_FLOOR, Decimal

from app.config import APP_TIME_ZONE, TradingCostSettings, TradingRules
from app.data.providers.base import Instrument, Quote
from app.execution.calendar import TradingCalendar
from app.execution.costs import execution_price_with_adjustments
from app.execution.trading_rules import (
    calculate_price_limits,
    get_market_phase,
    is_at_limit_down,
    is_at_limit_up,
)
from app.models import Order, OrderSide, OrderStatus, OrderType


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
    reference_price: Decimal | None = None


class SimulatedMatcher:
    def __init__(
        self,
        trading_calendar: TradingCalendar,
        config: ExecutionConfig | None = None,
    ) -> None:
        self.trading_calendar = trading_calendar
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
        if order.status.is_terminal:
            return ExecutionResult(order.status, 0, None, "终态订单不可再次撮合")

        now = self._localize(current_time)
        timing_result = self._check_order_timing(order, now)
        if timing_result is not None:
            return timing_result
        if not self.trading_calendar.is_trading_day(now.date()):
            return self._defer("当前不是交易日，订单顺延")
        if get_market_phase(now, True) != "连续竞价":
            return self._defer("当前不在连续竞价时段，订单顺延")
        if order.order_type is OrderType.CANCEL:
            return ExecutionResult(OrderStatus.REJECTED, 0, None, "撤单请求不能参与撮合")
        if order.order_type is OrderType.LIMIT and order.limit_price is None:
            return ExecutionResult(OrderStatus.REJECTED, 0, None, "限价单缺少限价")
        if instrument.is_st:
            return ExecutionResult(OrderStatus.REJECTED, 0, None, "ST股票已从可交易股票池排除")
        if instrument.is_delisted or instrument.is_delisting:
            return ExecutionResult(OrderStatus.REJECTED, 0, None, "退市或退市整理股票禁止撮合")
        if instrument.is_suspended:
            return self._defer("股票停牌，订单顺延到下一交易日")

        quote_time = self._localize(quote.quote_time)
        quote_age_seconds = (now - quote_time).total_seconds()
        if quote_age_seconds < 0:
            return self._defer("行情时间晚于当前时间，暂停撮合")
        if quote_age_seconds > self.config.max_quote_age_seconds:
            return self._defer("行情数据过期，暂停撮合")

        effective_listing_days = (
            listing_days
            if listing_days is not None
            else (now.date() - instrument.listed_date).days
        )
        limit = calculate_price_limits(
            prev_close=quote.prev_close,
            board=instrument.board,
            is_st=instrument.is_st,
            listing_days=effective_listing_days,
        )
        if limit.uncertain:
            return ExecutionResult(OrderStatus.REJECTED, 0, None, limit.reason)

        reference_price = (
            quote.open_price if order.order_type is OrderType.NEXT_OPEN else quote.last_price
        )
        if order.side is OrderSide.BUY and is_at_limit_up(reference_price, limit.limit_up):
            return self._defer("开盘涨停无法买入，订单顺延")
        if order.side is OrderSide.SELL and is_at_limit_down(reference_price, limit.limit_down):
            return self._defer("开盘跌停无法卖出，订单顺延")
        if order.limit_price is not None:
            if order.side is OrderSide.BUY and reference_price > order.limit_price:
                return self._defer("市场价格高于买入限价，订单等待")
            if order.side is OrderSide.SELL and reference_price < order.limit_price:
                return self._defer("市场价格低于卖出限价，订单等待")

        fill_quantity = self._participation_quantity(order, interval_volume)
        if fill_quantity <= 0:
            return self._defer("可参与成交量不足，订单顺延")
        fill_price = execution_price_with_adjustments(order.side, reference_price)
        if order.limit_price is not None:
            if order.side is OrderSide.BUY and fill_price > order.limit_price:
                return self._defer("含滑点成交价高于买入限价，订单等待")
            if order.side is OrderSide.SELL and fill_price < order.limit_price:
                return self._defer("含滑点成交价低于卖出限价，订单等待")
        remaining_quantity = order.remaining_quantity or 0
        status = (
            OrderStatus.FILLED
            if fill_quantity == remaining_quantity
            else OrderStatus.PARTIALLY_FILLED
        )
        reason = "按盘口模拟成交" if has_order_book else "无盘口数据，使用最新价加滑点降级撮合"
        return ExecutionResult(
            status,
            fill_quantity,
            fill_price,
            reason,
            degraded_model=not has_order_book,
            reference_price=reference_price,
        )

    def _check_order_timing(
        self, order: Order, current_time: datetime
    ) -> ExecutionResult | None:
        if order.order_type is not OrderType.NEXT_OPEN:
            return None
        submitted_at = self._localize(order.submitted_at)
        if order.eligible_at is None:
            eligible_date = self.trading_calendar.next_trading_day(submitted_at.date())
            eligible_at = datetime.combine(eligible_date, time(9, 30), tzinfo=APP_TIME_ZONE)
        else:
            eligible_at = self._localize(order.eligible_at)
        if current_time.date() <= submitted_at.date() or current_time < eligible_at:
            return ExecutionResult(
                OrderStatus.PENDING_NEXT_OPEN,
                0,
                None,
                "NEXT_OPEN订单等待下一交易日开盘",
            )
        return None

    def _participation_quantity(self, order: Order, interval_volume: int | None) -> int:
        remaining_quantity = order.remaining_quantity or 0
        if interval_volume is None:
            return remaining_quantity
        allowed = int(
            (Decimal(interval_volume) * self.config.max_volume_participation).to_integral_value(
                ROUND_FLOOR
            )
        )
        if allowed <= 0:
            return 0
        if order.side is OrderSide.BUY and remaining_quantity >= TradingRules().buy_lot_size:
            allowed = allowed - allowed % TradingRules().buy_lot_size
        return min(remaining_quantity, allowed)

    @staticmethod
    def _localize(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=APP_TIME_ZONE)
        return value.astimezone(APP_TIME_ZONE)

    @staticmethod
    def _defer(reason: str) -> ExecutionResult:
        return ExecutionResult(OrderStatus.DEFERRED, 0, None, reason)
