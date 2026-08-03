from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.config import TradingCostSettings
from app.models import OrderSide

MONEY_QUANT = Decimal("0.01")
BPS_DIVISOR = Decimal("10000")


@dataclass(frozen=True)
class TradeCostBreakdown:
    reference_notional: Decimal
    notional: Decimal
    commission: Decimal
    stamp_tax: Decimal
    transfer_fee: Decimal
    slippage: Decimal
    market_impact: Decimal

    @property
    def cash_fees(self) -> Decimal:
        return self.commission + self.stamp_tax + self.transfer_fee

    @property
    def economic_cost(self) -> Decimal:
        return self.cash_fees + self.slippage + self.market_impact

    @property
    def total(self) -> Decimal:
        """兼容旧调用；表示经济成本，不可再次从现金中扣除价格影响。"""

        return self.economic_cost


def quantize_money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def calculate_trade_cost(
    side: OrderSide,
    price: Decimal,
    quantity: int,
    settings: TradingCostSettings | None = None,
    reference_price: Decimal | None = None,
) -> TradeCostBreakdown:
    if quantity <= 0:
        raise ValueError("成交数量必须大于0")
    if price <= Decimal("0"):
        raise ValueError("成交价格必须大于0")

    config = settings or TradingCostSettings()
    reference = reference_price or price
    if reference <= Decimal("0"):
        raise ValueError("参考价格必须大于0")
    reference_notional = quantize_money(reference * Decimal(quantity))
    notional = quantize_money(price * Decimal(quantity))
    commission = max(quantize_money(notional * config.commission_rate), config.min_commission)
    stamp_tax = (
        quantize_money(notional * config.stamp_tax_rate) if side is OrderSide.SELL else Decimal("0")
    )
    transfer_fee = quantize_money(notional * config.transfer_fee_rate)
    realized_price_impact = abs(notional - reference_notional)
    total_adjustment_bps = config.slippage_bps + config.market_impact_bps
    if realized_price_impact and total_adjustment_bps:
        slippage = quantize_money(
            realized_price_impact * config.slippage_bps / total_adjustment_bps
        )
        market_impact = realized_price_impact - slippage
    else:
        slippage = Decimal("0")
        market_impact = Decimal("0")
    return TradeCostBreakdown(
        reference_notional=reference_notional,
        notional=notional,
        commission=commission,
        stamp_tax=stamp_tax,
        transfer_fee=transfer_fee,
        slippage=slippage,
        market_impact=market_impact,
    )


def execution_price_with_adjustments(
    side: OrderSide,
    last_price: Decimal,
    settings: TradingCostSettings | None = None,
) -> Decimal:
    config = settings or TradingCostSettings()
    factor = (config.slippage_bps + config.market_impact_bps) / BPS_DIVISOR
    if side is OrderSide.BUY:
        return quantize_money(last_price * (Decimal("1") + factor))
    return quantize_money(last_price * (Decimal("1") - factor))


def execution_price_with_slippage(
    side: OrderSide,
    last_price: Decimal,
    settings: TradingCostSettings | None = None,
) -> Decimal:
    """兼容旧 API；返回统一包含滑点和市场冲击的成交价格。"""

    return execution_price_with_adjustments(side, last_price, settings)
