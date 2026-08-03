from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock


@dataclass
class CacheEntry[T]:
    value: T
    expires_at: datetime


class TtlMemoryCache[T]:
    """轻量内存缓存，阶段2用于Mock和后续适配器共用。"""

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)
        self._items: dict[str, CacheEntry[T]] = {}
        self._lock = RLock()

    def get(self, key: str) -> T | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if datetime.now(UTC) >= entry.expires_at:
                self._items.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._items[key] = CacheEntry(value=value, expires_at=datetime.now(UTC) + self.ttl)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
