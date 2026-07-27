from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from app.config import TradingCostSettings, TradingRules
from app.execution.costs import calculate_trade_cost
from app.execution.trading_rules import is_t_plus_one_sell_allowed, is_valid_buy_quantity
from app.models import Fill, Order, OrderSide, OrderStatus, OrderType, Position

MONEY_QUANT = Decimal("0.01")


class AccountError(RuntimeError):
    """模拟账户业务异常。"""


@dataclass
class SimulatedAccount:
    account_id: str = "SIM-001"
    name: str = "本地模拟账户"
    initial_cash: Decimal = TradingRules().initial_cash
    cash: Decimal = TradingRules().initial_cash
    positions: dict[str, Position] = field(default_factory=dict)
    orders: list[Order] = field(default_factory=list)
    fills: list[Fill] = field(default_factory=list)

    def market_value(self, latest_prices: dict[str, Decimal]) -> Decimal:
        total = Decimal("0")
        for symbol, position in self.positions.items():
            price = latest_prices.get(symbol, position.cost_price)
            total += position.market_value(price)
        return quantize_money(total)

    def total_assets(self, latest_prices: dict[str, Decimal] | None = None) -> Decimal:
        prices = latest_prices or {}
        return quantize_money(self.cash + self.market_value(prices))

    def submit_order(
        self,
        symbol: str,
        side: OrderSide,
        quantity: int,
        submitted_at: datetime,
        order_type: OrderType = OrderType.NEXT_OPEN,
        limit_price: Decimal | None = None,
    ) -> Order:
        if side is OrderSide.BUY and not is_valid_buy_quantity(quantity):
            raise AccountError("普通A股买入数量必须是100股整数倍")
        if quantity <= 0:
            raise AccountError("订单数量必须大于0")

        order = Order(
            order_id=f"O-{uuid4().hex[:12]}",
            account_id=self.account_id,
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            submitted_at=submitted_at,
            limit_price=limit_price,
            status=OrderStatus.PENDING_FILL,
        )
        self.orders.append(order)
        return order

    def update_order_status(self, order: Order, status: OrderStatus, reason: str = "") -> Order:
        updated_order = replace(order, status=status, reason=reason)
        self.orders = [updated_order if item.order_id == order.order_id else item for item in self.orders]
        return updated_order

    def apply_fill(
        self,
        order: Order,
        price: Decimal,
        quantity: int,
        filled_at: datetime,
        stock_name: str = "",
        settings: TradingCostSettings | None = None,
        degraded_model: bool = False,
    ) -> Fill:
        if quantity <= 0:
            raise AccountError("成交数量必须大于0")
        if quantity > order.quantity:
            raise AccountError("成交数量不能超过订单数量")
        costs = calculate_trade_cost(order.side, price, quantity, settings)
        fill = Fill(
            fill_id=f"F-{uuid4().hex[:12]}",
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=quantity,
            price=price,
            commission=costs.commission,
            tax=costs.stamp_tax,
            transfer_fee=costs.transfer_fee,
            slippage=costs.slippage,
            filled_at=filled_at,
            degraded_model=degraded_model,
        )
        if order.side is OrderSide.BUY:
            cash_required = costs.notional + costs.total
            if cash_required > self.cash:
                raise AccountError("可用现金不足")
            self.cash = quantize_money(self.cash - cash_required)
            self._increase_position(order.symbol, stock_name or order.symbol, quantity, price, filled_at.date())
        else:
            self._decrease_position(order.symbol, quantity, price, filled_at.date())
            cash_in = costs.notional - costs.total
            self.cash = quantize_money(self.cash + cash_in)
        self.fills.append(fill)
        return fill

    def advance_trading_day(self) -> None:
        for position in self.positions.values():
            position.available_quantity = position.quantity

    def _increase_position(self, symbol: str, name: str, quantity: int, price: Decimal, buy_date: date) -> None:
        position = self.positions.get(symbol)
        if position is None:
            self.positions[symbol] = Position(
                symbol=symbol,
                name=name,
                quantity=quantity,
                available_quantity=0,
                cost_price=price,
                last_buy_date=buy_date,
            )
            return
        old_value = position.cost_price * Decimal(position.quantity)
        new_value = price * Decimal(quantity)
        new_quantity = position.quantity + quantity
        position.cost_price = quantize_money((old_value + new_value) / Decimal(new_quantity))
        position.quantity = new_quantity
        position.last_buy_date = buy_date

    def _decrease_position(self, symbol: str, quantity: int, price: Decimal, sell_date: date) -> None:
        position = self.positions.get(symbol)
        if position is None:
            raise AccountError("没有可卖持仓")
        if not is_t_plus_one_sell_allowed(position.last_buy_date, sell_date):
            raise AccountError("T+1限制：当日买入股票当日不能卖出")
        if quantity > position.available_quantity:
            raise AccountError("可卖数量不足")
        position.quantity -= quantity
        position.available_quantity -= quantity
        if position.quantity == 0:
            self.positions.pop(symbol)


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
