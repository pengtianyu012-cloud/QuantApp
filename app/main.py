from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication

from app.config import default_runtime_paths
from app.services.startup import ensure_runtime_directories
from app.ui.main_window import QuantMainWindow
from app.ui.styles import build_stylesheet
from app.utils.logging import configure_logging


def build_application(argv: Sequence[str] | None = None) -> tuple[QApplication, QuantMainWindow]:
    """构建Qt应用和主窗口，供启动脚本与测试复用。"""

    paths = default_runtime_paths()
    ensure_runtime_directories(paths)
    logger = configure_logging(paths)
    logger.info("application bootstrap started")

    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(build_stylesheet())

    window = QuantMainWindow()
    return app, window


def main(argv: Sequence[str] | None = None) -> int:
    app, window = build_application(argv)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
