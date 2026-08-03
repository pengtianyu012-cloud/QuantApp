import unittest
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.config import APP_TIME_ZONE, RuntimeMode
from app.data.providers import (
    Bar,
    Instrument,
    MarketDataProvider,
    MockMarketDataProvider,
    OrderBook,
    ProviderHealth,
    Quote,
    TradingDay,
)
from app.models import OrderSide
from app.services import TradingAppService
from app.utils import FrozenClock


class RecordingResearchProvider(MarketDataProvider):
    name = "测试研究行情"

    def __init__(self) -> None:
        self.daily_requests: list[tuple[str, date, date]] = []

    def get_stock_list(self) -> list[Instrument]:
        return []

    def get_latest_quotes(self, symbols: list[str]) -> list[Quote]:
        return []

    def get_order_book(self, symbol: str) -> OrderBook:
        raise AssertionError("本测试不应请求盘口")

    def get_intraday_bars(self, symbol: str, interval: str) -> list[Bar]:
        return []

    def get_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[Bar]:
        self.daily_requests.append((symbol, start_date, end_date))
        return []

    def get_trading_calendar(self, start_date: date, end_date: date) -> list[TradingDay]:
        return []

    def get_financial_indicators(
        self, symbols: list[str], report_date: date
    ) -> dict[str, dict[str, Any]]:
        return {}

    def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            ok=True,
            message="ok",
            checked_at=datetime(2030, 8, 5, 15, 0, tzinfo=APP_TIME_ZONE),
        )


class RuntimeModeTests(unittest.TestCase):
    def test_research_and_paper_modes_reject_mock_provider(self) -> None:
        for mode in (RuntimeMode.RESEARCH, RuntimeMode.PAPER):
            with self.subTest(mode=mode):
                with self.assertRaisesRegex(ValueError, "禁止使用 Mock"):
                    TradingAppService(
                        mode=mode,
                        market_data=MockMarketDataProvider(),
                        persist_account=False,
                    )

    def test_research_mode_strategy_and_backtest_keep_configured_provider(self) -> None:
        provider = RecordingResearchProvider()
        clock = FrozenClock(datetime(2030, 8, 5, 15, 30, tzinfo=APP_TIME_ZONE))
        service = TradingAppService(
            mode=RuntimeMode.RESEARCH,
            market_data=provider,
            persist_account=False,
            clock=clock,
        )

        self.assertIs(service.strategy_service.market_data, provider)
        result = service.run_demo_backtest()

        self.assertEqual(result.end_date, clock.today())
        self.assertEqual(provider.daily_requests[-1][2], clock.today())
        self.assertEqual(provider.daily_requests[-1][1], date(2025, 8, 5))

    def test_research_mode_disables_manual_orders(self) -> None:
        service = TradingAppService(
            mode=RuntimeMode.RESEARCH,
            market_data=RecordingResearchProvider(),
            persist_account=False,
        )

        result = service.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            100,
            Decimal("10"),
        )

        self.assertFalse(result.ok)
        self.assertIn("research", result.message)


if __name__ == "__main__":
    unittest.main()
