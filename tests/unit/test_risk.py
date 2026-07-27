import unittest
from datetime import datetime
from decimal import Decimal

from app.models import OrderSide
from app.portfolio import SimulatedAccount
from app.risk import RiskManager


class RiskManagerTests(unittest.TestCase):
    def test_single_position_limit_blocks_buy(self) -> None:
        account = SimulatedAccount()
        manager = RiskManager()

        result = manager.check_order(
            OrderSide.BUY,
            account,
            "600519.SH",
            Decimal("40000"),
            {},
        )

        self.assertFalse(result.passed)
        self.assertIn("单股", result.message)

    def test_total_position_limit_blocks_buy(self) -> None:
        account = SimulatedAccount(cash=Decimal("100000"))
        buy_time = datetime(2026, 7, 27, 9, 30)
        order = account.submit_order("000001.SZ", OrderSide.BUY, 4000, buy_time)
        account.apply_fill(order, Decimal("20"), 4000, buy_time, stock_name="平安银行")
        manager = RiskManager()

        result = manager.check_order(
            OrderSide.BUY,
            account,
            "300750.SZ",
            Decimal("15000"),
            {"000001.SZ": Decimal("20")},
        )

        self.assertFalse(result.passed)
        self.assertIn("总仓位", result.message)

    def test_drawdown_blocks_new_buy_but_not_sell(self) -> None:
        account = SimulatedAccount()
        manager = RiskManager()

        buy_result = manager.check_order(
            OrderSide.BUY,
            account,
            "600519.SH",
            Decimal("10000"),
            {},
            current_drawdown=Decimal("0.15"),
        )
        sell_result = manager.check_order(
            OrderSide.SELL,
            account,
            "600519.SH",
            Decimal("10000"),
            {},
            current_drawdown=Decimal("0.20"),
        )

        self.assertFalse(buy_result.passed)
        self.assertTrue(sell_result.passed)


if __name__ == "__main__":
    unittest.main()
