from __future__ import annotations

import os
from enum import StrEnum


class RuntimeModeError(ValueError):
    """运行模式配置不明确或不安全。"""


class RuntimeMode(StrEnum):
    MOCK = "mock"
    RESEARCH = "research"
    PAPER = "paper"

    @property
    def requires_real_market_data(self) -> bool:
        return self in {RuntimeMode.RESEARCH, RuntimeMode.PAPER}

    @property
    def allows_manual_orders(self) -> bool:
        return self in {RuntimeMode.MOCK, RuntimeMode.PAPER}


def resolve_runtime_mode(value: RuntimeMode | str | None = None) -> RuntimeMode:
    if isinstance(value, RuntimeMode):
        return value
    raw = value or os.environ.get("QUANT_APP_MODE")
    if raw:
        try:
            return RuntimeMode(str(raw).strip().lower())
        except ValueError as exc:
            raise RuntimeModeError(f"不支持的运行模式：{raw}") from exc

    legacy_provider = os.environ.get("QUANT_APP_DATA_PROVIDER", "mock").strip().lower()
    if legacy_provider == "mock":
        return RuntimeMode.MOCK
    if legacy_provider in {"public", "akshare", "real"}:
        return RuntimeMode.RESEARCH
    raise RuntimeModeError(f"无法从旧数据源配置推导运行模式：{legacy_provider}")
