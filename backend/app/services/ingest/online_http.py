"""Bounded public GET transport. No credentials, private endpoints or bypasses."""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable
from urllib.parse import urlsplit

import httpx


class SourceFailure(Exception):
    def __init__(self, code: str, retry_after: float = 0, permanent: bool = False):
        super().__init__(code)  # No upstream URL, body, header or exception text.
        self.code, self.retry_after, self.permanent = code, retry_after, permanent


def retry_delay(value: str | None) -> float:
    if not value:
        return 0
    try:
        return max(0, float(value))
    except ValueError:
        try:
            return max(0, (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return 0


class PublicHttp:
    def __init__(self, *, timeout: float = 10, retries: int = 2,
                 stop: threading.Event | None = None,
                 transport: httpx.BaseTransport | None = None,
                 clock: Callable[[], float] = time.monotonic):
        self.timeout, self.retries = timeout, retries
        self.stop = stop or threading.Event()
        self.clock = clock
        self.client = httpx.Client(
            timeout=timeout, follow_redirects=False, transport=transport,
            headers={"User-Agent": "ResilientRoute-Collector/1.0 (academic; public announcements)"},
        )

    def close(self):
        self.client.close()

    def get(self, url: str) -> bytes:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname != "www.mtr.com.hk"
                or parsed.port not in (None, 443) or parsed.username or parsed.password
                or parsed.query or parsed.fragment
                or parsed.path not in {
                    "/robots.txt", "/alert/alert.json", "/alert/ryg_line_status.json",
                }):
            raise SourceFailure("unsupported_endpoint", permanent=True)
        for attempt in range(self.retries + 1):
            if self.stop.is_set():
                raise SourceFailure("stopped")
            deadline = self.clock() + self.timeout
            try:
                with self.client.stream("GET", url) as response:
                    if response.status_code in (401, 403):
                        raise SourceFailure("access_denied", permanent=True)
                    if response.status_code == 429:
                        raise SourceFailure("rate_limited", retry_delay(response.headers.get("Retry-After")))
                    if response.status_code >= 500:
                        raise SourceFailure("server_error")
                    if response.status_code != 200:
                        raise SourceFailure("unexpected_http_status", permanent=True)
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        if self.stop.is_set():
                            raise SourceFailure("stopped")
                        if self.clock() > deadline:
                            raise SourceFailure("timeout")
                        size += len(chunk)
                        if size > 2 * 1024 * 1024:
                            raise SourceFailure("response_too_large", permanent=True)
                        chunks.append(chunk)
                    return b"".join(chunks)
            except httpx.TimeoutException:
                error = SourceFailure("timeout")
            except httpx.HTTPError:
                error = SourceFailure("network_error")
            except SourceFailure as exc:
                error = exc
            if error.permanent or error.code in {"rate_limited", "stopped"} or attempt == self.retries:
                raise error
            if self.stop.wait(min(2 ** attempt, 4)):
                raise SourceFailure("stopped")
        raise AssertionError("unreachable")
