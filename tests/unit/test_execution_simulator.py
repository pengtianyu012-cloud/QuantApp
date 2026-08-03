import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from decimal import Decimal

from app.config import APP_TIME_ZONE
from app.data.providers import MockMarketDataProvider
from app.execution import (
    InvalidOrderTransition,
    OrderStateMachine,
    ProviderTradingCalendar,
    SimulatedMatcher,
    calculate_price_limits,
)
from app.models import Order, OrderSide, OrderStatus, OrderType
from app.portfolio import SimulatedAccount
from app.utils import FrozenClock


class ExecutionSimulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2030, 8, 6, 9, 30, tzinfo=APP_TIME_ZONE)
        self.clock = FrozenClock(self.now)
        self.provider = MockMarketDataProvider(clock=self.clock)
        self.instrument = self.provider.get_stock_list()[1]
        self.quote = self.provider.get_latest_quotes([self.instrument.symbol])[0]
        self.matcher = SimulatedMatcher(ProviderTradingCalendar(self.provider))

    def order(
        self,
        *,
        side: OrderSide = OrderSide.BUY,
        order_type: OrderType = OrderType.MARKET,
        quantity: int = 100,
        limit_price: Decimal | None = None,
        status: OrderStatus = OrderStatus.ELIGIBLE,
    ) -> Order:
        return Order(
            order_id="O-TEST",
            account_id="SIM-001",
            symbol=self.instrument.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            submitted_at=self.now - timedelta(days=1),
            limit_price=limit_price,
            status=status,
            eligible_at=self.now if order_type is OrderType.NEXT_OPEN else None,
        )

    def test_next_open_order_never_fills_on_submission_day(self) -> None:
        order = self.order(
            order_type=OrderType.NEXT_OPEN,
            status=OrderStatus.PENDING_NEXT_OPEN,
        )
        same_day = order.submitted_at.replace(hour=14)

        pending = self.matcher.evaluate(
            order, self.quote, self.instrument, same_day, interval_volume=10_000
        )
        eligible = self.matcher.evaluate(
            order, self.quote, self.instrument, self.now, interval_volume=10_000
        )

        self.assertEqual(pending.status, OrderStatus.PENDING_NEXT_OPEN)
        self.assertEqual(pending.fill_quantity, 0)
        self.assertEqual(eligible.status, OrderStatus.FILLED)

    def test_limit_buy_and_sell_conditions_are_directional(self) -> None:
        buy_waits = self.matcher.evaluate(
            self.order(order_type=OrderType.LIMIT, limit_price=Decimal("10.79")),
            self.quote,
            self.instrument,
            self.now,
        )
        buy_fills = self.matcher.evaluate(
            self.order(order_type=OrderType.LIMIT, limit_price=Decimal("10.81")),
            self.quote,
            self.instrument,
            self.now,
        )
        sell_waits = self.matcher.evaluate(
            self.order(
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                limit_price=Decimal("10.81"),
            ),
            self.quote,
            self.instrument,
            self.now,
        )
        sell_fills = self.matcher.evaluate(
            self.order(
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                limit_price=Decimal("10.79"),
            ),
            self.quote,
            self.instrument,
            self.now,
        )

        self.assertEqual(buy_waits.status, OrderStatus.DEFERRED)
        self.assertEqual(buy_fills.status, OrderStatus.FILLED)
        self.assertEqual(sell_waits.status, OrderStatus.DEFERRED)
        self.assertEqual(sell_fills.status, OrderStatus.FILLED)

    def test_current_time_change_makes_quote_stale(self) -> None:
        fresh = self.matcher.evaluate(
            self.order(), self.quote, self.instrument, self.now, interval_volume=10_000
        )
        stale = self.matcher.evaluate(
            self.order(),
            self.quote,
            self.instrument,
            self.now + timedelta(seconds=31),
            interval_volume=10_000,
        )

        self.assertEqual(fresh.status, OrderStatus.FILLED)
        self.assertEqual(stale.status, OrderStatus.DEFERRED)
        self.assertIn("过期", stale.reason)

    def test_partial_fill_tracks_remaining_and_can_continue(self) -> None:
        account = SimulatedAccount()
        order = account.submit_order(
            self.instrument.symbol,
            OrderSide.BUY,
            1_000,
            self.now,
            order_type=OrderType.MARKET,
        )

        first = self.matcher.evaluate(
            order, self.quote, self.instrument, self.now, interval_volume=3_000
        )
        account.apply_fill(
            order,
            first.fill_price or self.quote.last_price,
            first.fill_quantity,
            self.now,
            reason=first.reason,
        )
        remaining = account.get_order(order.order_id)
        second = self.matcher.evaluate(
            remaining,
            self.quote,
            self.instrument,
            self.now,
            interval_volume=7_000,
        )
        account.apply_fill(
            remaining,
            second.fill_price or self.quote.last_price,
            second.fill_quantity,
            self.now,
            reason=second.reason,
        )
        completed = account.get_order(order.order_id)

        self.assertEqual(first.status, OrderStatus.PARTIALLY_FILLED)
        self.assertEqual(remaining.filled_quantity, 300)
        self.assertEqual(remaining.remaining_quantity, 700)
        self.assertEqual(second.status, OrderStatus.FILLED)
        self.assertEqual(completed.filled_quantity, 1_000)
        self.assertEqual(completed.remaining_quantity, 0)

    def test_st_suspended_delisting_and_delisted_stocks_cannot_fill(self) -> None:
        st = self.matcher.evaluate(
            self.order(),
            self.quote,
            replace(self.instrument, is_st=True),
            self.now,
        )
        suspended = self.matcher.evaluate(
            self.order(),
            self.quote,
            replace(self.instrument, is_suspended=True),
            self.now,
        )
        delisted = self.matcher.evaluate(
            self.order(),
            self.quote,
            replace(self.instrument, is_delisted=True),
            self.now,
        )
        delisting = self.matcher.evaluate(
            self.order(),
            self.quote,
            replace(self.instrument, is_delisting=True),
            self.now,
        )

        self.assertEqual(st.status, OrderStatus.REJECTED)
        self.assertEqual(suspended.status, OrderStatus.DEFERRED)
        self.assertEqual(delisted.status, OrderStatus.REJECTED)
        self.assertEqual(delisting.status, OrderStatus.REJECTED)

    def test_stock_listed_for_less_than_60_days_is_rejected(self) -> None:
        result = self.matcher.evaluate(
            self.order(),
            self.quote,
            self.instrument,
            self.now,
            listing_days=59,
        )

        self.assertEqual(result.status, OrderStatus.REJECTED)

    def test_limit_up_blocks_buy_and_limit_down_blocks_sell(self) -> None:
        limits = calculate_price_limits(self.quote.prev_close, self.instrument.board)
        limit_up_quote = replace(self.quote, last_price=limits.limit_up)
        limit_down_quote = replace(self.quote, last_price=limits.limit_down)

        buy = self.matcher.evaluate(
            self.order(), limit_up_quote, self.instrument, self.now
        )
        sell = self.matcher.evaluate(
            self.order(side=OrderSide.SELL),
            limit_down_quote,
            self.instrument,
            self.now,
        )

        self.assertEqual(buy.status, OrderStatus.DEFERRED)
        self.assertEqual(sell.status, OrderStatus.DEFERRED)

    def test_non_trading_day_and_non_trading_session_defer(self) -> None:
        before_open = self.now.replace(hour=9, minute=0)
        saturday = self.now + timedelta(days=4)

        session_result = self.matcher.evaluate(
            self.order(), self.quote, self.instrument, before_open
        )
        calendar_result = self.matcher.evaluate(
            self.order(), self.quote, self.instrument, saturday
        )

        self.assertEqual(session_result.status, OrderStatus.DEFERRED)
        self.assertIn("连续竞价", session_result.reason)
        self.assertEqual(calendar_result.status, OrderStatus.DEFERRED)
        self.assertIn("交易日", calendar_result.reason)

    def test_missing_order_book_marks_degraded_model(self) -> None:
        result = self.matcher.evaluate(
            self.order(),
            self.quote,
            self.instrument,
            self.now,
            interval_volume=10_000,
            has_order_book=False,
        )

        self.assertTrue(result.degraded_model)

    def test_terminal_order_cannot_be_reactivated(self) -> None:
        filled = replace(
            self.order(),
            status=OrderStatus.FILLED,
            filled_quantity=100,
            remaining_quantity=0,
        )

        with self.assertRaises(InvalidOrderTransition):
            OrderStateMachine.transition(
                filled, OrderStatus.ELIGIBLE, self.now, "错误重启"
            )


if __name__ == "__main__":
    unittest.main()
