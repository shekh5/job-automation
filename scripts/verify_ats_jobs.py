#!/usr/bin/env python3
"""Phase 3B local data-quality verification for persisted ATS jobs.

This verifier intentionally performs no network requests. It checks only the
job records already stored in Postgres and writes results into the Phase 3A
verification tables.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlsplit

from ats_common import PROVIDERS, clean_text, parse_datetime
from ats_supabase import _database_url, _ensure_schema, _load_psycopg, persist_verification_results

LOCAL_VERIFIER_SCHEMA_VERSION = 1
REQUIRED_TEXT_FIELDS = (
    "company",
    "source",
    "source_id",
    "title",
    "location",
    "url",
    "apply_url",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="ATS scan run UUID; defaults to latest combined scan")
    parser.add_argument("--company", help="Optional exact company filter")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing verification rows")
    return parser.parse_args()


def valid_http_url(value: Any) -> bool:
    text = clean_text(value)
    if not text or any(char.isspace() for char in text):
        return False
    parsed = urlsplit(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _casefold_key(*values: Any) -> tuple[str, ...]:
    return tuple(clean_text(value).casefold() for value in values)


def _staleness_signal(job: Mapping[str, Any], checked_at: datetime) -> tuple[bool, str]:
    try:
        freshness_days = int(job.get("freshness_days") or 14)
    except (TypeError, ValueError):
        freshness_days = 14
    timestamps = [
        parse_datetime(job.get("updated_at"), now=checked_at),
        parse_datetime(job.get("first_published"), now=checked_at),
    ]
    observed = next((item for item in timestamps if item is not None), None)
    if observed is None:
        return False, ""
    age_days = (checked_at - observed).days
    return age_days > freshness_days, f"{age_days}d/{freshness_days}d"


def verify_job_locally(
    job: Mapping[str, Any],
    *,
    duplicate_source_count: int = 1,
    duplicate_posting_count: int = 1,
    checked_at: datetime | None = None,
) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(timezone.utc)
    reasons: list[str] = []
    warnings: list[str] = []
    invalid_reasons: list[str] = []

    missing_fields = [field for field in REQUIRED_TEXT_FIELDS if not clean_text(job.get(field))]
    invalid_reasons.extend(f"missing_{field}" for field in missing_fields)

    provider = clean_text(job.get("source"))
    if provider not in PROVIDERS:
        invalid_reasons.append("unknown_provider")

    schema_version = job.get("schema_version")
    if schema_version not in (1, "1", None):
        invalid_reasons.append("unsupported_schema_version")

    if not valid_http_url(job.get("url")):
        invalid_reasons.append("malformed_job_url")
    if not valid_http_url(job.get("apply_url")):
        invalid_reasons.append("malformed_apply_url")

    locations = job.get("locations")
    if locations is not None and not isinstance(locations, list):
        invalid_reasons.append("locations_not_array")
    elif not locations:
        warnings.append("empty_locations_array")

    try:
        freshness_days = int(job.get("freshness_days") or 0)
    except (TypeError, ValueError):
        freshness_days = 0
    if freshness_days < 1:
        invalid_reasons.append("invalid_freshness_days")

    for date_field in ("updated_at", "first_published"):
        value = clean_text(job.get(date_field))
        if value and parse_datetime(value, now=checked_at) is None:
            invalid_reasons.append(f"malformed_{date_field}")

    title = clean_text(job.get("title"))
    if title and len(title) < 3:
        invalid_reasons.append("title_too_short")
    if not clean_text(job.get("description")):
        warnings.append("empty_description")
    if clean_text(job.get("location")).casefold() in {"not listed", "unknown", "n/a"}:
        warnings.append("location_not_specific")

    stale, stale_detail = _staleness_signal(job, checked_at)
    if stale:
        warnings.append("stale_date_signal")

    if duplicate_source_count > 1:
        invalid_reasons.append("duplicate_provider_source_id")
    if duplicate_posting_count > 1:
        warnings.append("duplicate_company_title_apply_url")

    job_key = clean_text(job.get("job_key")) or f"{provider}:{clean_text(job.get('source_id'))}"
    expected_job_key = f"{provider}:{clean_text(job.get('source_id'))}" if provider and clean_text(job.get("source_id")) else ""
    if job_key and expected_job_key and job_key != expected_job_key:
        invalid_reasons.append("job_key_source_mismatch")

    status = "invalid" if invalid_reasons else "unknown"
    if invalid_reasons:
        reasons = invalid_reasons
        confidence = 0.95
    elif warnings:
        reasons = warnings
        confidence = 0.65
    else:
        reasons = ["local_quality_checks_passed"]
        confidence = 0.8

    return {
        "job_key": job_key,
        "scan_run_id": clean_text(job.get("scan_run_id")),
        "content_hash": clean_text(job.get("content_hash")) or None,
        "verification_status": status,
        "confidence": confidence,
        "reasons": reasons,
        "signals": {
            "checker": "local_quality",
            "schema_version": LOCAL_VERIFIER_SCHEMA_VERSION,
            "has_required_fields": not missing_fields,
            "known_provider": provider in PROVIDERS,
            "valid_job_url": valid_http_url(job.get("url")),
            "valid_apply_url": valid_http_url(job.get("apply_url")),
            "has_locations_array": isinstance(locations, list),
            "has_description": bool(clean_text(job.get("description"))),
            "specific_location": "location_not_specific" not in warnings,
            "stale_date_signal": stale,
            "stale_detail": stale_detail,
            "duplicate_provider_source_id": duplicate_source_count > 1,
            "duplicate_company_title_apply_url": duplicate_posting_count > 1,
            "network_checked": False,
        },
        "evidence": {
            "checker": "local_quality",
            "schema_version": LOCAL_VERIFIER_SCHEMA_VERSION,
            "checked_at": checked_at.isoformat(),
            "checked_fields": [
                *REQUIRED_TEXT_FIELDS,
                "locations",
                "description",
                "updated_at",
                "first_published",
                "freshness_days",
            ],
        },
        "url": clean_text(job.get("url")),
        "apply_url": clean_text(job.get("apply_url")),
        "url_status_code": 0,
        "apply_url_status_code": 0,
        "final_url": "",
        "final_apply_url": "",
        "error": "; ".join(invalid_reasons),
    }


def verify_jobs_locally(jobs: Sequence[Mapping[str, Any]], checked_at: datetime | None = None) -> list[dict[str, Any]]:
    checked_at = checked_at or datetime.now(timezone.utc)
    source_counts = Counter(
        _casefold_key(job.get("source"), job.get("source_id"))
        for job in jobs
        if clean_text(job.get("source")) or clean_text(job.get("source_id"))
    )
    posting_counts = Counter(
        _casefold_key(job.get("company"), job.get("title"), job.get("apply_url"))
        for job in jobs
        if clean_text(job.get("company")) or clean_text(job.get("title")) or clean_text(job.get("apply_url"))
    )
    return [
        verify_job_locally(
            job,
            duplicate_source_count=source_counts.get(_casefold_key(job.get("source"), job.get("source_id")), 1),
            duplicate_posting_count=posting_counts.get(_casefold_key(job.get("company"), job.get("title"), job.get("apply_url")), 1),
            checked_at=checked_at,
        )
        for job in jobs
    ]


def _rows(cursor) -> list[dict[str, Any]]:
    columns = [item.name for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def load_jobs(run_id: str | None = None, *, company: str | None = None, limit: int = 2000) -> tuple[str, list[dict[str, Any]]]:
    database_url = _database_url()
    if not database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is not configured")
    psycopg = _load_psycopg()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _ensure_schema(cursor)
            selected_run_id = run_id
            if not selected_run_id:
                cursor.execute(
                    """
                    select id from ats_scan_runs
                    where scan_kind = 'combined'
                    order by persisted_at desc
                    limit 1
                    """
                )
                result = cursor.fetchone()
                if not result:
                    raise RuntimeError("No combined ATS run exists")
                selected_run_id = str(result[0])

            conditions = ["rj.run_id = %s"]
            params: list[Any] = [selected_run_id]
            if company:
                conditions.append("j.company = %s")
                params.append(company)
            params.append(limit)
            cursor.execute(
                f"""
                select
                  rj.run_id as scan_run_id,
                  rj.job_key,
                  coalesce(rj.content_hash, j.current_content_hash) as content_hash,
                  j.provider as source,
                  j.source_id,
                  j.company,
                  j.title,
                  j.location,
                  j.locations,
                  j.department,
                  j.team,
                  j.employment_type,
                  j.workplace_type,
                  j.description,
                  j.url,
                  j.apply_url,
                  j.freshness_days,
                  j.updated_at,
                  j.first_published,
                  1 as schema_version
                from ats_run_jobs rj
                join ats_jobs j on j.job_key = rj.job_key
                where {' and '.join(conditions)}
                order by j.company, j.title
                limit %s
                """,
                params,
            )
            jobs = _rows(cursor)
    return selected_run_id, jobs


def summarize(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(clean_text(item.get("verification_status")) for item in results)
    reason_counts = Counter(
        reason
        for item in results
        for reason in item.get("reasons", [])
    )
    return {
        "total_jobs": len(results),
        "status_counts": dict(sorted(status_counts.items())),
        "top_reasons": dict(reason_counts.most_common(20)),
    }


def main() -> int:
    args = parse_args()
    if not 1 <= args.limit <= 10000:
        raise SystemExit("--limit must be between 1 and 10000")

    run_id, jobs = load_jobs(args.run_id, company=args.company, limit=args.limit)
    results = verify_jobs_locally(jobs)
    summary = summarize(results)
    output: dict[str, Any] = {
        "scan_run_id": run_id,
        "verification_kind": "local_quality",
        "dry_run": args.dry_run,
        "summary": summary,
    }
    if args.dry_run:
        output["rows"] = results[:50]
    else:
        persisted = persist_verification_results(
            results,
            scan_run_id=run_id,
            verification_kind="local_quality",
            config={
                "checker": "local_quality",
                "schema_version": LOCAL_VERIFIER_SCHEMA_VERSION,
                "limit": args.limit,
                "company": args.company or "",
                "network_checked": False,
            },
        )
        if persisted.status != "persisted":
            detail = persisted.error or persisted.skipped_reason or persisted.status
            raise RuntimeError(f"local verification persistence failed: {detail}")
        output["verification_run_id"] = persisted.verification_run_id
        output["verifications_inserted"] = persisted.verifications_inserted

    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
