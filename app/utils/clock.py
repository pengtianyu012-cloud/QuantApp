from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Protocol

from app.config.settings import APP_TIME_ZONE


class Clock(Protocol):
    def now(self) -> datetime: ...

    def today(self) -> date: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(APP_TIME_ZONE)

    def today(self) -> date:
        return self.now().date()


@dataclass
class FrozenClock:
    current: datetime

    def __post_init__(self) -> None:
        if self.current.tzinfo is None or self.current.utcoffset() is None:
            self.current = self.current.replace(tzinfo=APP_TIME_ZONE)
        else:
            self.current = self.current.astimezone(APP_TIME_ZONE)

    def now(self) -> datetime:
        return self.current

    def today(self) -> date:
        return self.current.date()

    def set(self, value: datetime) -> None:
        self.current = value
        self.__post_init__()

    def advance(self, delta: timedelta) -> None:
        self.current += delta
