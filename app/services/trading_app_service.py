from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from threading import RLock

from app.backtest import BacktestResult, DailyBacktestEngine
from app.config import APP_TIME_ZONE, RuntimeMode, TradingRules, resolve_runtime_mode
from app.data.providers import (
    AkSharePublicMarketDataProvider,
    Instrument,
    MarketDataError,
    MarketDataProvider,
    MockMarketDataProvider,
    OrderBook,
    ProviderHealth,
    Quote,
)
from app.database import AccountRepository, AccountRepositoryError
from app.execution import (
    ProviderTradingCalendar,
    SimulatedMatcher,
    TradingCalendar,
    identify_security,
)
from app.models import Fill, Order, OrderSide, OrderStatus, OrderType, PortfolioSnapshot
from app.portfolio import AccountError, SimulatedAccount
from app.risk import RiskManager
from app.services.strategy_service import StrategyService
from app.strategies import MovingAverageTrendStrategy
from app.utils.clock import Clock, SystemClock


@dataclass(frozen=True)
class ManualOrderResult:
    ok: bool
    order: Order | None
    fill: Fill | None
    message: str


class TradingAppService:
    """桌面端使用的应用服务，组合Mock行情、账户、风控、撮合、策略和回测。"""

    def __init__(
        self,
        market_data: MarketDataProvider | None = None,
        account_repository: AccountRepository | None = None,
        db_path: Path | None = None,
        persist_account: bool = True,
        background_market_data: bool | None = None,
        mode: RuntimeMode | str | None = None,
        clock: Clock | None = None,
        trading_calendar: TradingCalendar | None = None,
    ) -> None:
        if mode is None and market_data is not None:
            mode = (
                RuntimeMode.MOCK
                if isinstance(market_data, MockMarketDataProvider)
                else RuntimeMode.RESEARCH
            )
        self.mode = resolve_runtime_mode(mode)
        self.clock = clock or SystemClock()
        self.market_data = market_data or build_default_market_data_provider(self.mode, self.clock)
        if self.mode.requires_real_market_data and isinstance(
            self.market_data, MockMarketDataProvider
        ):
            raise ValueError(f"{self.mode.value} 模式禁止使用 MockMarketDataProvider")
        self.trading_calendar = trading_calendar or ProviderTradingCalendar(self.market_data)
        self.background_market_data = (
            background_market_data
            if background_market_data is not None
            else self.mode.requires_real_market_data
        )
        self._market_lock = RLock()
        self._account_lock = RLock()
        self._quote_snapshot: list[Quote] = []
        self._instrument_snapshot: list[Instrument] = []
        self._order_book_snapshots: dict[str, OrderBook] = {}
        self._provider_health: ProviderHealth | None = None
        self.last_market_error = ""
        self.persistence_required = persist_account
        self.persistence_error = ""
        self.account_repository = account_repository
        if self.account_repository is None and persist_account:
            try:
                self.account_repository = AccountRepository(db_path)
            except AccountRepositoryError as exc:
                self.persistence_error = str(exc)

        self.account = SimulatedAccount()
        if self.account_repository is not None:
            try:
                restored = self.account_repository.load(self.account.account_id)
                if restored is None:
                    self.account_repository.save(self.account)
                else:
                    self.account = restored
            except AccountRepositoryError as exc:
                self.persistence_error = str(exc)
                self.account_repository = None
        self.risk = RiskManager()
        self.matcher = SimulatedMatcher(self.trading_calendar)
        self.strategy_service = StrategyService(self.market_data, self.clock)
        self.watchlist = ["600519.SH", "000001.SZ", "300750.SZ", "688001.SH"]

    def get_dashboard_metrics(self) -> dict[str, str]:
        quotes = self.get_watchlist_quotes()
        latest_prices = {quote.symbol: quote.last_price for quote in quotes}
        health = self.provider_health()
        quote_delay = max(
            (quote_age_seconds(self.clock.now(), quote.quote_time) for quote in quotes),
            default=None,
        )
        return {
            "market_status": {
                RuntimeMode.MOCK: "Mock离线模式",
                RuntimeMode.RESEARCH: "真实行情研究模式",
                RuntimeMode.PAPER: "真实行情模拟盘模式",
            }[self.mode],
            "data_source": self.market_data.name,
            "data_status": (
                "等待后台连接" if health is None else ("正常" if health.ok else "异常")
            ),
            "quote_delay": f"{quote_delay}秒" if quote_delay is not None else "-",
            "account_total": format_money(self.account.total_assets(latest_prices)),
            "cash": format_money(self.account.cash),
            "market_value": format_money(self.account.market_value(latest_prices)),
            "current_drawdown": format_ratio(self.account.current_drawdown),
            "max_drawdown": format_ratio(self.account.max_drawdown),
            "cumulative_fees": format_money(self.account.cumulative_fees),
            "persistence_status": "正常" if not self.persistence_error else "不可用",
            "risk_status": self.account.risk_status,
            "running_strategy": "未运行",
        }

    def get_watchlist_quotes(self) -> list[Quote]:
        if not self.background_market_data:
            return self.market_data.get_latest_quotes(self.watchlist)
        with self._market_lock:
            return list(self._quote_snapshot)

    def get_instruments(self) -> list[Instrument]:
        if not self.background_market_data:
            return self.market_data.get_stock_list()
        with self._market_lock:
            return list(self._instrument_snapshot)

    def refresh_watchlist_market_data(self) -> list[Quote]:
        quotes = self.market_data.get_latest_quotes(self.watchlist)
        order_books: dict[str, OrderBook] = {}
        for quote in quotes:
            try:
                order_books[quote.symbol] = self.market_data.get_order_book(quote.symbol)
            except MarketDataError:
                continue
        health = self.market_data.health_check()
        with self._market_lock:
            self._quote_snapshot = list(quotes)
            self._order_book_snapshots = order_books
            self._provider_health = health
            self.last_market_error = "" if health.ok else health.message
        self.record_portfolio_snapshot(self.clock.now(), quotes)
        return quotes

    def refresh_instruments(self) -> list[Instrument]:
        instruments = self.market_data.get_stock_list()
        with self._market_lock:
            self._instrument_snapshot = list(instruments)
        return instruments

    def record_market_error(self, message: str) -> None:
        with self._market_lock:
            self.last_market_error = message
            self._provider_health = ProviderHealth(
                provider=self.market_data.name,
                ok=False,
                message=message,
                checked_at=self.clock.now(),
            )

    def provider_health(self) -> ProviderHealth | None:
        if not self.background_market_data:
            return self.market_data.health_check()
        with self._market_lock:
            return self._provider_health

    def get_order_book_snapshot(self, symbol: str) -> OrderBook | None:
        with self._market_lock:
            return self._order_book_snapshots.get(symbol)

    def latest_price_map(self) -> dict[str, Decimal]:
        return {quote.symbol: quote.last_price for quote in self.get_watchlist_quotes()}

    def place_manual_order(
        self,
        side: OrderSide,
        symbol_or_code: str,
        quantity: int,
        limit_price: Decimal | None = None,
        current_time: datetime | None = None,
        order_type: OrderType | None = None,
    ) -> ManualOrderResult:
        if self.persistence_required and self.account_repository is None:
            message = self.persistence_error or "账户数据库不可用"
            return ManualOrderResult(False, None, None, message)

        if not self.mode.allows_manual_orders:
            return ManualOrderResult(False, None, None, "research 模式仅用于研究，禁止手工下单")

        now = current_time or self.clock.now()
        working_account = deepcopy(self.account)
        order: Order | None = None
        try:
            identity = identify_security(symbol_or_code)
            symbol = identity.symbol
            quote = next(
                (item for item in self.get_watchlist_quotes() if item.symbol == symbol),
                None,
            )
            if quote is None:
                raise MarketDataError("当前没有该股票的可用行情，请先后台刷新自选股")
            instrument = self._find_instrument(symbol)
            order_price = limit_price or quote.last_price
            latest_prices = self.latest_price_map()
            latest_prices[symbol] = quote.last_price
            working_account.record_snapshot(now, latest_prices)
            if side is OrderSide.BUY:
                risk_result = self.risk.check_order(
                    side,
                    working_account,
                    symbol,
                    order_price * Decimal(quantity),
                    latest_prices,
                )
                if not risk_result.passed:
                    self._commit_account(working_account)
                    return ManualOrderResult(False, None, None, risk_result.message)

            selected_order_type = order_type or (
                OrderType.LIMIT if limit_price is not None else OrderType.MARKET
            )
            eligible_at = None
            if selected_order_type is OrderType.NEXT_OPEN:
                next_open_date = self.trading_calendar.next_trading_day(now.date())
                eligible_at = datetime.combine(
                    next_open_date, time(9, 30), tzinfo=APP_TIME_ZONE
                )
            order = working_account.submit_order(
                symbol,
                side,
                quantity,
                now,
                order_type=selected_order_type,
                limit_price=limit_price,
                eligible_at=eligible_at,
            )
            execution = self.matcher.evaluate(
                order,
                quote,
                instrument,
                now,
                interval_volume=quote.volume,
                has_order_book=self.get_order_book_snapshot(symbol) is not None
                if self.background_market_data
                else True,
            )
            if execution.status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}:
                fill = working_account.apply_fill(
                    order,
                    execution.fill_price or quote.last_price,
                    execution.fill_quantity,
                    now,
                    stock_name=quote.name,
                    degraded_model=execution.degraded_model,
                    reason=execution.reason,
                    reference_price=execution.reference_price,
                )
                working_account.record_snapshot(now, latest_prices)
                updated_order = working_account.get_order(order.order_id)
                self._commit_account(working_account)
                return ManualOrderResult(True, updated_order, fill, execution.reason)

            updated_order = working_account.update_order_status(
                order, execution.status, execution.reason
            )
            working_account.record_snapshot(now, latest_prices)
            self._commit_account(working_account)
            accepted = not updated_order.status.is_terminal
            return ManualOrderResult(accepted, updated_order, None, execution.reason)
        except (AccountError, ValueError, IndexError, MarketDataError) as exc:
            if order is not None:
                rejected = working_account.update_order_status(
                    order, OrderStatus.REJECTED, str(exc)
                )
                try:
                    self._commit_account(working_account)
                except AccountRepositoryError as persistence_exc:
                    return ManualOrderResult(False, None, None, str(persistence_exc))
                return ManualOrderResult(False, rejected, None, str(exc))
            return ManualOrderResult(False, None, None, str(exc))
        except AccountRepositoryError as exc:
            return ManualOrderResult(False, None, None, str(exc))

    def process_pending_order(
        self,
        order_id: str,
        current_time: datetime | None = None,
    ) -> ManualOrderResult:
        if self.persistence_required and self.account_repository is None:
            message = self.persistence_error or "账户数据库不可用"
            return ManualOrderResult(False, None, None, message)
        now = current_time or self.clock.now()
        working_account = deepcopy(self.account)
        try:
            order = working_account.get_order(order_id)
            if order.status.is_terminal:
                return ManualOrderResult(False, order, None, "终态订单不可再次撮合")
            quote = next(
                (
                    item
                    for item in self.get_watchlist_quotes()
                    if item.symbol == order.symbol
                ),
                None,
            )
            if quote is None:
                raise MarketDataError("当前没有该股票的可用行情")
            instrument = self._find_instrument(order.symbol)
            latest_prices = self.latest_price_map()
            latest_prices[order.symbol] = quote.last_price
            working_account.record_snapshot(now, latest_prices)
            if order.side is OrderSide.BUY:
                risk_result = self.risk.check_order(
                    order.side,
                    working_account,
                    order.symbol,
                    quote.last_price * Decimal(order.remaining_quantity or 0),
                    latest_prices,
                )
                if not risk_result.passed:
                    updated_order = working_account.update_order_status(
                        order,
                        OrderStatus.DEFERRED,
                        risk_result.message,
                        occurred_at=now,
                    )
                    self._commit_account(working_account)
                    return ManualOrderResult(True, updated_order, None, risk_result.message)
            execution = self.matcher.evaluate(
                order,
                quote,
                instrument,
                now,
                interval_volume=quote.volume,
                has_order_book=self.get_order_book_snapshot(order.symbol) is not None
                if self.background_market_data
                else True,
            )
            if execution.status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}:
                fill = working_account.apply_fill(
                    order,
                    execution.fill_price or quote.last_price,
                    execution.fill_quantity,
                    now,
                    stock_name=quote.name,
                    degraded_model=execution.degraded_model,
                    reason=execution.reason,
                    reference_price=execution.reference_price,
                )
                working_account.record_snapshot(now, latest_prices)
                updated_order = working_account.get_order(order.order_id)
                self._commit_account(working_account)
                return ManualOrderResult(True, updated_order, fill, execution.reason)
            updated_order = working_account.update_order_status(
                order, execution.status, execution.reason, occurred_at=now
            )
            working_account.record_snapshot(now, latest_prices)
            self._commit_account(working_account)
            return ManualOrderResult(
                not updated_order.status.is_terminal,
                updated_order,
                None,
                execution.reason,
            )
        except (AccountError, ValueError, IndexError, MarketDataError) as exc:
            return ManualOrderResult(False, None, None, str(exc))
        except AccountRepositoryError as exc:
            return ManualOrderResult(False, None, None, str(exc))

    def advance_trading_day(self) -> None:
        working_account = deepcopy(self.account)
        working_account.advance_trading_day()
        self._commit_account(working_account)

    def record_portfolio_snapshot(
        self,
        snapshot_time: datetime | None = None,
        quotes: list[Quote] | None = None,
    ) -> PortfolioSnapshot:
        current_quotes = quotes if quotes is not None else self.get_watchlist_quotes()
        latest_prices = {quote.symbol: quote.last_price for quote in current_quotes}
        with self._account_lock:
            working_account = deepcopy(self.account)
            snapshot = working_account.record_snapshot(
                snapshot_time or self.clock.now(), latest_prices
            )
            self._commit_account(working_account)
        return snapshot

    def run_demo_backtest(self) -> BacktestResult:
        engine = DailyBacktestEngine(self.market_data)
        strategy = MovingAverageTrendStrategy({"short_window": 3, "long_window": 5})
        end_date = self.clock.today()
        start_date = _years_before(end_date, TradingRules().backtest_years)
        return engine.run(strategy, "000001.SZ", start_date, end_date)

    def _find_instrument(self, symbol: str) -> Instrument:
        for instrument in self.market_data.get_stock_list():
            if instrument.symbol == symbol:
                return instrument
        raise ValueError(f"未知股票代码：{symbol}")

    def _commit_account(self, account: SimulatedAccount) -> None:
        with self._account_lock:
            if self.account_repository is not None:
                self.account_repository.save(account)
            self.account = account


def format_money(value: Decimal) -> str:
    return f"¥{value:,.2f}"


def format_ratio(value: Decimal) -> str:
    return f"{value * Decimal('100'):.2f}%"


def quote_age_seconds(current_time: datetime, quote_time: datetime) -> int:
    current = (
        current_time.replace(tzinfo=APP_TIME_ZONE)
        if current_time.tzinfo is None or current_time.utcoffset() is None
        else current_time.astimezone(APP_TIME_ZONE)
    )
    quoted = (
        quote_time.replace(tzinfo=APP_TIME_ZONE)
        if quote_time.tzinfo is None or quote_time.utcoffset() is None
        else quote_time.astimezone(APP_TIME_ZONE)
    )
    return max(0, int((current - quoted).total_seconds()))


def build_default_market_data_provider(
    mode: RuntimeMode | str | None = None,
    clock: Clock | None = None,
) -> MarketDataProvider:
    selected_mode = resolve_runtime_mode(mode)
    if selected_mode.requires_real_market_data:
        return AkSharePublicMarketDataProvider()
    return MockMarketDataProvider(clock=clock)


def _years_before(value: date, years: int) -> date:
    try:
        return value.replace(year=value.year - years)
    except ValueError:
        return value.replace(year=value.year - years, day=28)
