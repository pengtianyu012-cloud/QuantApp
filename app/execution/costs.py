from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.config import TradingCostSettings
from app.models import OrderSide

MONEY_QUANT = Decimal("0.01")
BPS_DIVISOR = Decimal("10000")


@dataclass(frozen=True)
class TradeCostBreakdown:
    notional: Decimal
    commission: Decimal
    stamp_tax: Decimal
    transfer_fee: Decimal
    slippage: Decimal
    market_impact: Decimal

    @property
    def total(self) -> Decimal:
        return self.commission + self.stamp_tax + self.transfer_fee + self.slippage + self.market_impact


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def calculate_trade_cost(
    side: OrderSide,
    price: Decimal,
    quantity: int,
    settings: TradingCostSettings | None = None,
) -> TradeCostBreakdown:
    if quantity <= 0:
        raise ValueError("成交数量必须大于0")
    if price <= Decimal("0"):
        raise ValueError("成交价格必须大于0")

    config = settings or TradingCostSettings()
    notional = quantize_money(price * Decimal(quantity))
    commission = max(quantize_money(notional * config.commission_rate), config.min_commission)
    stamp_tax = quantize_money(notional * config.stamp_tax_rate) if side is OrderSide.SELL else Decimal("0")
    transfer_fee = quantize_money(notional * config.transfer_fee_rate)
    slippage = quantize_money(notional * config.slippage_bps / BPS_DIVISOR)
    market_impact = quantize_money(notional * config.market_impact_bps / BPS_DIVISOR)
    return TradeCostBreakdown(
        notional=notional,
        commission=commission,
        stamp_tax=stamp_tax,
        transfer_fee=transfer_fee,
        slippage=slippage,
        market_impact=market_impact,
    )


def execution_price_with_slippage(
    side: OrderSide,
    last_price: Decimal,
    settings: TradingCostSettings | None = None,
) -> Decimal:
    config = settings or TradingCostSettings()
    factor = config.slippage_bps / BPS_DIVISOR
    if side is OrderSide.BUY:
        return quantize_money(last_price * (Decimal("1") + factor))
    return quantize_money(last_price * (Decimal("1") - factor))
