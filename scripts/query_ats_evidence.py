#!/usr/bin/env python3
"""Query Phase 2 ATS evidence and decision dashboards."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ats_supabase import _database_url, _load_psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="Run UUID; defaults to the latest combined run")
    parser.add_argument("--view", choices=("jobs", "fetches"), default="jobs")
    parser.add_argument("--decision", choices=("accepted", "rejected"))
    parser.add_argument("--status", choices=("new", "changed", "unchanged", "imported"))
    parser.add_argument("--outcome", choices=("success", "error"))
    parser.add_argument("--limit", type=int, default=50)
    return parser.parse_args()


def _rows(cursor) -> list[dict[str, Any]]:
    columns = [item.name for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def main() -> int:
    args = parse_args()
    if not 1 <= args.limit <= 500:
        raise SystemExit("--limit must be between 1 and 500")
    database_url = _database_url()
    if not database_url:
        raise SystemExit("SUPABASE_DATABASE_URL is not configured")

    psycopg = _load_psycopg()
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            run_id = args.run_id
            if not run_id:
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
                    raise SystemExit("No combined ATS run exists")
                run_id = str(result[0])

            if args.view == "jobs":
                conditions = ["run_id = %s"]
                params: list[Any] = [run_id]
                if args.decision:
                    conditions.append("decision = %s")
                    params.append(args.decision)
                if args.status:
                    conditions.append("observation_status = %s")
                    params.append(args.status)
                params.append(args.limit)
                cursor.execute(
                    f"""
                    select job_key, provider, company, title, location, url,
                           observation_status, decision, reasons, signals, content_hash
                    from ats_job_evidence_dashboard
                    where {' and '.join(conditions)}
                    order by company, title
                    limit %s
                    """,
                    params,
                )
                rows = _rows(cursor)
                cursor.execute(
                    """
                    select observation_status, decision, count(*)
                    from ats_job_evidence_dashboard
                    where run_id = %s
                    group by observation_status, decision
                    order by observation_status, decision
                    """,
                    (run_id,),
                )
                summary = [
                    {"observation_status": row[0], "decision": row[1], "count": row[2]}
                    for row in cursor.fetchall()
                ]
            else:
                conditions = ["run_id = %s"]
                params = [run_id]
                if args.outcome:
                    conditions.append("outcome = %s")
                    params.append(args.outcome)
                params.append(args.limit)
                cursor.execute(
                    f"""
                    select company, provider, source_slug, url, method, outcome,
                           status_code, attempt_count, elapsed_ms, error, evidence_hash
                    from ats_fetch_evidence_dashboard
                    where {' and '.join(conditions)}
                    order by company, url
                    limit %s
                    """,
                    params,
                )
                rows = _rows(cursor)
                cursor.execute(
                    """
                    select outcome, status_code, count(*)
                    from ats_fetch_evidence_dashboard
                    where run_id = %s
                    group by outcome, status_code
                    order by outcome, status_code
                    """,
                    (run_id,),
                )
                summary = [
                    {"outcome": row[0], "status_code": row[1], "count": row[2]}
                    for row in cursor.fetchall()
                ]

    print(json.dumps({"run_id": run_id, "view": args.view, "summary": summary, "rows": rows}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
