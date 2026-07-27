from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import requests

LOGGER = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class HttpTransportError(RuntimeError):
    """公开行情 HTTP 请求在有限重试后仍失败。"""


class RateLimitedHttpClient:
    """带超时、退避、限流和状态码检查的 requests 客户端。"""

    def __init__(
        self,
        timeout_seconds: float = 8.0,
        max_retries: int = 3,
        backoff_seconds: float = 0.5,
        min_interval_seconds: float = 0.5,
        session: requests.Session | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("请求超时必须大于0")
        if max_retries < 1:
            raise ValueError("最大重试次数必须至少为1")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.min_interval_seconds = min_interval_seconds
        self.session = session or requests.Session()
        self.sleeper = sleeper
        self.monotonic = monotonic
        self._rate_lock = threading.Lock()
        self._next_request_at = 0.0

    def get_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            self._wait_for_rate_limit()
            try:
                response = self.session.get(
                    url,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                if response.status_code in RETRYABLE_STATUS_CODES:
                    raise requests.HTTPError(f"HTTP {response.status_code}", response=response)
                response.raise_for_status()
                if not response.content:
                    raise ValueError("响应内容为空")
                return bytes(response.content)
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                LOGGER.warning(
                    "market data request failed attempt=%s/%s error=%s",
                    attempt + 1,
                    self.max_retries,
                    type(exc).__name__,
                )
                if attempt + 1 < self.max_retries:
                    self.sleeper(self.backoff_seconds * (2**attempt))
        raise HttpTransportError(f"公开行情请求失败：{last_error}") from last_error

    def _wait_for_rate_limit(self) -> None:
        with self._rate_lock:
            now = self.monotonic()
            wait_seconds = max(0.0, self._next_request_at - now)
            if wait_seconds:
                self.sleeper(wait_seconds)
                now = self.monotonic()
            self._next_request_at = now + self.min_interval_seconds
