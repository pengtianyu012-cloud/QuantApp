from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.data.providers.base import OrderBook, Quote


@dataclass(frozen=True)
class ValidationIssue:
    field: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: tuple[ValidationIssue, ...]


def validate_quote(quote: Quote) -> ValidationResult:
    issues: list[ValidationIssue] = []
    if not quote.symbol:
        issues.append(ValidationIssue("symbol", "股票代码不能为空"))
    if quote.last_price <= Decimal("0"):
        issues.append(ValidationIssue("last_price", "最新价必须大于0"))
    if quote.prev_close <= Decimal("0"):
        issues.append(ValidationIssue("prev_close", "昨收价必须大于0"))
    if quote.volume < 0:
        issues.append(ValidationIssue("volume", "成交量不能为负"))
    if quote.amount < Decimal("0"):
        issues.append(ValidationIssue("amount", "成交额不能为负"))
    if quote.quote_time.tzinfo is None:
        issues.append(ValidationIssue("quote_time", "行情时间必须包含时区"))
    if quote.delay_seconds < 0:
        issues.append(ValidationIssue("delay_seconds", "行情延迟不能为负"))
    return ValidationResult(ok=not issues, issues=tuple(issues))


def validate_order_book(order_book: OrderBook) -> ValidationResult:
    issues: list[ValidationIssue] = []
    if len(order_book.bids) != 5:
        issues.append(ValidationIssue("bids", "买盘必须包含5档或明确数据源不支持"))
    if len(order_book.asks) != 5:
        issues.append(ValidationIssue("asks", "卖盘必须包含5档或明确数据源不支持"))
    for side_name, levels in (("bids", order_book.bids), ("asks", order_book.asks)):
        for index, level in enumerate(levels, start=1):
            if level.price is not None and level.price <= Decimal("0"):
                issues.append(ValidationIssue(f"{side_name}_{index}_price", "盘口价格必须大于0"))
            if level.quantity is not None and level.quantity < 0:
                issues.append(ValidationIssue(f"{side_name}_{index}_quantity", "盘口委托量不能为负"))
    return ValidationResult(ok=not issues, issues=tuple(issues))
