from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum


class OrderSide(StrEnum):
    BUY = "买入"
    SELL = "卖出"


class OrderType(StrEnum):
    MARKET = "市价模拟单"
    LIMIT = "限价模拟单"
    NEXT_OPEN = "下一交易日开盘单"
    CANCEL = "撤单"


class OrderStatus(StrEnum):
    PENDING_SUBMIT = "待提交"
    PENDING_FILL = "待成交"
    PARTIALLY_FILLED = "部分成交"
    FILLED = "已成交"
    CANCELLED = "已撤销"
    REJECTED = "已拒绝"
    DEFERRED = "顺延"
    EXPIRED = "已过期"


@dataclass(frozen=True)
class Order:
    order_id: str
    account_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    submitted_at: datetime
    limit_price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING_FILL
    reason: str = ""


@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal
    commission: Decimal
    tax: Decimal
    transfer_fee: Decimal
    slippage: Decimal
    filled_at: datetime
    degraded_model: bool = False


@dataclass
class Position:
    symbol: str
    name: str
    quantity: int
    available_quantity: int
    cost_price: Decimal
    last_buy_date: date | None = None

    def market_value(self, last_price: Decimal) -> Decimal:
        return last_price * Decimal(self.quantity)
