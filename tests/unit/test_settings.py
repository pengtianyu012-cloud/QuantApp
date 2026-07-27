import unittest
from decimal import Decimal

from app.config import DISCLAIMER, TradingCostSettings, TradingRules, default_runtime_paths


class SettingsTests(unittest.TestCase):
    def test_trading_rules_defaults(self) -> None:
        rules = TradingRules()

        self.assertEqual(rules.initial_cash, Decimal("100000"))
        self.assertEqual(rules.max_single_position_pct, Decimal("0.30"))
        self.assertEqual(rules.max_total_position_pct, Decimal("0.90"))
        self.assertEqual(rules.max_drawdown_pct, Decimal("0.15"))
        self.assertEqual(rules.buy_lot_size, 100)
        self.assertEqual(rules.benchmark, "沪深300")

    def test_cost_settings_are_centralized(self) -> None:
        costs = TradingCostSettings()

        self.assertGreater(costs.commission_rate, Decimal("0"))
        self.assertEqual(costs.min_commission, Decimal("5"))
        self.assertLessEqual(costs.max_volume_participation, Decimal("1"))

    def test_disclaimer_is_explicit(self) -> None:
        self.assertIn("不连接真实券商", DISCLAIMER)
        self.assertIn("不执行真实订单", DISCLAIMER)

    def test_runtime_paths_are_inside_project(self) -> None:
        paths = default_runtime_paths()

        self.assertEqual(paths.data_dir.name, "data")
        self.assertEqual(paths.logs_dir.name, "logs")
        self.assertIn(paths.project_root, paths.data_dir.parents)


if __name__ == "__main__":
    unittest.main()
