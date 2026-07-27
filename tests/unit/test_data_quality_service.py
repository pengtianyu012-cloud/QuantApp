import unittest
from dataclasses import replace
from decimal import Decimal

from app.data.providers import MockMarketDataProvider
from app.services import DataQualityService


class DataQualityServiceTests(unittest.TestCase):
    def test_mock_data_quality_reports_pass(self) -> None:
        service = DataQualityService(MockMarketDataProvider())

        reports = service.run_all_checks()

        self.assertGreaterEqual(len(reports), 3)
        self.assertTrue(all(report.ok for report in reports))

    def test_invalid_quote_report_fails(self) -> None:
        provider = MockMarketDataProvider()
        quote = provider.get_latest_quotes(["000001.SZ"])[0]
        invalid = replace(quote, last_price=Decimal("0"))
        service = DataQualityService(provider)

        report = service.check_quotes([invalid])

        self.assertFalse(report.ok)
        self.assertIn("last_price", report.missing_fields)


if __name__ == "__main__":
    unittest.main()
