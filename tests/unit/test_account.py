import unittest
from datetime import datetime
from decimal import Decimal

from app.execution import calculate_trade_cost, execution_price_with_adjustments
from app.models import OrderSide
from app.portfolio import AccountError, SimulatedAccount


class SimulatedAccountTests(unittest.TestCase):
    def test_buy_reduces_cash_and_position_is_not_sellable_same_day(self) -> None:
        account = SimulatedAccount()
        submitted_at = datetime(2026, 7, 27, 9, 30)
        order = account.submit_order("600519.SH", OrderSide.BUY, 100, submitted_at)

        account.apply_fill(order, Decimal("100"), 100, submitted_at, stock_name="贵州茅台")

        self.assertLess(account.cash, Decimal("100000"))
        self.assertEqual(account.positions["600519.SH"].quantity, 100)
        self.assertEqual(account.positions["600519.SH"].available_quantity, 0)

    def test_t_plus_one_blocks_same_day_sell_and_allows_next_day(self) -> None:
        account = SimulatedAccount()
        buy_time = datetime(2026, 7, 27, 9, 30)
        buy_order = account.submit_order("600519.SH", OrderSide.BUY, 100, buy_time)
        account.apply_fill(buy_order, Decimal("100"), 100, buy_time, stock_name="贵州茅台")

        sell_order = account.submit_order("600519.SH", OrderSide.SELL, 100, buy_time)
        with self.assertRaises(AccountError):
            account.apply_fill(sell_order, Decimal("101"), 100, buy_time)

        account.advance_trading_day()
        sell_time = datetime(2026, 7, 28, 9, 30)
        next_sell_order = account.submit_order("600519.SH", OrderSide.SELL, 100, sell_time)
        account.apply_fill(next_sell_order, Decimal("101"), 100, sell_time)

        self.assertNotIn("600519.SH", account.positions)
        self.assertGreater(account.cash, Decimal("99900"))

    def test_total_assets_uses_latest_prices(self) -> None:
        account = SimulatedAccount()
        buy_time = datetime(2026, 7, 27, 9, 30)
        order = account.submit_order("000001.SZ", OrderSide.BUY, 1000, buy_time)
        account.apply_fill(order, Decimal("10"), 1000, buy_time, stock_name="平安银行")

        total_assets = account.total_assets({"000001.SZ": Decimal("11")})

        self.assertGreater(total_assets, Decimal("100000"))

    def test_execution_costs_are_recorded_once_and_reconcile(self) -> None:
        account = SimulatedAccount()
        trade_time = datetime(2030, 8, 6, 9, 30)
        reference_price = Decimal("10.00")
        execution_price = execution_price_with_adjustments(
            OrderSide.BUY,
            reference_price,
        )
        order = account.submit_order("000001.SZ", OrderSide.BUY, 100, trade_time)

        fill = account.apply_fill(
            order,
            execution_price,
            100,
            trade_time,
            reference_price=reference_price,
        )
        costs = calculate_trade_cost(
            OrderSide.BUY,
            execution_price,
            100,
            reference_price=reference_price,
        )

        self.assertEqual(
            account.cash,
            account.initial_cash - costs.notional - costs.cash_fees,
        )
        self.assertEqual(
            account.total_assets({"000001.SZ": reference_price}),
            account.initial_cash - costs.economic_cost,
        )
        self.assertEqual(account.cumulative_fees, costs.economic_cost)
        self.assertEqual(fill.commission, costs.commission)
        self.assertEqual(fill.tax, costs.stamp_tax)
        self.assertEqual(fill.transfer_fee, costs.transfer_fee)
        self.assertEqual(fill.slippage, costs.slippage)
        self.assertEqual(fill.market_impact, costs.market_impact)

    def test_daily_snapshots_track_peak_current_and_max_drawdown(self) -> None:
        account = SimulatedAccount()

        first = account.record_snapshot(datetime(2030, 8, 6, 15, 0), {})
        account.cash = Decimal("85000")
        trough = account.record_snapshot(datetime(2030, 8, 7, 15, 0), {})
        account.cash = Decimal("90000")
        recovery = account.record_snapshot(datetime(2030, 8, 8, 15, 0), {})

        self.assertEqual(first.net_value, Decimal("1.000000"))
        self.assertEqual(trough.current_drawdown, Decimal("0.150000"))
        self.assertEqual(recovery.current_drawdown, Decimal("0.100000"))
        self.assertEqual(recovery.max_drawdown, Decimal("0.150000"))
        self.assertEqual(account.peak_total_assets, Decimal("100000"))


if __name__ == "__main__":
    unittest.main()
