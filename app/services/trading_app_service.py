from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.backtest import BacktestResult, DailyBacktestEngine
from app.config import APP_TIME_ZONE
from app.data.providers import (
    Instrument,
    MarketDataError,
    MarketDataProvider,
    MockMarketDataProvider,
    Quote,
)
from app.database import AccountRepository, AccountRepositoryError
from app.execution import SimulatedMatcher, identify_security
from app.models import Fill, Order, OrderSide, OrderStatus
from app.portfolio import AccountError, SimulatedAccount
from app.risk import RiskManager
from app.services.strategy_service import StrategyService
from app.strategies import MovingAverageTrendStrategy


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
    ) -> None:
        self.market_data = market_data or MockMarketDataProvider()
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
        self.matcher = SimulatedMatcher()
        self.strategy_service = StrategyService(self.market_data)
        self.watchlist = ["600519.SH", "000001.SZ", "300750.SZ", "688001.SH"]

    def get_dashboard_metrics(self) -> dict[str, str]:
        quotes = self.get_watchlist_quotes()
        latest_prices = {quote.symbol: quote.last_price for quote in quotes}
        health = self.market_data.health_check()
        return {
            "market_status": "交易日Mock",
            "data_source": health.provider,
            "data_status": "正常" if health.ok else "异常",
            "account_total": format_money(self.account.total_assets(latest_prices)),
            "cash": format_money(self.account.cash),
            "market_value": format_money(self.account.market_value(latest_prices)),
            "persistence_status": "正常" if not self.persistence_error else "不可用",
            "risk_status": "允许交易",
            "running_strategy": "未运行",
        }

    def get_watchlist_quotes(self) -> list[Quote]:
        return self.market_data.get_latest_quotes(self.watchlist)

    def get_instruments(self) -> list[Instrument]:
        return self.market_data.get_stock_list()

    def latest_price_map(self) -> dict[str, Decimal]:
        return {quote.symbol: quote.last_price for quote in self.get_watchlist_quotes()}

    def place_manual_order(
        self,
        side: OrderSide,
        symbol_or_code: str,
        quantity: int,
        limit_price: Decimal | None = None,
        current_time: datetime | None = None,
    ) -> ManualOrderResult:
        if self.persistence_required and self.account_repository is None:
            message = self.persistence_error or "账户数据库不可用"
            return ManualOrderResult(False, None, None, message)

        now = current_time or datetime.now(APP_TIME_ZONE)
        working_account = deepcopy(self.account)
        order: Order | None = None
        try:
            identity = identify_security(symbol_or_code)
            symbol = identity.symbol
            quote = self.market_data.get_latest_quotes([symbol])[0]
            instrument = self._find_instrument(symbol)
            order_price = limit_price or quote.last_price
            if side is OrderSide.BUY:
                risk_result = self.risk.check_order(
                    side,
                    working_account,
                    symbol,
                    order_price * Decimal(quantity),
                    self.latest_price_map(),
                )
                if not risk_result.passed:
                    return ManualOrderResult(False, None, None, risk_result.message)

            order = working_account.submit_order(
                symbol, side, quantity, now, limit_price=limit_price
            )
            execution = self.matcher.evaluate(
                order,
                quote,
                instrument,
                now,
                interval_volume=quote.volume,
                has_order_book=True,
            )
            if execution.status in {OrderStatus.FILLED, OrderStatus.PARTIALLY_FILLED}:
                fill = working_account.apply_fill(
                    order,
                    execution.fill_price or quote.last_price,
                    execution.fill_quantity,
                    now,
                    stock_name=quote.name,
                    degraded_model=execution.degraded_model,
                )
                updated_order = working_account.update_order_status(
                    order, execution.status, execution.reason
                )
                self._commit_account(working_account)
                return ManualOrderResult(True, updated_order, fill, execution.reason)

            updated_order = working_account.update_order_status(
                order, execution.status, execution.reason
            )
            self._commit_account(working_account)
            return ManualOrderResult(False, updated_order, None, execution.reason)
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

    def advance_trading_day(self) -> None:
        working_account = deepcopy(self.account)
        working_account.advance_trading_day()
        self._commit_account(working_account)

    def run_demo_backtest(self) -> BacktestResult:
        engine = DailyBacktestEngine(self.market_data)
        strategy = MovingAverageTrendStrategy({"short_window": 3, "long_window": 5})
        return engine.run(strategy, "000001.SZ", date(2026, 4, 1), date(2026, 7, 27))

    def _find_instrument(self, symbol: str) -> Instrument:
        for instrument in self.market_data.get_stock_list():
            if instrument.symbol == symbol:
                return instrument
        raise ValueError(f"未知股票代码：{symbol}")

    def _commit_account(self, account: SimulatedAccount) -> None:
        if self.account_repository is not None:
            self.account_repository.save(account)
        self.account = account


def format_money(value: Decimal) -> str:
    return f"¥{value:,.2f}"
