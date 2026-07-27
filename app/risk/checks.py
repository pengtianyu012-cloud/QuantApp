from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.config import TradingRules
from app.models import OrderSide
from app.portfolio import SimulatedAccount


@dataclass(frozen=True)
class RiskResult:
    passed: bool
    message: str
    adjusted_value: Decimal | None = None


@dataclass(frozen=True)
class RiskLimits:
    max_single_position_pct: Decimal = TradingRules().max_single_position_pct
    max_total_position_pct: Decimal = TradingRules().max_total_position_pct
    max_drawdown_pct: Decimal = TradingRules().max_drawdown_pct


class RiskManager:
    def __init__(self, limits: RiskLimits | None = None) -> None:
        self.limits = limits or RiskLimits()

    def check_buy_order(
        self,
        account: SimulatedAccount,
        symbol: str,
        order_value: Decimal,
        latest_prices: dict[str, Decimal],
        current_drawdown: Decimal = Decimal("0"),
    ) -> RiskResult:
        if current_drawdown >= self.limits.max_drawdown_pct:
            return RiskResult(False, "最大回撤达到15%，暂停新增买入")
        total_assets = account.total_assets(latest_prices)
        if total_assets <= Decimal("0"):
            return RiskResult(False, "账户总资产必须大于0")
        current_symbol_value = Decimal("0")
        if symbol in account.positions:
            price = latest_prices.get(symbol, account.positions[symbol].cost_price)
            current_symbol_value = account.positions[symbol].market_value(price)
        after_symbol_pct = (current_symbol_value + order_value) / total_assets
        if after_symbol_pct > self.limits.max_single_position_pct:
            return RiskResult(False, "单股仓位超过30%限制")

        total_position_value = account.market_value(latest_prices) + order_value
        if total_position_value / total_assets > self.limits.max_total_position_pct:
            return RiskResult(False, "总仓位超过90%限制")
        if order_value > account.cash:
            return RiskResult(False, "可用现金不足")
        return RiskResult(True, "风控通过")

    def check_order(
        self,
        side: OrderSide,
        account: SimulatedAccount,
        symbol: str,
        order_value: Decimal,
        latest_prices: dict[str, Decimal],
        current_drawdown: Decimal = Decimal("0"),
    ) -> RiskResult:
        if side is OrderSide.SELL:
            return RiskResult(True, "卖出不受新增买入风控暂停限制")
        return self.check_buy_order(account, symbol, order_value, latest_prices, current_drawdown)
