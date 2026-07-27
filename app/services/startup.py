from __future__ import annotations

import importlib.util
from pathlib import Path

from app.config.settings import RuntimePaths

REQUIRED_DEPENDENCIES = ("PySide6", "pandas", "numpy", "sqlalchemy")
DEV_DEPENDENCIES = ("pytest", "ruff", "PyInstaller")


def dependency_status() -> dict[str, bool]:
    """检查关键依赖是否可导入，不触发安装或网络访问。"""

    return {
        module_name: importlib.util.find_spec(module_name) is not None
        for module_name in (*REQUIRED_DEPENDENCIES, *DEV_DEPENDENCIES)
    }


def ensure_runtime_directories(paths: RuntimePaths) -> None:
    for path in (paths.data_dir, paths.logs_dir, paths.cache_dir, paths.config_dir):
        Path(path).mkdir(parents=True, exist_ok=True)
