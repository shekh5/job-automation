#!/usr/bin/env python3
"""Query Phase 3 ATS job verification dashboards."""

from __future__ import annotations

import argparse
import json
from typing import Any

from ats_supabase import _database_url, _load_psycopg


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verification-run-id", help="Verification run UUID; defaults to latest verification run")
    parser.add_argument("--scan-run-id", help="Optional ATS scan run UUID filter")
    parser.add_argument("--status", choices=("open", "closed", "unknown", "invalid", "blocked"))
    parser.add_argument("--company", help="Optional exact company filter")
    parser.add_argument("--latest", action="store_true", help="Query latest verification per job instead of one run")
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
            verification_run_id = args.verification_run_id
            if not args.latest and not verification_run_id:
                cursor.execute(
                    """
                    select id from ats_verification_runs
                    order by started_at desc
                    limit 1
                    """
                )
                result = cursor.fetchone()
                if not result:
                    raise SystemExit("No ATS verification run exists")
                verification_run_id = str(result[0])

            table_name = "ats_job_verification_latest" if args.latest else "ats_job_verification_dashboard"
            conditions: list[str] = []
            params: list[Any] = []
            if verification_run_id:
                conditions.append("verification_run_id = %s")
                params.append(verification_run_id)
            if args.scan_run_id:
                conditions.append("(verification_scan_run_id = %s or job_scan_run_id = %s)")
                params.extend([args.scan_run_id, args.scan_run_id])
            if args.status:
                conditions.append("verification_status = %s")
                params.append(args.status)
            if args.company:
                conditions.append("company = %s")
                params.append(args.company)

            where_sql = f"where {' and '.join(conditions)}" if conditions else ""
            params.append(args.limit)
            cursor.execute(
                f"""
                select
                  verification_run_id, job_key, provider, company, title, location,
                  url, apply_url, verification_status, confidence, reasons, signals,
                  url_status_code, apply_url_status_code, error, checked_at
                from {table_name}
                {where_sql}
                order by checked_at desc, company, title
                limit %s
                """,
                params,
            )
            rows = _rows(cursor)

            summary_params = params[:-1]
            cursor.execute(
                f"""
                select verification_status, count(*)
                from {table_name}
                {where_sql}
                group by verification_status
                order by verification_status
                """,
                summary_params,
            )
            summary = [
                {"verification_status": row[0], "count": row[1]}
                for row in cursor.fetchall()
            ]

    print(json.dumps({
        "verification_run_id": verification_run_id,
        "latest": args.latest,
        "summary": summary,
        "rows": rows,
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
