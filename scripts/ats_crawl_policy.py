#!/usr/bin/env python3
"""Explicit crawl policy for the configured ATS company sources."""

from __future__ import annotations

import hashlib
import http.client
import json
import urllib.error
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class CrawlPolicy:
    scope: str = "configured_companies_only"
    source_priority: tuple[str, ...] = (
        "official_ats_api",
        "official_career_page_http",
        "public_browser_render",
        "unresolved",
    )
    retry_delays_seconds: tuple[float, ...] = (5.0, 30.0, 120.0)
    jitter_ratio: float = 0.15
    request_timeout_seconds: float = 20.0
    retention_days: int = 90
    robots_policy: str = "advisory_for_public_pages"
    access_control_policy: str = "do_not_bypass"

    @property
    def max_attempts(self) -> int:
        return len(self.retry_delays_seconds) + 1

    def as_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_priority"] = list(self.source_priority)
        value["retry_delays_seconds"] = list(self.retry_delays_seconds)
        return value


DEFAULT_CRAWL_POLICY = CrawlPolicy()


def deterministic_retry_delay(url: str, retry_index: int, policy: CrawlPolicy = DEFAULT_CRAWL_POLICY) -> float:
    base = policy.retry_delays_seconds[retry_index]
    digest = hashlib.sha256(f"{url}|{retry_index}".encode("utf-8")).digest()
    unit = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    factor = 1.0 + ((unit * 2.0) - 1.0) * policy.jitter_ratio
    return round(base * factor, 3)


def retryable_error(error: BaseException) -> bool:
    if isinstance(error, urllib.error.HTTPError):
        return error.code in {408, 425, 429} or 500 <= error.code <= 599
    return isinstance(
        error,
        (
            http.client.HTTPException,
            urllib.error.URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
        ),
    )
