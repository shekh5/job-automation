#!/usr/bin/env python3
"""Phase 3D open/closed classification for persisted ATS jobs.

This classifier does not crawl. It combines the selected scan membership with
the latest Phase 3B local-quality result and Phase 3C URL-reachability result.
It is intentionally conservative: a job is closed only when it is absent from
the selected source scan and has repeated missing URL evidence.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ats_common import clean_text
from ats_supabase import _database_url, _ensure_schema, _load_psycopg, persist_verification_results

OPEN_CLOSED_SCHEMA_VERSION = 1
REPEATED_MISSING_THRESHOLD = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="ATS scan run UUID; defaults to latest combined scan")
    parser.add_argument("--company", help="Optional exact company filter")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing verification rows")
    return parser.parse_args()


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return default


def _rows(cursor) -> list[dict[str, Any]]:
    columns = [item.name for item in cursor.description]
    rows: list[dict[str, Any]] = []
    for row in cursor.fetchall():
        item = dict(zip(columns, row, strict=True))
        for key in ("local_reasons", "url_reasons", "closed_reasons"):
            item[key] = _json_value(item.get(key), [])
        for key in ("local_signals", "url_signals", "closed_signals"):
            item[key] = _json_value(item.get(key), {})
        rows.append(item)
    return rows


def _latest_combined_run_id(cursor) -> str:
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
    return str(result[0])


def load_classification_inputs(
    run_id: str | None = None,
    *,
    company: str | None = None,
    limit: int = 2000,
) -> tuple[str, list[dict[str, Any]]]:
    database_url = _database_url()
    if not database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is not configured")

    psycopg = _load_psycopg()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            _ensure_schema(cursor)
            selected_run_id = run_id or _latest_combined_run_id(cursor)

            conditions = ["true"]
            params: list[Any] = [selected_run_id]
            if company:
                conditions.append("j.company = %s")
                params.append(company)
            params.extend([selected_run_id, limit])

            cursor.execute(
                f"""
                select
                  %s::uuid as scan_run_id,
                  j.job_key,
                  coalesce(rj.content_hash, j.current_content_hash) as content_hash,
                  j.provider as source,
                  j.source_id,
                  j.company,
                  j.title,
                  j.location,
                  j.url,
                  j.apply_url,
                  (rj.job_key is not null) as present_in_scan,
                  local.verification_status as local_status,
                  local.reasons as local_reasons,
                  local.signals as local_signals,
                  urlv.verification_status as url_status,
                  urlv.reasons as url_reasons,
                  urlv.signals as url_signals,
                  coalesce(history.url_missing_count, 0) as url_missing_count,
                  coalesce(history.url_blocked_count, 0) as url_blocked_count,
                  coalesce(history.url_transient_count, 0) as url_transient_count,
                  closedv.verification_status as closed_status,
                  closedv.reasons as closed_reasons,
                  closedv.signals as closed_signals
                from ats_jobs j
                left join ats_run_jobs rj
                  on rj.job_key = j.job_key and rj.run_id = %s::uuid
                left join lateral (
                  select jv.verification_status, jv.reasons, jv.signals
                  from ats_job_verifications jv
                  join ats_verification_runs vr on vr.id = jv.verification_run_id
                  where jv.job_key = j.job_key
                    and vr.verification_kind = 'local_quality'
                  order by jv.checked_at desc, vr.started_at desc
                  limit 1
                ) local on true
                left join lateral (
                  select jv.verification_status, jv.reasons, jv.signals
                  from ats_job_verifications jv
                  join ats_verification_runs vr on vr.id = jv.verification_run_id
                  where jv.job_key = j.job_key
                    and vr.verification_kind = 'url_reachability'
                  order by jv.checked_at desc, vr.started_at desc
                  limit 1
                ) urlv on true
                left join lateral (
                  select jv.verification_status, jv.reasons, jv.signals
                  from ats_job_verifications jv
                  join ats_verification_runs vr on vr.id = jv.verification_run_id
                  where jv.job_key = j.job_key
                    and vr.verification_kind = 'closed_text_signals'
                  order by jv.checked_at desc, vr.started_at desc
                  limit 1
                ) closedv on true
                left join lateral (
                  select
                    count(*) filter (
                      where jv.reasons ?| array['job_url_missing', 'apply_url_missing']
                    ) as url_missing_count,
                    count(*) filter (
                      where jv.reasons ?| array['job_url_blocked', 'apply_url_blocked']
                    ) as url_blocked_count,
                    count(*) filter (
                      where jv.reasons ?| array['job_url_transient_failure', 'apply_url_transient_failure']
                    ) as url_transient_count
                  from ats_job_verifications jv
                  join ats_verification_runs vr on vr.id = jv.verification_run_id
                  where jv.job_key = j.job_key
                    and vr.verification_kind = 'url_reachability'
                ) history on true
                where {' and '.join(conditions)}
                order by (rj.job_key is not null) desc, j.company, j.title
                limit %s
                """,
                params,
            )
            jobs = _rows(cursor)
    return selected_run_id, jobs


def _has_signal(signals: Mapping[str, Any], *names: str) -> bool:
    return any(bool(signals.get(name)) for name in names)


def _has_reason(reasons: Sequence[Any], *names: str) -> bool:
    reason_set = {clean_text(reason) for reason in reasons}
    return any(name in reason_set for name in names)


def classify_open_closed(job: Mapping[str, Any], *, checked_at: datetime | None = None) -> dict[str, Any]:
    checked_at = checked_at or datetime.now(timezone.utc)
    present_in_scan = bool(job.get("present_in_scan"))
    local_status = clean_text(job.get("local_status"))
    url_status = clean_text(job.get("url_status"))
    local_reasons = [clean_text(reason) for reason in job.get("local_reasons") or [] if clean_text(reason)]
    url_reasons = [clean_text(reason) for reason in job.get("url_reasons") or [] if clean_text(reason)]
    closed_reasons = [clean_text(reason) for reason in job.get("closed_reasons") or [] if clean_text(reason)]
    local_signals = _json_value(job.get("local_signals"), {})
    url_signals = _json_value(job.get("url_signals"), {})
    closed_signals = _json_value(job.get("closed_signals"), {})
    missing_count = int(job.get("url_missing_count") or 0)
    blocked_count = int(job.get("url_blocked_count") or 0)
    transient_count = int(job.get("url_transient_count") or 0)
    
    explicit_closed_text = _has_signal(closed_signals, "closed_text_found") or _has_reason(closed_reasons, "closed_text_signal_found")

    reachable = _has_signal(url_signals, "job_url_reachable", "apply_url_reachable") or _has_reason(
        url_reasons,
        "job_url_reachable",
        "apply_url_reachable",
    )
    missing = _has_signal(url_signals, "job_url_missing", "apply_url_missing") or _has_reason(
        url_reasons,
        "job_url_missing",
        "apply_url_missing",
    )
    blocked = (
        url_status == "blocked"
        or blocked_count > 0
        or _has_signal(url_signals, "blocked", "job_url_blocked", "apply_url_blocked")
        or _has_reason(url_reasons, "job_url_blocked", "apply_url_blocked")
    )
    transient = _has_signal(url_signals, "transient_failure", "job_url_transient_failure", "apply_url_transient_failure") or _has_reason(
        url_reasons,
        "job_url_transient_failure",
        "apply_url_transient_failure",
    )

    reasons: list[str]
    status: str
    confidence: float

    if local_status == "invalid" or url_status == "invalid":
        status = "invalid"
        confidence = 0.95
        reasons = ["invalid_job_data", *(local_reasons or url_reasons)]
    elif blocked:
        status = "blocked"
        confidence = 0.85
        reasons = ["url_access_blocked"]
        if blocked_count:
            reasons.append(f"url_blocked_count_{blocked_count}")
        reasons.extend(reason for reason in url_reasons if reason not in reasons)
    elif explicit_closed_text and not present_in_scan:
        status = "closed"
        confidence = 0.95
        reasons = ["explicit_closed_text_signal", "absent_from_selected_scan"]
        if closed_reasons:
            reasons.extend(reason for reason in closed_reasons if reason not in reasons)
    elif explicit_closed_text and missing_count >= 2:
        status = "closed"
        confidence = 0.95
        reasons = ["explicit_closed_text_signal", f"repeated_missing_url_count_{missing_count}"]
        if closed_reasons:
            reasons.extend(reason for reason in closed_reasons if reason not in reasons)
    elif not present_in_scan and missing_count >= REPEATED_MISSING_THRESHOLD:
        status = "closed"
        confidence = 0.9
        reasons = [
            "absent_from_selected_scan",
            f"repeated_missing_url_count_{missing_count}",
        ]
    elif present_in_scan and reachable and not explicit_closed_text:
        status = "open"
        confidence = 0.9
        reasons = ["present_in_selected_scan", "url_reachable"]
    elif present_in_scan and missing:
        status = "unknown"
        confidence = 0.55
        reasons = ["present_in_selected_scan", "single_or_conflicting_missing_url_not_enough_to_close"]
        if missing_count:
            reasons.append(f"url_missing_count_{missing_count}")
    elif not present_in_scan and missing:
        status = "unknown"
        confidence = 0.6
        reasons = ["absent_from_selected_scan", "missing_url_below_close_threshold"]
        if missing_count:
            reasons.append(f"url_missing_count_{missing_count}")
    elif transient or transient_count:
        status = "unknown"
        confidence = 0.45
        reasons = ["transient_url_failure"]
        if transient_count:
            reasons.append(f"url_transient_count_{transient_count}")
    elif present_in_scan:
        status = "unknown"
        confidence = 0.65
        reasons = ["present_in_selected_scan_without_url_reachability"]
    else:
        status = "unknown"
        confidence = 0.5
        reasons = ["absent_from_selected_scan_without_close_evidence"]

    return {
        "job_key": clean_text(job.get("job_key")),
        "scan_run_id": clean_text(job.get("scan_run_id")),
        "content_hash": clean_text(job.get("content_hash")) or None,
        "verification_status": status,
        "confidence": confidence,
        "reasons": reasons,
        "signals": {
            "checker": "open_closed_classification",
            "schema_version": OPEN_CLOSED_SCHEMA_VERSION,
            "network_checked": False,
            "present_in_scan": present_in_scan,
            "local_status": local_status,
            "url_status": url_status,
            "url_reachable": reachable,
            "url_missing": missing,
            "url_blocked": blocked,
            "url_transient_failure": transient,
            "url_missing_count": missing_count,
            "url_blocked_count": blocked_count,
            "url_transient_count": transient_count,
            "closed_requires_absence_and_repeated_missing": True,
            "repeated_missing_threshold": REPEATED_MISSING_THRESHOLD,
        },
        "evidence": {
            "checker": "open_closed_classification",
            "schema_version": OPEN_CLOSED_SCHEMA_VERSION,
            "checked_at": checked_at.isoformat(),
            "source_membership": {
                "scan_run_id": clean_text(job.get("scan_run_id")),
                "present_in_scan": present_in_scan,
            },
            "local_quality": {
                "status": local_status,
                "reasons": local_reasons,
                "signals": local_signals,
            },
            "url_reachability": {
                "status": url_status,
                "reasons": url_reasons,
                "signals": url_signals,
                "missing_count": missing_count,
                "blocked_count": blocked_count,
                "transient_count": transient_count,
            },
        },
        "url": clean_text(job.get("url")),
        "apply_url": clean_text(job.get("apply_url")),
        "url_status_code": int(url_signals.get("job_url_status_code") or 0),
        "apply_url_status_code": int(url_signals.get("apply_url_status_code") or 0),
        "final_url": clean_text(url_signals.get("job_url_final_url")),
        "final_apply_url": clean_text(url_signals.get("apply_url_final_url")),
        "error": "",
    }


def classify_jobs(jobs: Sequence[Mapping[str, Any]], checked_at: datetime | None = None) -> list[dict[str, Any]]:
    checked_at = checked_at or datetime.now(timezone.utc)
    return [classify_open_closed(job, checked_at=checked_at) for job in jobs]


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

    run_id, jobs = load_classification_inputs(args.run_id, company=args.company, limit=args.limit)
    results = classify_jobs(jobs)
    output: dict[str, Any] = {
        "scan_run_id": run_id,
        "verification_kind": "open_closed_classification",
        "dry_run": args.dry_run,
        "summary": summarize(results),
    }
    if args.dry_run:
        output["rows"] = results[:50]
    else:
        persisted = persist_verification_results(
            results,
            scan_run_id=run_id,
            verification_kind="open_closed_classification",
            config={
                "checker": "open_closed_classification",
                "schema_version": OPEN_CLOSED_SCHEMA_VERSION,
                "limit": args.limit,
                "company": args.company or "",
                "network_checked": False,
                "closed_requires_absence_and_repeated_missing": True,
                "repeated_missing_threshold": REPEATED_MISSING_THRESHOLD,
            },
        )
        if persisted.status != "persisted":
            detail = persisted.error or persisted.skipped_reason or persisted.status
            raise RuntimeError(f"open/closed classification persistence failed: {detail}")
        output["verification_run_id"] = persisted.verification_run_id
        output["verifications_inserted"] = persisted.verifications_inserted

    print(json.dumps(output, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
