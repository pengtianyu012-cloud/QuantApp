import unittest
from decimal import Decimal

from app.execution import calculate_trade_cost, execution_price_with_slippage
from app.models import OrderSide


class TradeCostTests(unittest.TestCase):
    def test_buy_cost_uses_min_commission_and_no_stamp_tax(self) -> None:
        costs = calculate_trade_cost(OrderSide.BUY, Decimal("10"), 100)

        self.assertEqual(costs.notional, Decimal("1000.00"))
        self.assertEqual(costs.commission, Decimal("5"))
        self.assertEqual(costs.stamp_tax, Decimal("0"))
        self.assertGreater(costs.total, Decimal("5"))

    def test_sell_cost_has_stamp_tax(self) -> None:
        costs = calculate_trade_cost(OrderSide.SELL, Decimal("20"), 1000)

        self.assertGreater(costs.stamp_tax, Decimal("0"))
        self.assertGreater(costs.total, costs.commission)

    def test_execution_price_applies_slippage_directionally(self) -> None:
        buy_price = execution_price_with_slippage(OrderSide.BUY, Decimal("100"))
        sell_price = execution_price_with_slippage(OrderSide.SELL, Decimal("100"))

        self.assertGreater(buy_price, Decimal("100"))
        self.assertLess(sell_price, Decimal("100"))


if __name__ == "__main__":
    unittest.main()
