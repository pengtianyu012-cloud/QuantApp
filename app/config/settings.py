from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import timedelta, timezone
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

APP_NAME = "A股量化模拟交易系统"
APP_VERSION = "0.1.0"
DISCLAIMER = "本软件仅用于量化研究和模拟交易，不构成投资建议，不连接真实券商，不执行真实订单。"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_DATA_DIRECTORY_NAME = "QuantApp"


def build_app_timezone():
    try:
        return ZoneInfo("Asia/Shanghai")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8), name="Asia/Shanghai")


APP_TIME_ZONE = build_app_timezone()


@dataclass(frozen=True)
class TradingRules:
    """集中保存A股模拟交易的核心规则。"""

    initial_cash: Decimal = Decimal("100000")
    max_single_position_pct: Decimal = Decimal("0.30")
    max_total_position_pct: Decimal = Decimal("0.90")
    max_drawdown_pct: Decimal = Decimal("0.15")
    min_listing_days: int = 60
    buy_lot_size: int = 100
    backtest_years: int = 5
    benchmark: str = "沪深300"
    signal_time: str = "每日收盘后"
    execution_time: str = "下一交易日开盘"


@dataclass(frozen=True)
class TradingCostSettings:
    """交易成本假设，后续由系统设置页持久化。"""

    commission_rate: Decimal = Decimal("0.0003")
    min_commission: Decimal = Decimal("5")
    stamp_tax_rate: Decimal = Decimal("0.0005")
    transfer_fee_rate: Decimal = Decimal("0.00001")
    slippage_bps: Decimal = Decimal("2")
    market_impact_bps: Decimal = Decimal("3")
    max_volume_participation: Decimal = Decimal("0.10")


@dataclass(frozen=True)
class RefreshSettings:
    watchlist_seconds: int = 3
    monitor_seconds: int = 10
    request_timeout_seconds: int = 8
    max_retries: int = 3
    cache_ttl_seconds: int = 15
    stale_quote_seconds: int = 30


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    data_dir: Path
    logs_dir: Path
    cache_dir: Path
    config_dir: Path


def default_runtime_paths(project_root: Path | None = None) -> RuntimePaths:
    runtime_root = project_root or _default_runtime_root()
    return RuntimePaths(
        project_root=runtime_root,
        data_dir=runtime_root / "data",
        logs_dir=runtime_root / "logs",
        cache_dir=runtime_root / "data" / "cache",
        config_dir=runtime_root / "data" / "config",
    )


def _default_runtime_root() -> Path:
    if not getattr(sys, "frozen", False):
        return PROJECT_ROOT
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / APP_DATA_DIRECTORY_NAME
    return Path.home() / "AppData" / "Local" / APP_DATA_DIRECTORY_NAME
