from __future__ import annotations

import queue
import threading
import time
from collections.abc import Callable
from datetime import date, datetime, timedelta
from datetime import time as datetime_time
from decimal import Decimal, InvalidOperation
from typing import Any, TypeVar

import akshare as akshare_library
import truststore

from app.config import APP_TIME_ZONE, RefreshSettings
from app.data.cache import TtlMemoryCache
from app.data.providers.base import (
    Bar,
    Instrument,
    MarketDataError,
    MarketDataProvider,
    OrderBook,
    OrderBookLevel,
    ProviderHealth,
    Quote,
    TradingDay,
)
from app.data.providers.http_client import HttpTransportError, RateLimitedHttpClient
from app.data.validators import validate_order_book, validate_quote
from app.execution.trading_rules import detect_board, identify_security

T = TypeVar("T")
TENCENT_QUOTE_URL = "https://qt.gtimg.cn/q="
TENCENT_HEADERS = {
    "Referer": "https://gu.qq.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) QuantApp/0.1",
}


class AkSharePublicMarketDataProvider(MarketDataProvider):
    """交易所主表、AkShare 历史数据与腾讯公开实时行情的研究适配器。"""

    name = "公开行情(AkShare/腾讯)"

    def __init__(
        self,
        settings: RefreshSettings | None = None,
        http_client: RateLimitedHttpClient | None = None,
        akshare_module: Any | None = None,
        now_provider: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings = settings or RefreshSettings()
        self.http_client = http_client or RateLimitedHttpClient(
            timeout_seconds=self.settings.request_timeout_seconds,
            max_retries=self.settings.max_retries,
        )
        self.akshare = akshare_module or akshare_library
        self.now_provider = now_provider or (lambda: datetime.now(APP_TIME_ZONE))
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.instrument_cache: TtlMemoryCache[list[Instrument]] = TtlMemoryCache(6 * 60 * 60)
        self.raw_quote_cache: TtlMemoryCache[dict[str, tuple[str, ...]]] = TtlMemoryCache(
            self.settings.watchlist_seconds
        )
        self.calendar_cache: TtlMemoryCache[set[date]] = TtlMemoryCache(6 * 60 * 60)
        self.daily_bar_cache: TtlMemoryCache[list[Bar]] = TtlMemoryCache(6 * 60 * 60)
        self._akshare_lock = threading.Lock()
        self._next_akshare_at = 0.0
        truststore.inject_into_ssl()

    def get_stock_list(self) -> list[Instrument]:
        cached = self.instrument_cache.get("all")
        if cached is not None:
            return cached

        sh_main = self._call_akshare(
            "上交所主板列表",
            lambda: self.akshare.stock_info_sh_name_code(symbol="主板A股"),
            timeout_seconds=30,
        )
        sh_star = self._call_akshare(
            "上交所科创板列表",
            lambda: self.akshare.stock_info_sh_name_code(symbol="科创板"),
            timeout_seconds=30,
        )
        sz_all = self._call_akshare(
            "深交所A股列表",
            lambda: self.akshare.stock_info_sz_name_code(symbol="A股列表"),
            timeout_seconds=30,
        )

        instruments: dict[str, Instrument] = {}
        for frame in (sh_main, sh_star):
            for row in frame.to_dict("records"):
                instrument = self._instrument_from_row(
                    code=row.get("证券代码"),
                    name=row.get("证券简称"),
                    listed_date=row.get("上市日期"),
                    exchange="SH",
                )
                instruments[instrument.symbol] = instrument
        for row in sz_all.to_dict("records"):
            instrument = self._instrument_from_row(
                code=row.get("A股代码"),
                name=row.get("A股简称"),
                listed_date=row.get("A股上市日期"),
                exchange="SZ",
                industry=self._optional_text(row.get("所属行业")),
            )
            instruments[instrument.symbol] = instrument
        if not instruments:
            raise MarketDataError("交易所股票列表为空")
        result = sorted(instruments.values(), key=lambda item: item.symbol)
        self.instrument_cache.set("all", result)
        return result

    def get_latest_quotes(self, symbols: list[str]) -> list[Quote]:
        if not symbols:
            return []
        raw_quotes = self._get_tencent_fields(symbols)
        quotes: list[Quote] = []
        for requested_symbol in symbols:
            symbol = identify_security(requested_symbol).symbol
            fields = raw_quotes.get(symbol)
            if fields is None:
                raise MarketDataError(f"腾讯行情未返回股票：{symbol}")
            quote = self._quote_from_fields(symbol, fields)
            validation = validate_quote(quote)
            if not validation.ok:
                details = ", ".join(issue.message for issue in validation.issues)
                raise MarketDataError(f"{symbol} 行情字段校验失败：{details}")
            quotes.append(quote)
        return quotes

    def get_order_book(self, symbol: str) -> OrderBook:
        normalized_symbol = identify_security(symbol).symbol
        fields = self._get_tencent_fields([normalized_symbol]).get(normalized_symbol)
        if fields is None:
            raise MarketDataError(f"腾讯盘口未返回股票：{normalized_symbol}")
        quote_time = self._parse_quote_time(fields[30])
        bids = tuple(
            self._order_book_level(fields, price_index, quantity_index)
            for price_index, quantity_index in ((9, 10), (11, 12), (13, 14), (15, 16), (17, 18))
        )
        asks = tuple(
            self._order_book_level(fields, price_index, quantity_index)
            for price_index, quantity_index in ((19, 20), (21, 22), (23, 24), (25, 26), (27, 28))
        )
        order_book = OrderBook(
            symbol=normalized_symbol,
            quote_time=quote_time,
            bids=bids,
            asks=asks,
            source=f"{self.name}/腾讯",
            inner_volume=self._lots_to_shares(fields[8]),
            outer_volume=self._lots_to_shares(fields[7]),
            commission_ratio=None,
            commission_diff=None,
            unsupported_fields=frozenset({"commission_ratio", "commission_diff"}),
        )
        validation = validate_order_book(order_book)
        if not validation.ok:
            details = ", ".join(issue.message for issue in validation.issues)
            raise MarketDataError(f"{normalized_symbol} 盘口字段校验失败：{details}")
        return order_book

    def get_intraday_bars(self, symbol: str, interval: str) -> list[Bar]:
        raise MarketDataError("AkShare 分时接口在当前网络尚未通过稳定性验证，真实源暂不提供分时线")

    def get_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[Bar]:
        identity = identify_security(symbol)
        cache_key = f"{identity.symbol}:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = self.daily_bar_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            frame = self._call_akshare(
                f"{identity.symbol}东财日线",
                lambda: self.akshare.stock_zh_a_hist(
                    symbol=identity.code,
                    period="daily",
                    start_date=start_date.strftime("%Y%m%d"),
                    end_date=end_date.strftime("%Y%m%d"),
                    adjust="",
                    timeout=self.settings.request_timeout_seconds,
                ),
            )
            bars = self._eastmoney_daily_bars(identity.symbol, frame)
        except MarketDataError as primary_error:
            try:
                frame = self._call_akshare(
                    f"{identity.symbol}新浪备用日线",
                    lambda: self.akshare.stock_zh_a_daily(
                        symbol=self._tencent_code(identity.symbol),
                        start_date=start_date.strftime("%Y%m%d"),
                        end_date=end_date.strftime("%Y%m%d"),
                        adjust="",
                    ),
                )
                bars = self._sina_daily_bars(identity.symbol, frame)
            except MarketDataError as fallback_error:
                raise MarketDataError(
                    f"{identity.symbol} 日线主备源均失败：{primary_error}; {fallback_error}"
                ) from fallback_error
        if not bars:
            raise MarketDataError(f"{identity.symbol} 在指定区间无日线数据")
        self.daily_bar_cache.set(cache_key, bars)
        return bars

    def _eastmoney_daily_bars(self, symbol: str, frame: Any) -> list[Bar]:
        bars: list[Bar] = []
        for row in frame.to_dict("records"):
            trade_date = self._date_value(row.get("日期"))
            bars.append(
                Bar(
                    symbol=symbol,
                    bar_time=datetime.combine(
                        trade_date, datetime_time(15, 0), tzinfo=APP_TIME_ZONE
                    ),
                    open_price=self._decimal(row.get("开盘"), "开盘"),
                    high_price=self._decimal(row.get("最高"), "最高"),
                    low_price=self._decimal(row.get("最低"), "最低"),
                    close_price=self._decimal(row.get("收盘"), "收盘"),
                    volume=self._lots_to_shares(row.get("成交量")),
                    amount=self._decimal(row.get("成交额"), "成交额"),
                    source=f"{self.name}/AkShare-东方财富",
                )
            )
        return bars

    def _sina_daily_bars(self, symbol: str, frame: Any) -> list[Bar]:
        bars: list[Bar] = []
        for row in frame.to_dict("records"):
            trade_date = self._date_value(row.get("date"))
            bars.append(
                Bar(
                    symbol=symbol,
                    bar_time=datetime.combine(
                        trade_date, datetime_time(15, 0), tzinfo=APP_TIME_ZONE
                    ),
                    open_price=self._decimal(row.get("open"), "open"),
                    high_price=self._decimal(row.get("high"), "high"),
                    low_price=self._decimal(row.get("low"), "low"),
                    close_price=self._decimal(row.get("close"), "close"),
                    volume=int(self._decimal(row.get("volume"), "volume")),
                    amount=self._decimal(row.get("amount"), "amount"),
                    source=f"{self.name}/AkShare-新浪备用",
                )
            )
        return bars

    def get_trading_calendar(self, start_date: date, end_date: date) -> list[TradingDay]:
        open_dates = self.calendar_cache.get("sina")
        if open_dates is None:
            frame = self._call_akshare("A股交易日历", self.akshare.tool_trade_date_hist_sina)
            open_dates = {
                self._date_value(row.get("trade_date")) for row in frame.to_dict("records")
            }
            if not open_dates:
                raise MarketDataError("A股交易日历为空")
            self.calendar_cache.set("sina", open_dates)
        result: list[TradingDay] = []
        current = start_date
        while current <= end_date:
            is_open = current in open_dates
            result.append(
                TradingDay(
                    trade_date=current,
                    is_open=is_open,
                    market_phase="交易日" if is_open else "非交易日",
                )
            )
            current += timedelta(days=1)
        return result

    def get_financial_indicators(
        self, symbols: list[str], report_date: date
    ) -> dict[str, dict[str, Any]]:
        return {
            identify_security(symbol).symbol: {
                "pe": None,
                "pb": None,
                "roe": None,
                "report_date": report_date.isoformat(),
                "warning": "真实历史财务披露时点接口尚未接入，字段不伪造",
            }
            for symbol in symbols
        }

    def health_check(self) -> ProviderHealth:
        started_at = self.monotonic()
        checked_at = self.now_provider()
        try:
            quote = self.get_latest_quotes(["000001.SZ"])[0]
        except MarketDataError as exc:
            return ProviderHealth(
                provider=self.name,
                ok=False,
                message=str(exc),
                checked_at=checked_at,
                latency_ms=int((self.monotonic() - started_at) * 1000),
            )
        return ProviderHealth(
            provider=self.name,
            ok=True,
            message=f"腾讯最新价可用，行情时间 {quote.quote_time.isoformat()}",
            checked_at=checked_at,
            latency_ms=int((self.monotonic() - started_at) * 1000),
        )

    def _get_tencent_fields(self, symbols: list[str]) -> dict[str, tuple[str, ...]]:
        normalized_symbols = [identify_security(symbol).symbol for symbol in symbols]
        cache_key = ",".join(sorted(set(normalized_symbols)))
        cached = self.raw_quote_cache.get(cache_key)
        if cached is not None:
            return cached
        per_symbol = {
            symbol: self.raw_quote_cache.get(f"symbol:{symbol}") for symbol in normalized_symbols
        }
        if all(fields is not None for fields in per_symbol.values()):
            return {symbol: fields for symbol, fields in per_symbol.items() if fields is not None}
        query_codes = [self._tencent_code(symbol) for symbol in normalized_symbols]
        try:
            payload = self.http_client.get_bytes(
                TENCENT_QUOTE_URL + ",".join(query_codes), headers=TENCENT_HEADERS
            )
        except HttpTransportError as exc:
            raise MarketDataError(str(exc)) from exc
        try:
            text = payload.decode("gbk")
        except UnicodeDecodeError as exc:
            raise MarketDataError("腾讯行情响应不是有效 GBK 文本") from exc
        parsed = self._parse_tencent_payload(text)
        if not parsed:
            raise MarketDataError("腾讯行情返回空数据或页面格式已变化")
        self.raw_quote_cache.set(cache_key, parsed)
        for symbol, fields in parsed.items():
            self.raw_quote_cache.set(f"symbol:{symbol}", fields)
        return parsed

    def _quote_from_fields(self, symbol: str, fields: tuple[str, ...]) -> Quote:
        if len(fields) < 39:
            raise MarketDataError(f"{symbol} 腾讯行情字段数量不足：{len(fields)}")
        quote_time = self._parse_quote_time(fields[30])
        amount_parts = fields[35].split("/")
        if len(amount_parts) != 3:
            raise MarketDataError(f"{symbol} 成交额组合字段格式变化")
        delay_seconds = max(
            0, int((self.now_provider().astimezone(APP_TIME_ZONE) - quote_time).total_seconds())
        )
        return Quote(
            symbol=symbol,
            name=fields[1].strip(),
            quote_time=quote_time,
            last_price=self._decimal(fields[3], "最新价"),
            change_amount=self._decimal(fields[31], "涨跌额"),
            pct_change=self._decimal(fields[32], "涨跌幅") / Decimal("100"),
            open_price=self._decimal(fields[5], "今开"),
            high_price=self._decimal(fields[33], "最高"),
            low_price=self._decimal(fields[34], "最低"),
            prev_close=self._decimal(fields[4], "昨收"),
            volume=self._lots_to_shares(fields[6]),
            amount=self._decimal(amount_parts[2], "成交额"),
            turnover_rate=self._optional_decimal(fields[38], "换手率", scale=Decimal("0.01")),
            source=f"{self.name}/腾讯",
            delay_seconds=delay_seconds,
            unsupported_fields=frozenset({"exact_share_volume"}),
        )

    def _call_akshare(
        self,
        label: str,
        operation: Callable[[], T],
        timeout_seconds: float | None = None,
    ) -> T:
        last_error: BaseException | None = None
        operation_timeout = timeout_seconds or self.settings.request_timeout_seconds
        for attempt in range(self.settings.max_retries):
            self._wait_for_akshare_rate_limit()
            result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

            def run_operation(
                target_queue: queue.Queue[tuple[bool, Any]] = result_queue,
            ) -> None:
                try:
                    target_queue.put((True, operation()))
                except BaseException as exc:
                    target_queue.put((False, exc))

            worker = threading.Thread(target=run_operation, daemon=True)
            worker.start()
            worker.join(operation_timeout)
            if worker.is_alive():
                last_error = TimeoutError(f"超过 {operation_timeout} 秒")
            else:
                succeeded, value = result_queue.get_nowait()
                if succeeded:
                    return value
                last_error = value
            if attempt + 1 < self.settings.max_retries:
                self.sleeper(0.5 * (2**attempt))
        raise MarketDataError(f"{label} 获取失败：{last_error}") from last_error

    def _wait_for_akshare_rate_limit(self) -> None:
        with self._akshare_lock:
            now = self.monotonic()
            wait_seconds = max(0.0, self._next_akshare_at - now)
            if wait_seconds:
                self.sleeper(wait_seconds)
                now = self.monotonic()
            self._next_akshare_at = now + 0.5

    @staticmethod
    def _parse_tencent_payload(text: str) -> dict[str, tuple[str, ...]]:
        parsed: dict[str, tuple[str, ...]] = {}
        for line in text.splitlines():
            first_quote = line.find(chr(34))
            last_quote = line.rfind(chr(34))
            if first_quote < 0 or last_quote <= first_quote:
                continue
            fields = tuple(line[first_quote + 1 : last_quote].split("~"))
            if len(fields) < 3 or len(fields[2]) != 6:
                continue
            exchange = "SH" if fields[2].startswith(("5", "6", "9")) else "SZ"
            parsed[f"{fields[2]}.{exchange}"] = fields
        return parsed

    @staticmethod
    def _instrument_from_row(
        code: Any,
        name: Any,
        listed_date: Any,
        exchange: str,
        industry: str | None = None,
    ) -> Instrument:
        normalized_code = str(code).strip().zfill(6)
        normalized_name = str(name).strip()
        if len(normalized_code) != 6 or not normalized_code.isdigit() or not normalized_name:
            raise MarketDataError(f"股票主表字段无效：{code}/{name}")
        upper_name = normalized_name.upper()
        return Instrument(
            symbol=f"{normalized_code}.{exchange}",
            code=normalized_code,
            exchange=exchange,
            name=normalized_name,
            board=detect_board(normalized_code),
            industry=industry,
            listed_date=AkSharePublicMarketDataProvider._date_value(listed_date),
            is_st="ST" in upper_name,
            is_delisting="退" in normalized_name,
        )

    @staticmethod
    def _order_book_level(
        fields: tuple[str, ...], price_index: int, quantity_index: int
    ) -> OrderBookLevel:
        return OrderBookLevel(
            price=AkSharePublicMarketDataProvider._optional_decimal(
                fields[price_index], f"盘口价{price_index}"
            ),
            quantity=AkSharePublicMarketDataProvider._lots_to_shares(fields[quantity_index]),
        )

    @staticmethod
    def _tencent_code(symbol: str) -> str:
        identity = identify_security(symbol)
        return f"{'sh' if identity.exchange == 'SH' else 'sz'}{identity.code}"

    @staticmethod
    def _parse_quote_time(value: str) -> datetime:
        try:
            parsed = datetime.strptime(value, "%Y%m%d%H%M%S")
        except ValueError as exc:
            raise MarketDataError(f"行情时间格式变化：{value}") from exc
        return parsed.replace(tzinfo=APP_TIME_ZONE)

    @staticmethod
    def _date_value(value: Any) -> date:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = str(value).strip()[:10]
        try:
            return date.fromisoformat(text)
        except ValueError as exc:
            raise MarketDataError(f"日期字段无效：{value}") from exc

    @staticmethod
    def _decimal(value: Any, field_name: str) -> Decimal:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none"} or text == "-":
            raise MarketDataError(f"{field_name} 缺失")
        try:
            parsed = Decimal(text)
        except InvalidOperation as exc:
            raise MarketDataError(f"{field_name} 不是有效数值：{value}") from exc
        if not parsed.is_finite():
            raise MarketDataError(f"{field_name} 不是有限数值")
        return parsed

    @staticmethod
    def _optional_decimal(
        value: Any, field_name: str, scale: Decimal = Decimal("1")
    ) -> Decimal | None:
        text = str(value).strip()
        if not text or text.lower() in {"nan", "none"} or text == "-":
            return None
        return AkSharePublicMarketDataProvider._decimal(text, field_name) * scale

    @staticmethod
    def _lots_to_shares(value: Any) -> int:
        lots = AkSharePublicMarketDataProvider._decimal(value, "成交量/委托量")
        return int(lots * Decimal("100"))

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        text = str(value).strip()
        return None if not text or text.lower() in {"nan", "none"} else text
