import unittest
from datetime import date, datetime, timedelta
from decimal import Decimal

import pandas as pd

from app.config import APP_TIME_ZONE, RefreshSettings
from app.data.providers import AkSharePublicMarketDataProvider, MarketDataError


class FakeHttpClient:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls = 0

    def get_bytes(self, url: str, headers=None) -> bytes:
        self.calls += 1
        return self.payload


class FakeAkShare:
    def __init__(self) -> None:
        today = datetime.now(APP_TIME_ZONE).date()
        self.sh_main = pd.DataFrame(
            [
                {
                    "证券代码": "600519",
                    "证券简称": "贵州茅台",
                    "上市日期": date(2001, 8, 27),
                },
                {
                    "证券代码": "600001",
                    "证券简称": "ST测试",
                    "上市日期": date(1990, 1, 1),
                },
            ]
        )
        self.sh_star = pd.DataFrame(
            [
                {
                    "证券代码": "688001",
                    "证券简称": "华兴源创",
                    "上市日期": date(2019, 7, 22),
                }
            ]
        )
        self.sz = pd.DataFrame(
            [
                {
                    "A股代码": "000001",
                    "A股简称": "平安银行",
                    "A股上市日期": "1991-04-03",
                    "所属行业": "J 金融业",
                },
                {
                    "A股代码": "301999",
                    "A股简称": "近期上市",
                    "A股上市日期": (today - timedelta(days=10)).isoformat(),
                    "所属行业": "C 制造业",
                },
            ]
        )

    def stock_info_sh_name_code(self, symbol: str):
        return self.sh_main if symbol == "主板A股" else self.sh_star

    def stock_info_sz_name_code(self, symbol: str):
        return self.sz

    def stock_zh_a_hist(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "日期": date(2026, 7, 27),
                    "开盘": 1308.0,
                    "收盘": 1289.5,
                    "最高": 1308.0,
                    "最低": 1279.58,
                    "成交量": 31990,
                    "成交额": 4129228560,
                }
            ]
        )

    def tool_trade_date_hist_sina(self):
        return pd.DataFrame([{"trade_date": date(2026, 7, 27)}, {"trade_date": date(2026, 7, 29)}])


class FallbackDailyAkShare(FakeAkShare):
    def stock_zh_a_hist(self, **kwargs):
        raise ConnectionError("primary unavailable")

    def stock_zh_a_daily(self, **kwargs):
        return pd.DataFrame(
            [
                {
                    "date": date(2026, 7, 27),
                    "open": 1308.0,
                    "close": 1289.5,
                    "high": 1308.0,
                    "low": 1279.58,
                    "volume": 3_199_044,
                    "amount": 4_129_228_560,
                }
            ]
        )


def tencent_payload() -> bytes:
    fields = [""] * 39
    values = {
        0: "1",
        1: "贵州茅台",
        2: "600519",
        3: "1289.50",
        4: "1297.41",
        5: "1308.00",
        6: "31990",
        7: "16204",
        8: "15786",
        9: "1289.50",
        10: "21",
        11: "1289.49",
        12: "1",
        13: "1289.48",
        14: "17",
        15: "1289.46",
        16: "1",
        17: "1289.45",
        18: "7",
        19: "1289.66",
        20: "1",
        21: "1289.95",
        22: "1",
        23: "1290.00",
        24: "12",
        25: "1290.01",
        26: "1",
        27: "1290.49",
        28: "1",
        30: "20260727161456",
        31: "-7.91",
        32: "-0.61",
        33: "1308.00",
        34: "1279.58",
        35: "1289.50/31990/4129228560",
        38: "0.26",
    }
    for index, value in values.items():
        fields[index] = value
    return f'v_sh600519="{"~".join(fields)}";\n'.encode("gbk")


class AkSharePublicMarketDataProviderTests(unittest.TestCase):
    def create_provider(self, payload: bytes | None = None):
        return AkSharePublicMarketDataProvider(
            settings=RefreshSettings(max_retries=1),
            http_client=FakeHttpClient(payload or tencent_payload()),
            akshare_module=FakeAkShare(),
            now_provider=lambda: datetime(2026, 7, 27, 16, 15, tzinfo=APP_TIME_ZONE),
            sleeper=lambda _: None,
            monotonic=lambda: 1.0,
        )

    def test_tencent_quote_and_five_level_book_use_documented_units(self) -> None:
        provider = self.create_provider()

        quote = provider.get_latest_quotes(["600519.SH"])[0]
        order_book = provider.get_order_book("600519.SH")

        self.assertEqual(quote.last_price, Decimal("1289.50"))
        self.assertEqual(quote.pct_change, Decimal("-0.0061"))
        self.assertEqual(quote.volume, 3_199_000)
        self.assertEqual(quote.amount, Decimal("4129228560"))
        self.assertEqual(quote.turnover_rate, Decimal("0.0026"))
        self.assertEqual(order_book.bids[0].quantity, 2_100)
        self.assertEqual(order_book.asks[2].price, Decimal("1290.00"))
        self.assertEqual(order_book.inner_volume, 1_578_600)
        self.assertEqual(order_book.outer_volume, 1_620_400)
        self.assertIn("commission_ratio", order_book.unsupported_fields)
        self.assertEqual(provider.http_client.calls, 1)

    def test_invalid_html_response_is_rejected_instead_of_fabricated(self) -> None:
        provider = self.create_provider(b"<html>blocked</html>")

        with self.assertRaises(MarketDataError):
            provider.get_latest_quotes(["600519.SH"])

    def test_exchange_lists_cover_boards_and_apply_stock_filters(self) -> None:
        provider = self.create_provider()

        instruments = provider.get_stock_list()
        by_symbol = {instrument.symbol: instrument for instrument in instruments}

        self.assertEqual(len(instruments), 5)
        self.assertEqual(by_symbol["688001.SH"].board, "科创板")
        self.assertEqual(by_symbol["000001.SZ"].industry, "J 金融业")
        self.assertFalse(by_symbol["600001.SH"].eligible)
        self.assertFalse(by_symbol["301999.SZ"].eligible)

    def test_daily_bars_and_calendar_are_normalized(self) -> None:
        provider = self.create_provider()

        bars = provider.get_daily_bars("600519.SH", date(2026, 7, 27), date(2026, 7, 27))
        calendar = provider.get_trading_calendar(date(2026, 7, 27), date(2026, 7, 29))

        self.assertEqual(bars[0].volume, 3_199_000)
        self.assertEqual(bars[0].bar_time.tzinfo, APP_TIME_ZONE)
        self.assertEqual([day.is_open for day in calendar], [True, False, True])

    def test_daily_bars_fall_back_to_sina_without_rescaling_share_volume(self) -> None:
        provider = AkSharePublicMarketDataProvider(
            settings=RefreshSettings(max_retries=1),
            http_client=FakeHttpClient(tencent_payload()),
            akshare_module=FallbackDailyAkShare(),
            sleeper=lambda _: None,
            monotonic=lambda: 1.0,
        )

        bars = provider.get_daily_bars("600519.SH", date(2026, 7, 27), date(2026, 7, 27))

        self.assertEqual(bars[0].volume, 3_199_044)
        self.assertIn("新浪备用", bars[0].source)


if __name__ == "__main__":
    unittest.main()
