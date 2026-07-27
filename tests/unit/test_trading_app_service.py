import unittest
from datetime import datetime
from decimal import Decimal

from app.config import APP_TIME_ZONE
from app.models import OrderSide, OrderStatus
from app.services import TradingAppService


class TradingAppServiceTests(unittest.TestCase):
    def test_manual_buy_updates_account_position_order_and_fill(self) -> None:
        service = TradingAppService(persist_account=False)

        result = service.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            100,
            Decimal("10.80"),
            datetime(2026, 7, 27, 9, 30, tzinfo=APP_TIME_ZONE),
        )

        self.assertTrue(result.ok)
        self.assertIsNotNone(result.order)
        self.assertIsNotNone(result.fill)
        self.assertIn("000001.SZ", service.account.positions)
        self.assertEqual(service.account.orders[-1].status, OrderStatus.FILLED)
        self.assertEqual(len(service.account.fills), 1)

    def test_risk_rejects_oversized_single_position_before_order_creation(self) -> None:
        service = TradingAppService(persist_account=False)

        result = service.place_manual_order(
            OrderSide.BUY,
            "600519.SH",
            100,
            Decimal("1688.00"),
            datetime(2026, 7, 27, 9, 30, tzinfo=APP_TIME_ZONE),
        )

        self.assertFalse(result.ok)
        self.assertIsNone(result.order)
        self.assertIn("单股", result.message)
        self.assertEqual(len(service.account.orders), 0)

    def test_invalid_buy_lot_is_rejected(self) -> None:
        service = TradingAppService(persist_account=False)

        result = service.place_manual_order(
            OrderSide.BUY,
            "000001.SZ",
            150,
            Decimal("10.80"),
            datetime(2026, 7, 27, 9, 30, tzinfo=APP_TIME_ZONE),
        )

        self.assertFalse(result.ok)
        self.assertIn("100股整数倍", result.message)


if __name__ == "__main__":
    unittest.main()
