from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config.settings import RuntimePaths

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def configure_logging(paths: RuntimePaths, level: int = logging.INFO) -> logging.Logger:
    """配置滚动文件日志，避免在控制台刷大量信息。"""

    paths.logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("quant_app")
    logger.setLevel(level)
    logger.propagate = False

    log_file = paths.logs_dir / "quant_app.log"
    existing_files = [
        getattr(handler, "baseFilename", None)
        for handler in logger.handlers
        if isinstance(handler, RotatingFileHandler)
    ]
    if str(log_file) not in existing_files:
        handler = RotatingFileHandler(
            log_file,
            maxBytes=2_000_000,
            backupCount=5,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        logger.addHandler(handler)

    return logger
