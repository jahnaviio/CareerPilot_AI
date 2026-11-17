"""Polite HTTP client: honours robots.txt, enforces per-host spacing, retries with backoff.
Never touches authenticated, CAPTCHA-protected or paywalled endpoints."""
from __future__ import annotations

import logging
import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import re

import requests

from config import settings

log = logging.getLogger(__name__)


_SECRET = re.compile(r"(app_key|app_id|api_key|key|token)=[^&\s'\"]+", re.I)


def redact(msg: str) -> str:
    """Remove credentials that requests puts inside exception text (the URL)."""
    return _SECRET.sub(r"\1=***", msg)


class FetchError(RuntimeError):
    def __init__(self, msg: str, status: int | None = None):
        super().__init__(msg)
        self.status = status


class PoliteClient:
    def __init__(self, min_interval: float | None = None, timeout: int | None = None, session: requests.Session | None = None):
        self.min_interval = settings.http_min_interval_s if min_interval is None else min_interval
        self.timeout = timeout or settings.http_timeout_s
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = settings.http_user_agent
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._lock = threading.Lock()

    def _wait(self, host: str) -> None:
        with self._lock:
            gap = time.monotonic() - self._last.get(host, 0.0)
            if gap < self.min_interval:
                time.sleep(self.min_interval - gap)
            self._last[host] = time.monotonic()

    def _allowed(self, url: str) -> bool:
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait(p.netloc)
                r = self.session.get(f"{host}/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[host] = rp
                else:
                    self._robots[host] = None  # no robots.txt -> allowed
            except requests.RequestException:
                self._robots[host] = None
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(settings.http_user_agent, url)

    def get_json(self, url: str, retries: int = 3):
        if not self._allowed(url):
            raise FetchError("Blocked by robots.txt", 403)
        host = urlparse(url).netloc
        last: Exception | None = None
        for attempt in range(retries):
            self._wait(host)
            try:
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code == 404:
                    raise FetchError("Board not found (404)", 404)
                if r.status_code in (429, 500, 502, 503, 504):
                    retry_after = float(r.headers.get("Retry-After", 0) or 0)
                    time.sleep(max(retry_after, 2 ** attempt))
                    last = FetchError(f"HTTP {r.status_code}", r.status_code)
                    continue
                r.raise_for_status()
                return r.json()
            except FetchError:
                raise
            except (requests.RequestException, ValueError) as exc:
                last = FetchError(redact(f"{type(exc).__name__}: {exc}")[:200])
                time.sleep(2 ** attempt)
        raise last or FetchError("unknown fetch failure")

    def check_url(self, url: str) -> tuple[bool, int | None]:
        """Broken-link check. Returns (reachable, status). Treats 403/405/429 as 'cannot tell' -> reachable."""
        if not self._allowed(url):
            return True, None  # we are not allowed to probe; do not claim it is broken
        self._wait(urlparse(url).netloc)
        try:
            r = self.session.get(url, timeout=self.timeout, allow_redirects=True, stream=True)
            r.close()
            if r.status_code in (404, 410):
                return False, r.status_code
            return (r.status_code < 500 or r.status_code in (503,)), r.status_code
        except requests.RequestException:
            return False, None
