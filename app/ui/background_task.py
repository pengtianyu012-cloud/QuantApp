from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class BackgroundTaskSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class BackgroundTask(QRunnable):
    """在线程池执行阻塞函数，并把结果安全送回 Qt 主线程。"""

    def __init__(self, operation: Callable[[], Any]) -> None:
        super().__init__()
        self.operation = operation
        self.signals = BackgroundTaskSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.operation()
        except Exception as exc:
            self.signals.error.emit(f"{type(exc).__name__}: {exc}")
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
