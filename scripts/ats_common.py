#!/usr/bin/env python3
"""Shared source loading, normalization, filtering, and reporting for ATS scanners."""

from __future__ import annotations

import hashlib
import html
import http.client
import json
import os
import re
import time
import sys
import urllib.error
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from ats_crawl_policy import (
    DEFAULT_CRAWL_POLICY,
    deterministic_retry_delay,
    retryable_error,
)

ROOT = Path(os.environ.get("OPENCLAW_WORKSPACE", Path(__file__).resolve().parents[1]))
ATS_SOURCES = ROOT / "data" / "ats_api_sources.json"
FRESHNESS_DAYS = 14
PROVIDERS = ("greenhouse", "lever", "ashby", "workday")

ROLE_PATTERNS = (
    "software engineer", "software development engineer", "software developer",
    "application developer", "product engineer", "platform engineer", "backend",
    "frontend", "full stack", "fullstack", "web developer", "mobile", "android",
    "ios", "machine learning", "artificial intelligence", " llm", "data engineer",
    "data scientist", "devops", "cloud", "site reliability", "quality engineer",
    "test engineer", "automation engineer", "associate engineer", "graduate engineer",
    "sre", "security", "sdet", " qa ",
)
EARLY_PATTERNS = (
    r"\bintern(ship)?\b", r"\bgraduate\b", r"\bnew grad\b", r"\bentry[-\s]?level\b",
    r"\bfresher\b", r"\b0\s*(?:-|to)\s*1\b", r"\b0\s*(?:-|to)\s*2\b",
    r"\b0\s*(?:-|to)\s*3\b", r"\b1\s*(?:-|to)\s*3\b",
    r"\b[0-3]\s*(?:years?|yrs?)\b", r"\bjunior\b", r"\bassociate\b",
    r"\bsoftware engineer\s+(?:i|1)\b", r"\bsoftware developer\s+(?:i|1)\b",
    r"\bsde\s+(?:i|1)\b", r"\bsde\b",
)
LOCATION_HINTS = (
    "india", "bengaluru", "bangalore", "hyderabad", "pune", "gurgaon", "gurugram",
    "mumbai", "chennai", "noida", "delhi", "remote",
)
EXCLUDE_PATTERNS = (
    "account executive", "sales", "marketing", "editor", "production manager",
    "partner manager", "customer success", "solution architect", "internal auditor",
    "finance", "recruiter",
)

NETWORK_ERRORS = (
    http.client.HTTPException,
    OSError,
    urllib.error.HTTPError,
    urllib.error.URLError,
    TimeoutError,
    json.JSONDecodeError,
)


@dataclass
class AdapterResult:
    jobs: list[dict[str, Any]]
    raw_count: int
    current_count: int
    dropped_count: int = 0
    source_repairs: list[str] = field(default_factory=list)
    current_jobs: list[dict[str, Any]] = field(default_factory=list)
    job_evidence: list[dict[str, Any]] = field(default_factory=list)


_FETCH_EVIDENCE: ContextVar[dict[str, Any] | None] = ContextVar("ats_fetch_evidence", default=None)


@contextmanager
def capture_source_evidence(source: dict[str, Any], provider: str):
    context = {
        "company": clean_text(source.get("company")),
        "provider": provider,
        "source_slug": clean_text(source.get("slug") or source.get("site") or source.get("tenant")),
        "records": [],
    }
    token = _FETCH_EVIDENCE.set(context)
    try:
        yield context["records"]
    finally:
        _FETCH_EVIDENCE.reset(token)


def _append_fetch_evidence(record: dict[str, Any]) -> None:
    context = _FETCH_EVIDENCE.get()
    if context is None:
        return
    context["records"].append({
        "company": context["company"],
        "provider": context["provider"],
        "source_slug": context["source_slug"],
        **record,
    })


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        value = " ".join(clean_text(item) for item in value.values())
    elif isinstance(value, (list, tuple, set)):
        value = " ".join(clean_text(item) for item in value)
    return re.sub(r"\s+", " ", html.unescape(str(value))).strip()


def strip_html(value: Any) -> str:
    return clean_text(re.sub(r"<[^>]+>", " ", html.unescape(str(value or ""))))


def nested(data: Any, *paths: str, default: Any = None) -> Any:
    """Return the first non-empty value from dotted paths."""
    for path in paths:
        value = data
        for part in path.split("."):
            if not isinstance(value, dict) or part not in value:
                value = None
                break
            value = value[part]
        if value not in (None, "", [], {}):
            return value
    return default


def unique_values(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for raw in values:
        if isinstance(raw, (list, tuple, set)):
            candidates = list(raw)
        else:
            candidates = [raw]
        for item in candidates:
            value = clean_text(item)
            key = value.casefold()
            if value and key not in seen:
                seen.add(key)
                result.append(value)
    return result


def parse_datetime(value: Any, now: datetime | None = None) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)):
        seconds = float(value) / 1000 if float(value) > 10_000_000_000 else float(value)
        try:
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = clean_text(value)
        relative_now = now or datetime.now(timezone.utc)
        match = re.search(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", text, re.I)
        if match:
            days = 0 if match.group(1).lower() == "today" else 1
            if match.group(2):
                days = int(match.group(2))
            parsed = relative_now - timedelta(days=days)
        else:
            try:
                parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            except ValueError:
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso_datetime(value: Any, now: datetime | None = None) -> str:
    parsed = parse_datetime(value, now=now)
    return parsed.isoformat() if parsed else ""


def is_current(*timestamps: Any, now: datetime | None = None) -> bool:
    reference = now or datetime.now(timezone.utc)
    parsed = None
    for value in timestamps:
        parsed = parse_datetime(value, now=reference)
        if parsed:
            break
    # Public ATS list endpoints contain open jobs. Providers without dates (notably Lever)
    # remain eligible instead of being discarded as stale.
    return parsed is None or reference - parsed <= timedelta(days=FRESHNESS_DAYS)


def evaluate_relevance(title: str, location: str, description: str = "") -> dict[str, Any]:
    blob = clean_text(f"{title} {location} {description}").lower()
    loc_blob = clean_text(location).lower()
    has_role = any(pattern in blob for pattern in ROLE_PATTERNS)
    has_early = any(re.search(pattern, blob) for pattern in EARLY_PATTERNS)
    has_place = any(pattern in blob for pattern in LOCATION_HINTS)
    india_place = any(pattern in loc_blob for pattern in LOCATION_HINTS if pattern != "remote")
    remote_place = "remote" in loc_blob and not re.search(
        r"\b(usa|u\.s\.|united states|canada|europe|uk|london|paris|virginia|california|new york)\b",
        loc_blob,
    )
    excluded = any(pattern in blob for pattern in EXCLUDE_PATTERNS)
    senior = bool(re.search(r"\b(senior|sr\.?|staff|principal|lead|manager|director)\b", blob))
    reasons: list[str] = []
    if not has_role:
        reasons.append("missing_role_signal")
    if not has_early:
        reasons.append("missing_early_career_signal")
    if not has_place or not (india_place or remote_place):
        reasons.append("location_not_india_or_global_remote")
    if excluded:
        reasons.append("excluded_role_signal")
    if senior:
        reasons.append("seniority_excluded")
    accepted = not reasons
    return {
        "decision": "accepted" if accepted else "rejected",
        "reasons": reasons or ["matched_role_early_career_and_location_policy"],
        "signals": {
            "role": has_role,
            "early_career": has_early,
            "location_hint": has_place,
            "india_location": india_place,
            "eligible_remote": remote_place,
            "excluded_role": excluded,
            "senior_role": senior,
        },
    }


def relevant(title: str, location: str, description: str = "") -> bool:
    return evaluate_relevance(title, location, description)["decision"] == "accepted"


def normalized_job(
    *,
    provider: str,
    source: dict[str, Any],
    source_id: Any,
    title: Any,
    locations: list[Any],
    url: Any,
    description: Any = "",
    department: Any = "",
    team: Any = "",
    employment_type: Any = "",
    workplace_type: Any = "",
    published_at: Any = "",
    updated_at: Any = "",
    now: datetime | None = None,
) -> dict[str, Any]:
    company = clean_text(source.get("company"))
    clean_title = clean_text(title)
    clean_url = clean_text(url)
    clean_locations = unique_values(locations)
    clean_workplace = clean_text(workplace_type)
    if "remote" in clean_workplace.lower() and not any("remote" in item.lower() for item in clean_locations):
        clean_locations.append("Remote")
    location = "; ".join(clean_locations) or "Not listed"
    if not company or not clean_title or not clean_url:
        raise ValueError("normalized job requires company, title, and apply URL")
    identifier = clean_text(source_id)
    if not identifier:
        key = f"{provider}|{company}|{clean_title}|{clean_url}".encode("utf-8")
        identifier = hashlib.sha256(key).hexdigest()[:20]
    first_published = iso_datetime(published_at, now=now)
    clean_updated = iso_datetime(updated_at, now=now)
    return {
        "schema_version": 1,
        "company": company,
        "source": provider,
        "source_id": identifier,
        "title": clean_title,
        "location": location,
        "locations": clean_locations,
        "department": clean_text(department),
        "team": clean_text(team),
        "employment_type": clean_text(employment_type),
        "workplace_type": clean_workplace,
        "description": strip_html(description),
        "updated_at": clean_updated,
        "first_published": first_published,
        "freshness_days": FRESHNESS_DAYS,
        "url": clean_url,
        "apply_url": clean_url,
    }


def fetch_json(url: str, payload: dict[str, Any] | None = None) -> Any:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"User-Agent": "OpenClaw job API scanner", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    method = "POST" if body else "GET"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    started_at = datetime.now(timezone.utc)
    last_error: BaseException | None = None
    for attempt in range(1, DEFAULT_CRAWL_POLICY.max_attempts + 1):
        try:
            with urllib.request.urlopen(
                request,
                timeout=DEFAULT_CRAWL_POLICY.request_timeout_seconds,
            ) as response:
                parsed = json.loads(response.read().decode("utf-8", errors="replace"))
                elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
                _append_fetch_evidence({
                    "url": url,
                    "method": method,
                    "request_payload": payload,
                    "response_payload": parsed,
                    "status_code": int(getattr(response, "status", 200) or 200),
                    "outcome": "success",
                    "attempt_count": attempt,
                    "elapsed_ms": elapsed_ms,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "error": "",
                })
                return parsed
        except NETWORK_ERRORS as exc:
            last_error = exc
            if attempt < DEFAULT_CRAWL_POLICY.max_attempts and retryable_error(exc):
                time.sleep(deterministic_retry_delay(url, attempt - 1))
                continue
            elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            _append_fetch_evidence({
                "url": url,
                "method": method,
                "request_payload": payload,
                "response_payload": None,
                "status_code": int(getattr(exc, "code", 0) or 0),
                "outcome": "error",
                "attempt_count": attempt,
                "elapsed_ms": elapsed_ms,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "error": clean_text(exc),
            })
            raise
    raise RuntimeError(f"fetch failed without an exception: {last_error}")


def infer_provider(source: dict[str, Any]) -> str:
    explicit = clean_text(source.get("provider")).lower()
    url = clean_text(source.get("api_url") or source.get("career_url")).lower()
    domains = {
        "greenhouse": ("greenhouse.io",),
        "lever": ("lever.co",),
        "ashby": ("ashbyhq.com",),
        "workday": ("myworkdayjobs.com",),
    }
    from_url = next((provider for provider, hints in domains.items() if any(hint in url for hint in hints)), "")
    return from_url or explicit


def load_source_database(path: Path = ATS_SOURCES) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for index, raw in enumerate(data.get("sources", [])):
        if not isinstance(raw, dict):
            errors.append({"company": f"source[{index}]", "source": "unknown", "slug": "", "error": "source must be an object"})
            continue
        source = dict(raw)
        provider = infer_provider(source)
        repairs: list[str] = []
        if provider and provider != clean_text(source.get("provider")).lower():
            repairs.append(f"provider inferred as {provider} from URL")
        source["provider"] = provider
        source["_repairs"] = repairs
        if not clean_text(source.get("company")) or provider not in PROVIDERS:
            errors.append({
                "company": clean_text(source.get("company")) or f"source[{index}]",
                "source": provider or "unknown",
                "slug": clean_text(source.get("slug")),
                "error": "source requires company and a supported provider or recognizable ATS URL",
            })
            continue
        sources.append(source)
    return sources, errors


def deduplicate_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for job in jobs:
        key = (job["company"].casefold(), job["title"].casefold(), job["url"].casefold())
        deduped[key] = job
    return sorted(deduped.values(), key=lambda job: (job["company"].casefold(), job["title"].casefold()))


def deduplicate_jobs_by_source(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped = {
        (job["source"], job["source_id"]): job
        for job in jobs
    }
    return sorted(
        deduped.values(),
        key=lambda job: (job["source"], job["company"].casefold(), job["title"].casefold()),
    )


def scan_provider(
    provider: str,
    scanner: Callable[[dict[str, Any]], AdapterResult],
    sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if sources is None:
        sources, _ = load_source_database()
    selected = [source for source in sources if source["provider"] == provider]
    checked: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    matches: list[dict[str, Any]] = []
    current_jobs: list[dict[str, Any]] = []
    fetch_evidence: list[dict[str, Any]] = []
    job_evidence: list[dict[str, Any]] = []
    job_evaluations: list[dict[str, Any]] = []
    repairs: list[dict[str, Any]] = []
    total_raw = total_current = total_dropped = 0
    for source in selected:
        source_fetches: list[dict[str, Any]] = []
        try:
            with capture_source_evidence(source, provider) as source_fetches:
                result = scanner(source)
            fetch_evidence.extend(source_fetches)
            total_raw += result.raw_count
            total_current += result.current_count
            total_dropped += result.dropped_count
            matches.extend(result.jobs)
            current_jobs.extend(result.current_jobs)
            job_evidence.extend(result.job_evidence)
            for job in result.current_jobs:
                context = f"{job['department']} {job['team']} {job['employment_type']} {job['description']}"
                evaluation = evaluate_relevance(job["title"], job["location"], context)
                job_evaluations.append({
                    "job_key": f"{job['source']}:{job['source_id']}",
                    **evaluation,
                })
            checked.append({
                "company": source["company"], "source": provider,
                "slug": clean_text(source.get("slug") or source.get("site") or source.get("tenant")),
                "raw_jobs": result.raw_count, "recent_jobs": result.current_count,
                "matches": len(result.jobs), "dropped_jobs": result.dropped_count,
            })
            notes = list(source.get("_repairs", [])) + result.source_repairs
            if notes:
                repairs.append({"company": source["company"], "source": provider, "repairs": unique_values(notes)})
        except NETWORK_ERRORS + (ValueError, TypeError, KeyError) as exc:
            fetch_evidence.extend(source_fetches)
            if not source_fetches:
                fetch_evidence.append({
                    "company": clean_text(source.get("company")),
                    "provider": provider,
                    "source_slug": clean_text(source.get("slug") or source.get("site") or source.get("tenant")),
                    "url": clean_text(source.get("api_url") or source.get("career_url")),
                    "method": "",
                    "request_payload": None,
                    "response_payload": None,
                    "status_code": int(getattr(exc, "code", 0) or 0),
                    "outcome": "error",
                    "attempt_count": 0,
                    "elapsed_ms": 0,
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "error": clean_text(exc),
                })
            errors.append({
                "company": clean_text(source.get("company")), "source": provider,
                "slug": clean_text(source.get("slug") or source.get("site") or source.get("tenant")),
                "error": str(exc),
            })
        time.sleep(0.2)
    return {
        "provider": provider,
        "attempted": len(selected),
        "successful": len(checked),
        "checked": checked,
        "errors": errors,
        "source_repairs": repairs,
        "total_raw_jobs": total_raw,
        "total_current_jobs": total_current,
        "total_dropped_jobs": total_dropped,
        "matches": deduplicate_jobs(matches),
        "_current_jobs": deduplicate_jobs_by_source(current_jobs),
        "_fetch_evidence": fetch_evidence,
        "_job_evidence": job_evidence,
        "_job_evaluations": job_evaluations,
    }


def write_provider_outputs(report: dict[str, Any]) -> None:
    try:
        from ats_supabase import persist_report
    except Exception:  # pragma: no cover - optional persistence path
        persist_report = None
    provider = report["provider"]
    json_path = ROOT / "memory" / f"job_api_scan_{provider}_latest.json"
    md_path = ROOT / "memory" / f"job_api_scan_{provider}_latest.md"
    public_report = {key: value for key, value in report.items() if not key.startswith("_")}
    payload = {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "freshness_days": FRESHNESS_DAYS,
        **public_report,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        f"# {provider.title()} ATS Job Scan - {payload['generated_at']}", "",
        f"Sources attempted: {report['attempted']}",
        f"Sources successful: {report['successful']}",
        f"Jobs fetched: {report['total_raw_jobs']}",
        f"Current/undated open jobs: {report['total_current_jobs']}",
        f"Matching jobs: {len(report['matches'])}", "", "## Matches",
    ]
    lines.extend(
        f"- {job['company']} - {job['title']} - {job['location']} - {job['url']}"
        for job in report["matches"][:40]
    )
    if report["errors"]:
        lines.extend(["", "## Endpoint Errors"])
        lines.extend(f"- {item['company']} ({item['slug']}): {item['error']}" for item in report["errors"][:30])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if persist_report is not None:
        result = persist_report(
            payload,
            report.get("_current_jobs") or [],
            scan_kind=provider,
            fetch_evidence=report.get("_fetch_evidence") or [],
            job_evidence=report.get("_job_evidence") or [],
            job_evaluations=report.get("_job_evaluations") or [],
        )
        if result.status == "error":
            print(f"ATS persistence error for {provider}: {result.error}", file=sys.stderr)
    print(md_path.read_text(encoding="utf-8"))


def provider_main(provider: str, scanner: Callable[[dict[str, Any]], AdapterResult]) -> int:
    write_provider_outputs(scan_provider(provider, scanner))
    return 0
