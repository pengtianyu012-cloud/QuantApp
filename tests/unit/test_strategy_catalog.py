import unittest

from app.models import built_in_strategy_catalog


class StrategyCatalogTests(unittest.TestCase):
    def test_builtin_strategy_catalog_contains_four_strategies(self) -> None:
        strategies = built_in_strategy_catalog()
        names = {strategy.name for strategy in strategies}

        self.assertEqual(names, {"均线趋势", "动量选股", "低估值因子", "盘口与量价演示"})

    def test_unimplemented_strategies_are_marked(self) -> None:
        strategies = built_in_strategy_catalog()

        self.assertTrue(all(strategy.status == "尚未实现" for strategy in strategies))
        self.assertEqual({strategy.stage for strategy in strategies}, {"P1", "P2"})


if __name__ == "__main__":
    unittest.main()
