import unittest
from datetime import datetime
from decimal import Decimal

from app.config import APP_TIME_ZONE
from app.execution import (
    calculate_price_limits,
    get_market_phase,
    identify_security,
    is_t_plus_one_sell_allowed,
    is_valid_buy_quantity,
    is_valid_sell_quantity,
)


class TradingRulesTests(unittest.TestCase):
    def test_identify_security_exchange_and_board(self) -> None:
        self.assertEqual(identify_security("600519").symbol, "600519.SH")
        self.assertEqual(identify_security("000001").symbol, "000001.SZ")
        self.assertEqual(identify_security("300750.SZ").board, "创业板")
        self.assertEqual(identify_security("688001.SH").board, "科创板")

    def test_buy_quantity_must_be_lot_size(self) -> None:
        self.assertTrue(is_valid_buy_quantity(100))
        self.assertTrue(is_valid_buy_quantity(300))
        self.assertFalse(is_valid_buy_quantity(150))
        self.assertFalse(is_valid_buy_quantity(0))

    def test_sell_quantity_allows_odd_lot_tail(self) -> None:
        self.assertTrue(is_valid_sell_quantity(37))
        self.assertFalse(is_valid_sell_quantity(0))

    def test_t_plus_one_rule(self) -> None:
        buy_date = datetime(2030, 8, 6).date()
        self.assertFalse(is_t_plus_one_sell_allowed(buy_date, datetime(2030, 8, 6).date()))
        self.assertTrue(is_t_plus_one_sell_allowed(buy_date, datetime(2030, 8, 7).date()))

    def test_market_phase_uses_explicit_trading_day(self) -> None:
        self.assertEqual(
            get_market_phase(datetime(2030, 8, 6, 9, 20, tzinfo=APP_TIME_ZONE), True), "集合竞价"
        )
        self.assertEqual(
            get_market_phase(datetime(2030, 8, 6, 12, 0, tzinfo=APP_TIME_ZONE), True), "午间休市"
        )
        self.assertEqual(
            get_market_phase(datetime(2026, 7, 26, 10, 0, tzinfo=APP_TIME_ZONE), False), "非交易日"
        )

    def test_price_limit_rules(self) -> None:
        main_board = calculate_price_limits(Decimal("10"), "主板")
        self.assertEqual(main_board.limit_up, Decimal("11.00"))
        self.assertEqual(main_board.limit_down, Decimal("9.00"))

        growth_board = calculate_price_limits(Decimal("10"), "创业板")
        self.assertEqual(growth_board.limit_up, Decimal("12.00"))

        st_rule = calculate_price_limits(Decimal("10"), "主板", is_st=True)
        self.assertEqual(st_rule.limit_up, Decimal("10.50"))

        new_stock = calculate_price_limits(Decimal("10"), "主板", listing_days=10)
        self.assertTrue(new_stock.uncertain)


if __name__ == "__main__":
    unittest.main()
