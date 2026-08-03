from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, time
from decimal import ROUND_FLOOR, Decimal

from app.config import APP_TIME_ZONE, RuntimeMode, TradingRules
from app.data.providers import Instrument, MarketDataError, MarketDataProvider, Quote
from app.database import (
    AccountRepository,
    AccountRepositoryError,
    PersistedSignal,
    SignalDispatchStatus,
    SignalRepository,
    SignalRepositoryError,
    build_signal_id,
)
from app.execution import TradingCalendar
from app.models import OrderSide, OrderType
from app.portfolio import AccountError, SimulatedAccount
from app.risk import RiskManager
from app.strategies import SignalDirection, StrategySignal


class CloseSignalOrchestrationError(RuntimeError):
    """收盘信号无法可靠落账或编排。"""


@dataclass(frozen=True)
class SignalDispatchOutcome:
    signal_id: str
    symbol: str
    status: SignalDispatchStatus
    order_id: str | None
    message: str


@dataclass(frozen=True)
class CloseSignalCycleResult:
    run_at: datetime
    scheduled_for: datetime
    received_count: int
    inserted_count: int
    recovered_pending_count: int
    orders_created_count: int
    account_saved: bool
    outcomes: tuple[SignalDispatchOutcome, ...]


@dataclass(frozen=True)
class _DispatchPlan:
    signal: PersistedSignal
    status: SignalDispatchStatus
    message: str
    order_id: str | None = None
    created_order: bool = False


class CloseSignalOrchestrator:
    CLOSE_TIME = time(15, 0)

    def __init__(
        self,
        *,
        mode: RuntimeMode,
        market_data: MarketDataProvider,
        account_repository: AccountRepository,
        signal_repository: SignalRepository,
        trading_calendar: TradingCalendar,
        risk_manager: RiskManager,
    ) -> None:
        self.mode = mode
        self.market_data = market_data
        self.account_repository = account_repository
        self.signal_repository = signal_repository
        self.trading_calendar = trading_calendar
        self.risk_manager = risk_manager

    def run(
        self,
        signals: list[StrategySignal],
        account: SimulatedAccount,
        current_time: datetime,
    ) -> CloseSignalCycleResult:
        now = _localize(current_time)
        self.validate_close_session(now)
        next_trade_date = self.trading_calendar.next_trading_day(now.date())
        scheduled_open = datetime.combine(
            next_trade_date,
            time(9, 30),
            tzinfo=APP_TIME_ZONE,
        )

        try:
            persisted = self.signal_repository.persist_for_next_open(
                signals,
                account.account_id,
                next_trade_date,
                now,
            )
            pending = self.signal_repository.list_pending(account.account_id)
        except SignalRepositoryError as exc:
            raise CloseSignalOrchestrationError(str(exc)) from exc

        requested_ids = {build_signal_id(account.account_id, item) for item in signals}
        recovered_count = sum(item.signal_id not in requested_ids for item in pending)
        outcomes_by_id = {
            item.signal_id: SignalDispatchOutcome(
                signal_id=item.signal_id,
                symbol=item.symbol,
                status=item.dispatch_status,
                order_id=item.order_id,
                message=item.dispatch_message,
            )
            for item in persisted.records
            if item.dispatch_status is not SignalDispatchStatus.PENDING
        }

        working_account = deepcopy(account)
        plans: list[_DispatchPlan] = []
        actionable = self.mode in {RuntimeMode.MOCK, RuntimeMode.PAPER}
        quote_map: dict[str, Quote] = {}
        instrument_map: dict[str, Instrument] = {}
        if actionable:
            quote_map, instrument_map = self._load_market_context(
                pending,
                working_account,
                now,
            )
            latest_prices = {symbol: quote.last_price for symbol, quote in quote_map.items()}
            working_account.record_snapshot(now, latest_prices)

        for signal in pending:
            plan = self._plan_signal(
                signal,
                working_account,
                now,
                quote_map,
                instrument_map,
            )
            plans.append(plan)

        account_saved = False
        if actionable:
            try:
                self.account_repository.save(working_account)
                account_saved = True
            except AccountRepositoryError as exc:
                raise CloseSignalOrchestrationError(
                    f"账户保存失败，信号保持 pending 可重试：{exc}"
                ) from exc

        for plan in plans:
            try:
                self.signal_repository.mark_dispatch(
                    plan.signal.signal_id,
                    plan.status,
                    now,
                    plan.message,
                    plan.order_id,
                )
            except SignalRepositoryError as exc:
                outcomes_by_id[plan.signal.signal_id] = SignalDispatchOutcome(
                    signal_id=plan.signal.signal_id,
                    symbol=plan.signal.symbol,
                    status=SignalDispatchStatus.PENDING,
                    order_id=plan.order_id,
                    message=f"派发结果待重启对账：{exc}",
                )
                continue
            outcomes_by_id[plan.signal.signal_id] = SignalDispatchOutcome(
                signal_id=plan.signal.signal_id,
                symbol=plan.signal.symbol,
                status=plan.status,
                order_id=plan.order_id,
                message=plan.message,
            )

        outcomes = tuple(
            sorted(
                outcomes_by_id.values(),
                key=lambda item: (item.signal_id, item.symbol),
            )
        )
        return CloseSignalCycleResult(
            run_at=now,
            scheduled_for=scheduled_open,
            received_count=len(signals),
            inserted_count=persisted.inserted_count,
            recovered_pending_count=recovered_count,
            orders_created_count=sum(plan.created_order for plan in plans),
            account_saved=account_saved,
            outcomes=outcomes,
        )

    def validate_close_session(self, current_time: datetime) -> None:
        local_time = _localize(current_time)
        if not self.trading_calendar.is_trading_day(local_time.date()):
            raise CloseSignalOrchestrationError("当前不是交易日，禁止生成收盘交易任务")
        if local_time.time().replace(tzinfo=None) < self.CLOSE_TIME:
            raise CloseSignalOrchestrationError("必须在交易日15:00收盘后运行信号编排")

    def _load_market_context(
        self,
        pending: list[PersistedSignal],
        account: SimulatedAccount,
        current_time: datetime,
    ) -> tuple[dict[str, Quote], dict[str, Instrument]]:
        symbols = {item.symbol for item in pending if item.direction is not SignalDirection.HOLD}
        symbols.update(account.positions)
        symbols.update(order.symbol for order in account.orders if not order.status.is_terminal)
        try:
            quotes = self.market_data.get_latest_quotes(sorted(symbols)) if symbols else []
            instruments = self.market_data.get_stock_list()
        except (MarketDataError, KeyError, IndexError, ValueError) as exc:
            raise CloseSignalOrchestrationError(f"收盘行情读取失败：{exc}") from exc
        quote_map = {quote.symbol: quote for quote in quotes}
        instrument_map = {instrument.symbol: instrument for instrument in instruments}
        for symbol in account.positions:
            quote = quote_map.get(symbol)
            if quote is None or not _is_same_day_quote(quote, current_time):
                raise CloseSignalOrchestrationError(
                    f"持仓 {symbol} 缺少当日收盘行情，无法计算真实净值与回撤"
                )
        for order in account.orders:
            if (
                order.side is OrderSide.BUY
                and not order.status.is_terminal
                and order.limit_price is None
            ):
                quote = quote_map.get(order.symbol)
                if quote is None or not _is_same_day_quote(quote, current_time):
                    raise CloseSignalOrchestrationError(
                        f"未完成买单 {order.order_id} 缺少当日行情，无法核算预留仓位"
                    )
        return quote_map, instrument_map

    def _plan_signal(
        self,
        signal: PersistedSignal,
        account: SimulatedAccount,
        current_time: datetime,
        quote_map: dict[str, Quote],
        instrument_map: dict[str, Instrument],
    ) -> _DispatchPlan:
        existing_order = next(
            (order for order in account.orders if order.signal_id == signal.signal_id),
            None,
        )
        if existing_order is not None:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.ORDER_CREATED,
                "已从账户审计记录恢复关联订单",
                existing_order.order_id,
            )
        timing_error = _signal_timing_error(signal)
        if timing_error:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                timing_error,
            )
        if signal.scheduled_for <= current_time.date():
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                "已错过计划开盘，拒绝补发以避免追单",
            )
        if signal.direction is SignalDirection.HOLD:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.SKIPPED,
                "观察信号不生成订单",
            )
        if self.mode is RuntimeMode.RESEARCH:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.SKIPPED,
                "research模式只保存研究信号，不创建模拟订单",
            )

        quote = quote_map.get(signal.symbol)
        if quote is None:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                "缺少当日收盘行情，无法计算订单数量",
            )
        if not _is_same_day_quote(quote, current_time):
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                "行情不是当日收盘数据或行情时间晚于当前时间",
            )
        instrument = instrument_map.get(signal.symbol)
        if instrument is None:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                "股票不在当前沪深A股主表中",
            )
        if not instrument.is_eligible(current_time.date()):
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                "股票不满足ST、退市和上市满60日过滤规则",
            )
        if not Decimal("0") <= signal.suggested_position_pct <= Decimal("1"):
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                "建议目标仓位必须在0%到100%之间",
            )

        signal_scheduled_open = datetime.combine(
            signal.scheduled_for,
            time(9, 30),
            tzinfo=APP_TIME_ZONE,
        )
        if signal.direction is SignalDirection.BUY:
            return self._plan_buy(
                signal,
                account,
                current_time,
                signal_scheduled_open,
                quote,
                quote_map,
            )
        return self._plan_sell(
            signal,
            account,
            current_time,
            signal_scheduled_open,
            quote,
            quote_map,
        )

    def _plan_buy(
        self,
        signal: PersistedSignal,
        account: SimulatedAccount,
        current_time: datetime,
        scheduled_open: datetime,
        quote: Quote,
        quote_map: dict[str, Quote],
    ) -> _DispatchPlan:
        latest_prices = {symbol: item.last_price for symbol, item in quote_map.items()}
        reserved = _reserved_buy_values(account, quote_map)
        total_assets = account.total_assets(latest_prices)
        target_value = total_assets * signal.suggested_position_pct
        current_value = (
            account.positions[signal.symbol].market_value(quote.last_price)
            if signal.symbol in account.positions
            else Decimal("0")
        )
        value_to_buy = (
            target_value
            - current_value
            - reserved.get(
                signal.symbol,
                Decimal("0"),
            )
        )
        quantity = _floor_buy_quantity(value_to_buy, quote.last_price)
        if quantity <= 0:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.SKIPPED,
                "当前持仓与未完成买单已达到建议目标仓位",
            )
        order_value = quote.last_price * Decimal(quantity)
        risk_result = self.risk_manager.check_order(
            OrderSide.BUY,
            account,
            signal.symbol,
            order_value,
            latest_prices,
            reserved,
        )
        if not risk_result.passed:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                risk_result.message,
            )
        return self._create_order(
            signal,
            account,
            OrderSide.BUY,
            quantity,
            current_time,
            scheduled_open,
        )

    def _plan_sell(
        self,
        signal: PersistedSignal,
        account: SimulatedAccount,
        current_time: datetime,
        scheduled_open: datetime,
        quote: Quote,
        quote_map: dict[str, Quote],
    ) -> _DispatchPlan:
        position = account.positions.get(signal.symbol)
        if position is None:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.SKIPPED,
                "当前没有可安排卖出的持仓",
            )
        latest_prices = {symbol: item.last_price for symbol, item in quote_map.items()}
        target_value = account.total_assets(latest_prices) * signal.suggested_position_pct
        target_quantity = int(
            (target_value / quote.last_price).to_integral_value(rounding=ROUND_FLOOR)
        )
        pending_sell_quantity = sum(
            order.remaining_quantity or 0
            for order in account.orders
            if (
                order.symbol == signal.symbol
                and order.side is OrderSide.SELL
                and not order.status.is_terminal
            )
        )
        quantity = max(
            0,
            position.quantity - target_quantity - pending_sell_quantity,
        )
        if quantity <= 0:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.SKIPPED,
                "持仓与未完成卖单已达到建议目标仓位",
            )
        risk_result = self.risk_manager.check_order(
            OrderSide.SELL,
            account,
            signal.symbol,
            quote.last_price * Decimal(quantity),
            {signal.symbol: quote.last_price},
        )
        if not risk_result.passed:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                risk_result.message,
            )
        return self._create_order(
            signal,
            account,
            OrderSide.SELL,
            quantity,
            current_time,
            scheduled_open,
        )

    @staticmethod
    def _create_order(
        signal: PersistedSignal,
        account: SimulatedAccount,
        side: OrderSide,
        quantity: int,
        current_time: datetime,
        scheduled_open: datetime,
    ) -> _DispatchPlan:
        order_id = build_signal_order_id(signal.signal_id)
        try:
            order = account.submit_order(
                signal.symbol,
                side,
                quantity,
                current_time,
                order_type=OrderType.NEXT_OPEN,
                eligible_at=scheduled_open,
                order_id=order_id,
                signal_id=signal.signal_id,
            )
        except (AccountError, ValueError) as exc:
            return _DispatchPlan(
                signal,
                SignalDispatchStatus.REJECTED,
                str(exc),
            )
        return _DispatchPlan(
            signal,
            SignalDispatchStatus.ORDER_CREATED,
            "已创建下一交易日开盘模拟订单",
            order.order_id,
            True,
        )


def build_signal_order_id(signal_id: str) -> str:
    return f"O-{signal_id.removeprefix('S-')}"


def _reserved_buy_values(
    account: SimulatedAccount,
    quote_map: dict[str, Quote],
) -> dict[str, Decimal]:
    reserved: dict[str, Decimal] = {}
    for order in account.orders:
        if order.side is not OrderSide.BUY or order.status.is_terminal:
            continue
        quote = quote_map.get(order.symbol)
        price = order.limit_price or (quote.last_price if quote is not None else None)
        if price is None:
            continue
        value = price * Decimal(order.remaining_quantity or 0)
        reserved[order.symbol] = reserved.get(order.symbol, Decimal("0")) + value
    return reserved


def _floor_buy_quantity(value: Decimal, price: Decimal) -> int:
    if value <= Decimal("0") or price <= Decimal("0"):
        return 0
    raw_quantity = int((value / price).to_integral_value(rounding=ROUND_FLOOR))
    lot_size = TradingRules().buy_lot_size
    return raw_quantity - raw_quantity % lot_size


def _signal_timing_error(signal: PersistedSignal) -> str:
    signal_time = _localize(signal.signal_time)
    market_time = _localize(signal.market_time)
    created_at = _localize(signal.created_at)
    if signal_time > created_at or market_time > created_at:
        return "信号或市场数据时间晚于收盘任务时间"
    if signal_time.date() != created_at.date() or market_time.date() != created_at.date():
        return "信号必须使用收盘任务当日的市场数据"
    return ""


def _is_same_day_quote(quote: Quote, current_time: datetime) -> bool:
    quote_time = _localize(quote.quote_time)
    return quote_time.date() == current_time.date() and quote_time <= current_time


def _localize(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=APP_TIME_ZONE)
    return value.astimezone(APP_TIME_ZONE)
