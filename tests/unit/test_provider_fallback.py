import unittest

from app.data.providers import FallbackMarketDataProvider, MarketDataError, MockMarketDataProvider


class ProviderFallbackTests(unittest.TestCase):
    def test_fallback_uses_secondary_provider_when_primary_fails(self) -> None:
        primary = MockMarketDataProvider(fail=True)
        secondary = MockMarketDataProvider()
        provider = FallbackMarketDataProvider([primary, secondary])

        quotes = provider.get_latest_quotes(["600519.SH"])

        self.assertEqual(len(quotes), 1)
        self.assertEqual(provider.last_provider_name, secondary.name)

    def test_fallback_raises_when_all_providers_fail(self) -> None:
        provider = FallbackMarketDataProvider(
            [
                MockMarketDataProvider(fail=True),
                MockMarketDataProvider(fail=True),
            ]
        )

        with self.assertRaises(MarketDataError) as context:
            provider.get_stock_list()

        self.assertIn("所有行情数据源均失败", str(context.exception))
        self.assertIn("Mock数据源被设置为失败", provider.last_error or "")


if __name__ == "__main__":
    unittest.main()
