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
    CREATED = "已创建"
    PENDING_NEXT_OPEN = "等待下一交易日开盘"
    ELIGIBLE = "可撮合"
    PARTIALLY_FILLED = "部分成交"
    FILLED = "已成交"
    DEFERRED = "顺延"
    CANCELLED = "已撤销"
    EXPIRED = "已过期"
    REJECTED = "已拒绝"

    # 仅用于读取旧数据库；新订单不得进入这些状态。
    PENDING_SUBMIT = "待提交"
    PENDING_FILL = "待成交"

    @property
    def is_terminal(self) -> bool:
        return self in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }


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
    status: OrderStatus = OrderStatus.CREATED
    reason: str = ""
    eligible_at: datetime | None = None
    filled_quantity: int = 0
    remaining_quantity: int | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        remaining = (
            self.quantity - self.filled_quantity
            if self.remaining_quantity is None
            else self.remaining_quantity
        )
        if self.quantity <= 0:
            raise ValueError("订单数量必须大于0")
        if self.filled_quantity < 0 or remaining < 0:
            raise ValueError("成交数量和剩余数量不能为负数")
        if self.filled_quantity + remaining != self.quantity:
            raise ValueError("订单数量必须等于已成交数量与剩余数量之和")
        object.__setattr__(self, "remaining_quantity", remaining)


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
