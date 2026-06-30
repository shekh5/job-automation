#!/usr/bin/env python3
"""Phase 3C URL reachability verification for persisted ATS jobs.

This verifier performs polite HTTP checks only. It does not render pages,
solve CAPTCHA, log in, or bypass access controls. It records URL reachability
signals and leaves final open/closed classification to Phase 3D.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ats_common import clean_text
from ats_crawl_policy import DEFAULT_CRAWL_POLICY, deterministic_retry_delay, retryable_error
from ats_supabase import persist_verification_results
from verify_ats_jobs import load_jobs, valid_http_url

URL_VERIFIER_SCHEMA_VERSION = 1
BLOCKED_STATUS_CODES = {401, 403, 429}
MISSING_STATUS_CODES = {404, 410}
HEAD_FALLBACK_STATUS_CODES = {403, 405, 501}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="ATS scan run UUID; defaults to latest combined scan")
    parser.add_argument("--company", help="Optional exact company filter")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing verification rows")
    parser.add_argument("--sleep", type=float, default=0.2, help="Delay between jobs in seconds")
    return parser.parse_args()


def _safe_error(exc: BaseException) -> str:
    text = clean_text(exc)
    if len(text) > 400:
        return text[:397] + "..."
    return text


def _request(url: str, method: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": "OpenClaw ATS URL verifier",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        method=method,
    )


def _status_category(status_code: int, error_type: str = "") -> str:
    if status_code in BLOCKED_STATUS_CODES:
        return "blocked"
    if status_code in MISSING_STATUS_CODES:
        return "missing"
    if 200 <= status_code <= 399:
        return "reachable"
    if status_code >= 500 or error_type in {"URLError", "TimeoutError", "OSError"}:
        return "transient_failure"
    if status_code:
        return "unknown"
    return "error"


def _single_request(url: str, method: str) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)
    try:
        with urllib.request.urlopen(
            _request(url, method),
            timeout=DEFAULT_CRAWL_POLICY.request_timeout_seconds,
        ) as response:
            elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
            status_code = int(getattr(response, "status", 200) or 200)
            final_url = clean_text(getattr(response, "url", "") or response.geturl() or url)
            return {
                "method": method,
                "status_code": status_code,
                "final_url": final_url,
                "elapsed_ms": elapsed_ms,
                "error": "",
                "error_type": "",
                "category": _status_category(status_code),
            }
    except urllib.error.HTTPError as exc:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        status_code = int(getattr(exc, "code", 0) or 0)
        final_url = clean_text(getattr(exc, "url", "") or url)
        return {
            "method": method,
            "status_code": status_code,
            "final_url": final_url,
            "elapsed_ms": elapsed_ms,
            "error": _safe_error(exc),
            "error_type": type(exc).__name__,
            "category": _status_category(status_code, type(exc).__name__),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        return {
            "method": method,
            "status_code": 0,
            "final_url": "",
            "elapsed_ms": elapsed_ms,
            "error": _safe_error(exc),
            "error_type": type(exc).__name__,
            "category": _status_category(0, type(exc).__name__),
        }


def check_url_reachability(url: Any, *, prefer_method: str = "HEAD") -> dict[str, Any]:
    text = clean_text(url)
    if not valid_http_url(text):
        return {
            "input_url": text,
            "method": "",
            "status_code": 0,
            "final_url": "",
            "elapsed_ms": 0,
            "attempt_count": 0,
            "error": "malformed_url",
            "error_type": "ValueError",
            "category": "invalid",
            "fallback_used": False,
        }

    attempts: list[dict[str, Any]] = []
    methods = [prefer_method.upper()]
    last_error_retryable = False
    for attempt_index in range(DEFAULT_CRAWL_POLICY.max_attempts):
        result = _single_request(text, methods[-1])
        attempts.append(result)

        if (
            result["method"] == "HEAD"
            and result["status_code"] in HEAD_FALLBACK_STATUS_CODES
            and "GET" not in methods
        ):
            methods.append("GET")
            result = _single_request(text, "GET")
            attempts.append(result)

        error_for_retry: BaseException | None = None
        status_code = int(result.get("status_code") or 0)
        if status_code >= 500 or result.get("category") == "transient_failure":
            error_for_retry = urllib.error.HTTPError(text, status_code or 503, result.get("error") or "transient", {}, None)
        last_error_retryable = bool(error_for_retry and retryable_error(error_for_retry))
        if not last_error_retryable or attempt_index >= DEFAULT_CRAWL_POLICY.max_attempts - 1:
            break
        time.sleep(deterministic_retry_delay(text, attempt_index))

    final = attempts[-1]
    return {
        "input_url": text,
        "method": final["method"],
        "status_code": final["status_code"],
        "final_url": final["final_url"],
        "elapsed_ms": sum(int(item.get("elapsed_ms") or 0) for item in attempts),
        "attempt_count": len(attempts),
        "error": final["error"],
        "error_type": final["error_type"],
        "category": final["category"],
        "fallback_used": any(item["method"] == "GET" for item in attempts) and attempts[0]["method"] == "HEAD",
        "retryable_final_error": last_error_retryable,
        "attempts": attempts,
    }


def _prefixed_signals(prefix: str, result: Mapping[str, Any]) -> dict[str, Any]:
    category = clean_text(result.get("category"))
    return {
        f"{prefix}_reachable": category == "reachable",
        f"{prefix}_missing": category == "missing",
        f"{prefix}_blocked": category == "blocked",
        f"{prefix}_invalid": category == "invalid",
        f"{prefix}_transient_failure": category == "transient_failure",
        f"{prefix}_status_code": int(result.get("status_code") or 0),
        f"{prefix}_final_url": clean_text(result.get("final_url")),
        f"{prefix}_method": clean_text(result.get("method")),
        f"{prefix}_fallback_used": bool(result.get("fallback_used")),
    }


def verify_job_urls(job: Mapping[str, Any]) -> dict[str, Any]:
    job_url = check_url_reachability(job.get("url"))
    apply_url = check_url_reachability(job.get("apply_url"))
    categories = {clean_text(job_url.get("category")), clean_text(apply_url.get("category"))}

    reasons: list[str] = []
    if "invalid" in categories:
        status = "invalid"
        confidence = 0.95
        if job_url["category"] == "invalid":
            reasons.append("malformed_job_url")
        if apply_url["category"] == "invalid":
            reasons.append("malformed_apply_url")
    elif "blocked" in categories:
        status = "blocked"
        confidence = 0.85
        if job_url["category"] == "blocked":
            reasons.append("job_url_blocked")
        if apply_url["category"] == "blocked":
            reasons.append("apply_url_blocked")
    else:
        status = "unknown"
        confidence = 0.75 if "reachable" in categories else 0.55
        if job_url["category"] == "reachable":
            reasons.append("job_url_reachable")
        if apply_url["category"] == "reachable":
            reasons.append("apply_url_reachable")
        if job_url["category"] == "missing":
            reasons.append("job_url_missing")
        if apply_url["category"] == "missing":
            reasons.append("apply_url_missing")
        if job_url["category"] == "transient_failure":
            reasons.append("job_url_transient_failure")
        if apply_url["category"] == "transient_failure":
            reasons.append("apply_url_transient_failure")
        if not reasons:
            reasons.append("url_reachability_unknown")

    return {
        "job_key": clean_text(job.get("job_key")),
        "scan_run_id": clean_text(job.get("scan_run_id")),
        "content_hash": clean_text(job.get("content_hash")) or None,
        "verification_status": status,
        "confidence": confidence,
        "reasons": reasons,
        "signals": {
            "checker": "url_reachability",
            "schema_version": URL_VERIFIER_SCHEMA_VERSION,
            "network_checked": True,
            "open_closed_classified": False,
            "blocked": "blocked" in categories,
            "transient_failure": "transient_failure" in categories,
            **_prefixed_signals("job_url", job_url),
            **_prefixed_signals("apply_url", apply_url),
        },
        "evidence": {
            "checker": "url_reachability",
            "schema_version": URL_VERIFIER_SCHEMA_VERSION,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "job_url": job_url,
            "apply_url": apply_url,
            "note": "Phase 3C checks reachability only; open/closed classification is Phase 3D.",
        },
        "url": clean_text(job.get("url")),
        "apply_url": clean_text(job.get("apply_url")),
        "url_status_code": int(job_url.get("status_code") or 0),
        "apply_url_status_code": int(apply_url.get("status_code") or 0),
        "final_url": clean_text(job_url.get("final_url")),
        "final_apply_url": clean_text(apply_url.get("final_url")),
        "error": "; ".join(
            item for item in [
                clean_text(job_url.get("error")),
                clean_text(apply_url.get("error")),
            ] if item
        ),
    }


def verify_urls(jobs: Sequence[Mapping[str, Any]], *, sleep_seconds: float = 0.2) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, job in enumerate(jobs):
        results.append(verify_job_urls(job))
        if sleep_seconds > 0 and index < len(jobs) - 1:
            time.sleep(sleep_seconds)
    return results


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(clean_text(item.get("verification_status")) for item in results)
    reason_counts = Counter(reason for item in results for reason in item.get("reasons", []))
    return {
        "total_jobs": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "top_reasons": dict(reason_counts.most_common(20)),
    }


def main() -> int:
    args = parse_args()
    if not 1 <= args.limit <= 10000:
        raise SystemExit("--limit must be between 1 and 10000")
    if args.sleep < 0:
        raise SystemExit("--sleep must be >= 0")

    run_id, jobs = load_jobs(args.run_id, company=args.company, limit=args.limit)
    results = verify_urls(jobs, sleep_seconds=args.sleep)
    output: dict[str, Any] = {
        "scan_run_id": run_id,
        "verification_kind": "url_reachability",
        "dry_run": args.dry_run,
        "summary": summarize(results),
    }
    if args.dry_run:
        output["rows"] = results[:50]
    else:
        persisted = persist_verification_results(
            results,
            scan_run_id=run_id,
            verification_kind="url_reachability",
            config={
                "checker": "url_reachability",
                "schema_version": URL_VERIFIER_SCHEMA_VERSION,
                "limit": args.limit,
                "company": args.company or "",
                "network_checked": True,
                "browser_rendered": False,
                "open_closed_classified": False,
            },
        )
        if persisted.status != "persisted":
            detail = persisted.error or persisted.skipped_reason or persisted.status
            raise RuntimeError(f"url reachability persistence failed: {detail}")
        output["verification_run_id"] = persisted.verification_run_id
        output["verifications_inserted"] = persisted.verifications_inserted

    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
