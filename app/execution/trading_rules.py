from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from app.config import APP_TIME_ZONE, TradingRules

PRICE_QUANT = Decimal("0.01")


@dataclass(frozen=True)
class SecurityIdentity:
    symbol: str
    code: str
    exchange: str
    board: str


@dataclass(frozen=True)
class PriceLimit:
    limit_up: Decimal | None
    limit_down: Decimal | None
    pct: Decimal | None
    uncertain: bool
    reason: str


def identify_security(symbol_or_code: str) -> SecurityIdentity:
    raw = symbol_or_code.strip().upper()
    if "." in raw:
        code, exchange = raw.split(".", 1)
    elif raw.startswith(("6", "9")):
        code, exchange = raw, "SH"
    elif raw.startswith(("0", "2", "3")):
        code, exchange = raw, "SZ"
    else:
        raise ValueError(f"无法识别A股代码：{symbol_or_code}")

    if exchange not in {"SH", "SZ"}:
        raise ValueError(f"暂不支持的交易所：{exchange}")
    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"股票代码必须是6位数字：{symbol_or_code}")

    return SecurityIdentity(
        symbol=f"{code}.{exchange}", code=code, exchange=exchange, board=detect_board(code)
    )


def detect_board(code: str) -> str:
    if code.startswith("688"):
        return "科创板"
    if code.startswith(("300", "301")):
        return "创业板"
    return "主板"


def is_valid_buy_quantity(quantity: int, lot_size: int = TradingRules().buy_lot_size) -> bool:
    return quantity > 0 and quantity % lot_size == 0


def is_valid_sell_quantity(quantity: int) -> bool:
    return quantity > 0


def is_t_plus_one_sell_allowed(last_buy_date: date | None, sell_date: date) -> bool:
    return last_buy_date is None or sell_date > last_buy_date


def get_market_phase(moment: datetime, is_trading_day: bool) -> str:
    local_moment = (
        moment.astimezone(APP_TIME_ZONE) if moment.tzinfo else moment.replace(tzinfo=APP_TIME_ZONE)
    )
    current_time = local_moment.time()
    if not is_trading_day:
        return "非交易日"
    if current_time < time(9, 15):
        return "开盘前"
    if time(9, 15) <= current_time < time(9, 25):
        return "集合竞价"
    if time(9, 30) <= current_time <= time(11, 30):
        return "连续竞价"
    if time(11, 30) < current_time < time(13, 0):
        return "午间休市"
    if time(13, 0) <= current_time <= time(15, 0):
        return "连续竞价"
    return "收盘后"


def price_limit_pct(board: str, is_st: bool = False, listing_days: int | None = None) -> PriceLimit:
    if listing_days is not None and listing_days < TradingRules().min_listing_days:
        return PriceLimit(None, None, None, True, "上市不足60日，规则不确定，禁止强制模拟成交")
    if is_st:
        pct = Decimal("0.05")
    elif board in {"创业板", "科创板"}:
        pct = Decimal("0.20")
    else:
        pct = Decimal("0.10")
    return PriceLimit(None, None, pct, False, "规则明确")


def calculate_price_limits(
    prev_close: Decimal,
    board: str,
    is_st: bool = False,
    listing_days: int | None = None,
) -> PriceLimit:
    pct_rule = price_limit_pct(board=board, is_st=is_st, listing_days=listing_days)
    if pct_rule.uncertain or pct_rule.pct is None:
        return pct_rule
    limit_up = (prev_close * (Decimal("1") + pct_rule.pct)).quantize(PRICE_QUANT, ROUND_HALF_UP)
    limit_down = (prev_close * (Decimal("1") - pct_rule.pct)).quantize(PRICE_QUANT, ROUND_HALF_UP)
    return PriceLimit(limit_up, limit_down, pct_rule.pct, False, "规则明确")


def is_at_limit_up(last_price: Decimal, limit_up: Decimal | None) -> bool:
    return limit_up is not None and last_price >= limit_up


def is_at_limit_down(last_price: Decimal, limit_down: Decimal | None) -> bool:
    return limit_down is not None and last_price <= limit_down
