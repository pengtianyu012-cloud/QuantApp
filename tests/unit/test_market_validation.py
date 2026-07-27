import unittest
from dataclasses import replace
from decimal import Decimal

from app.data.providers import MockMarketDataProvider
from app.data.validators import validate_quote


class MarketValidationTests(unittest.TestCase):
    def test_quote_price_must_be_positive(self) -> None:
        provider = MockMarketDataProvider()
        quote = provider.get_latest_quotes(["600519.SH"])[0]
        invalid_quote = replace(quote, last_price=Decimal("0"))

        result = validate_quote(invalid_quote)

        self.assertFalse(result.ok)
        self.assertEqual(result.issues[0].field, "last_price")

    def test_quote_time_must_be_timezone_aware(self) -> None:
        provider = MockMarketDataProvider()
        quote = provider.get_latest_quotes(["600519.SH"])[0]
        invalid_quote = replace(quote, quote_time=quote.quote_time.replace(tzinfo=None))

        result = validate_quote(invalid_quote)

        self.assertFalse(result.ok)
        self.assertTrue(any(issue.field == "quote_time" for issue in result.issues))


if __name__ == "__main__":
    unittest.main()
