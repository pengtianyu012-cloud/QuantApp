import unittest

import requests

from app.data.providers.http_client import HttpTransportError, RateLimitedHttpClient


class FakeSession:
    def __init__(self, responses: list[requests.Response]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, float]] = []

    def get(self, url: str, headers=None, timeout: float = 0) -> requests.Response:
        self.calls.append((url, timeout))
        return self.responses.pop(0)


def response(status_code: int, content: bytes) -> requests.Response:
    result = requests.Response()
    result.status_code = status_code
    result._content = content
    result.url = "https://example.test/quote"
    return result


class RateLimitedHttpClientTests(unittest.TestCase):
    def test_retries_retryable_status_with_exponential_backoff(self) -> None:
        session = FakeSession([response(503, b"busy"), response(200, b"quote")])
        sleeps: list[float] = []
        client = RateLimitedHttpClient(
            timeout_seconds=3,
            max_retries=2,
            backoff_seconds=0.25,
            min_interval_seconds=0,
            session=session,
            sleeper=sleeps.append,
        )

        payload = client.get_bytes("https://example.test/quote")

        self.assertEqual(payload, b"quote")
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(session.calls[0][1], 3)
        self.assertEqual(sleeps, [0.25])

    def test_empty_response_fails_after_limited_retries(self) -> None:
        session = FakeSession([response(200, b""), response(200, b"")])
        client = RateLimitedHttpClient(
            max_retries=2,
            min_interval_seconds=0,
            session=session,
            sleeper=lambda _: None,
        )

        with self.assertRaises(HttpTransportError):
            client.get_bytes("https://example.test/quote")

        self.assertEqual(len(session.calls), 2)


if __name__ == "__main__":
    unittest.main()
