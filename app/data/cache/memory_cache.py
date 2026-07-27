from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    value: T
    expires_at: datetime


class TtlMemoryCache(Generic[T]):
    """轻量内存缓存，阶段2用于Mock和后续适配器共用。"""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)
        self._items: dict[str, CacheEntry[T]] = {}

    def get(self, key: str) -> T | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if datetime.now(UTC) >= entry.expires_at:
            self._items.pop(key, None)
            return None
        return entry.value

    def set(self, key: str, value: T) -> None:
        self._items[key] = CacheEntry(value=value, expires_at=datetime.now(UTC) + self.ttl)

    def clear(self) -> None:
        self._items.clear()
