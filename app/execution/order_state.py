from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from app.models import Order, OrderStatus


class InvalidOrderTransition(ValueError):
    """订单状态转换不符合交易生命周期。"""


_ALLOWED_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.CREATED: frozenset(
        {
            OrderStatus.PENDING_NEXT_OPEN,
            OrderStatus.ELIGIBLE,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.PENDING_NEXT_OPEN: frozenset(
        {
            OrderStatus.ELIGIBLE,
            OrderStatus.DEFERRED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.ELIGIBLE: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.DEFERRED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.PARTIALLY_FILLED: frozenset(
        {
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
            OrderStatus.DEFERRED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.DEFERRED: frozenset(
        {
            OrderStatus.ELIGIBLE,
            OrderStatus.DEFERRED,
            OrderStatus.CANCELLED,
            OrderStatus.EXPIRED,
            OrderStatus.REJECTED,
        }
    ),
    OrderStatus.FILLED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
    OrderStatus.EXPIRED: frozenset(),
    OrderStatus.REJECTED: frozenset(),
    OrderStatus.PENDING_SUBMIT: frozenset(
        {OrderStatus.PENDING_NEXT_OPEN, OrderStatus.ELIGIBLE, OrderStatus.REJECTED}
    ),
    OrderStatus.PENDING_FILL: frozenset(
        {OrderStatus.ELIGIBLE, OrderStatus.DEFERRED, OrderStatus.REJECTED}
    ),
}


class OrderStateMachine:
    @staticmethod
    def transition(
        order: Order,
        target: OrderStatus,
        occurred_at: datetime,
        reason: str = "",
    ) -> Order:
        if target is order.status:
            return replace(order, reason=reason, updated_at=occurred_at)
        if target not in _ALLOWED_TRANSITIONS[order.status]:
            raise InvalidOrderTransition(
                f"非法订单状态转换：{order.status.name} -> {target.name}"
            )
        return replace(order, status=target, reason=reason, updated_at=occurred_at)

    @staticmethod
    def apply_fill_progress(
        order: Order,
        fill_quantity: int,
        occurred_at: datetime,
        reason: str,
    ) -> Order:
        remaining = order.remaining_quantity or 0
        if fill_quantity <= 0 or fill_quantity > remaining:
            raise InvalidOrderTransition("成交数量必须大于0且不能超过订单剩余数量")

        working = order
        if working.status in {
            OrderStatus.PENDING_NEXT_OPEN,
            OrderStatus.DEFERRED,
            OrderStatus.PENDING_FILL,
        }:
            working = OrderStateMachine.transition(
                working, OrderStatus.ELIGIBLE, occurred_at, "订单进入可撮合状态"
            )
        if working.status not in {OrderStatus.ELIGIBLE, OrderStatus.PARTIALLY_FILLED}:
            raise InvalidOrderTransition(f"订单状态 {working.status.value} 不允许成交")

        new_filled = working.filled_quantity + fill_quantity
        new_remaining = working.quantity - new_filled
        target = OrderStatus.FILLED if new_remaining == 0 else OrderStatus.PARTIALLY_FILLED
        progressed = replace(
            working,
            filled_quantity=new_filled,
            remaining_quantity=new_remaining,
        )
        return OrderStateMachine.transition(progressed, target, occurred_at, reason)
