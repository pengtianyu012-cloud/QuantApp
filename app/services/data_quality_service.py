from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.data.providers import Instrument, MarketDataProvider, Quote
from app.data.validators import validate_order_book, validate_quote


@dataclass(frozen=True)
class DataQualityReport:
    provider: str
    checked_at: datetime
    target: str
    status: str
    missing_fields: tuple[str, ...]
    duplicate_count: int
    message: str

    @property
    def ok(self) -> bool:
        return self.status == "通过"


class DataQualityService:
    def __init__(self, provider: MarketDataProvider) -> None:
        self.provider = provider

    def run_all_checks(self) -> list[DataQualityReport]:
        instruments = self.provider.get_stock_list()
        quotes = self.provider.get_latest_quotes(
            [instrument.symbol for instrument in instruments[:4]]
        )
        reports = [self.check_instruments(instruments), self.check_quotes(quotes)]
        if quotes:
            order_book = self.provider.get_order_book(quotes[0].symbol)
            reports.append(self.check_order_book(order_book.symbol, order_book))
        return reports

    def check_instruments(self, instruments: list[Instrument]) -> DataQualityReport:
        symbols = [instrument.symbol for instrument in instruments]
        duplicate_count = len(symbols) - len(set(symbols))
        missing = []
        for field_name in ("symbol", "code", "exchange", "name", "listed_date"):
            if any(not getattr(instrument, field_name) for instrument in instruments):
                missing.append(field_name)
        return self._report(
            target="instruments",
            passed=duplicate_count == 0 and not missing,
            missing_fields=tuple(missing),
            duplicate_count=duplicate_count,
            message="股票列表字段完整"
            if duplicate_count == 0 and not missing
            else "股票列表存在质量问题",
        )

    def check_quotes(self, quotes: list[Quote]) -> DataQualityReport:
        missing_fields: list[str] = []
        for quote in quotes:
            result = validate_quote(quote)
            missing_fields.extend(issue.field for issue in result.issues)
        return self._report(
            target="latest_quotes",
            passed=not missing_fields,
            missing_fields=tuple(sorted(set(missing_fields))),
            duplicate_count=0,
            message="最新行情字段校验通过" if not missing_fields else "最新行情字段校验失败",
        )

    def check_order_book(self, symbol: str, order_book) -> DataQualityReport:
        result = validate_order_book(order_book)
        missing_fields = tuple(issue.field for issue in result.issues)
        return self._report(
            target=f"order_book:{symbol}",
            passed=result.ok,
            missing_fields=missing_fields,
            duplicate_count=0,
            message="五档盘口字段校验通过" if result.ok else "五档盘口字段校验失败",
        )

    def _report(
        self,
        target: str,
        passed: bool,
        missing_fields: tuple[str, ...],
        duplicate_count: int,
        message: str,
    ) -> DataQualityReport:
        return DataQualityReport(
            provider=self.provider.name,
            checked_at=datetime.now(UTC),
            target=target,
            status="通过" if passed else "失败",
            missing_fields=missing_fields,
            duplicate_count=duplicate_count,
            message=message,
        )
