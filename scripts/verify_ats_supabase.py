#!/usr/bin/env python3
"""Apply the ATS schema and verify Supabase persistence end to end."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ats_supabase import _database_url, _load_psycopg, persist_report


def main() -> int:
    verification_id = uuid4().hex
    source_id = f"phase1-verification-{verification_id}"
    job_key = f"greenhouse:{source_id}"
    now = datetime.now(timezone.utc).isoformat()
    job = {
        "schema_version": 1,
        "company": "Phase 1 Verification",
        "source": "greenhouse",
        "source_id": source_id,
        "title": "Persistence Verification",
        "location": "Remote",
        "locations": ["Remote"],
        "department": "Engineering",
        "team": "Data",
        "employment_type": "test",
        "workplace_type": "remote",
        "description": "Temporary row used to verify ATS persistence.",
        "updated_at": now,
        "first_published": now,
        "freshness_days": 14,
        "url": f"https://example.invalid/jobs/{source_id}",
        "apply_url": f"https://example.invalid/jobs/{source_id}",
    }
    report = {
        "schema_version": 2,
        "generated_at": now,
        "freshness_days": 14,
        "strategy": "Phase 1 live persistence verification",
        "total_raw_jobs": 1,
        "total_current_jobs": 1,
        "total_dropped_jobs": 0,
        "checked": [],
        "errors": [],
        "source_repairs": [],
        "matches": [job],
    }

    raw_job = {"id": source_id, "title": job["title"], "location": job["location"]}
    fetch_evidence = [{
        "company": job["company"],
        "provider": job["source"],
        "source_slug": "phase1-verification",
        "url": "https://example.invalid/api/jobs",
        "method": "GET",
        "request_payload": None,
        "response_payload": {"jobs": [raw_job]},
        "status_code": 200,
        "outcome": "success",
        "attempt_count": 1,
        "elapsed_ms": 1,
        "fetched_at": now,
        "error": "",
    }]
    result = persist_report(
        report,
        [job],
        scan_kind="verification",
        fetch_evidence=fetch_evidence,
        job_evidence=[{"job_key": job_key, "normalized_job": job, "raw_job": raw_job}],
        job_evaluations=[{
            "job_key": job_key,
            "decision": "accepted",
            "reasons": ["verification"],
            "signals": {"verification": True},
        }],
    )
    if result.status != "persisted" or not result.run_id:
        detail = result.error or result.skipped_reason or result.status
        raise RuntimeError(f"persistence verification failed: {detail}")

    psycopg = _load_psycopg()
    database_url = _database_url()
    if not database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is not configured")

    verification_run_id = None
    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                select
                  exists(select 1 from ats_scan_runs where id = %s),
                  exists(select 1 from ats_jobs where job_key = %s),
                  exists(select 1 from ats_run_jobs where run_id = %s and job_key = %s),
                  exists(select 1 from ats_job_versions where job_key = %s),
                  exists(select 1 from ats_job_evaluations where run_id = %s and job_key = %s),
                  exists(select 1 from ats_fetch_observations where run_id = %s)
                """,
                (
                    result.run_id,
                    job_key,
                    result.run_id,
                    job_key,
                    job_key,
                    result.run_id,
                    job_key,
                    result.run_id,
                ),
            )
            checks = cursor.fetchone()
            if checks != (True, True, True, True, True, True):
                raise RuntimeError(f"write/read verification failed: {checks}")

            cursor.execute(
                """
                select
                  to_regclass('public.ats_verification_runs') is not null,
                  to_regclass('public.ats_job_verifications') is not null,
                  to_regclass('public.ats_job_verification_latest') is not null,
                  to_regclass('public.ats_job_verification_dashboard') is not null,
                  coalesce((
                    select 'security_invoker=true' = any(reloptions)
                    from pg_class
                    where oid = to_regclass('public.ats_job_verification_latest')
                  ), false),
                  coalesce((
                    select 'security_invoker=true' = any(reloptions)
                    from pg_class
                    where oid = to_regclass('public.ats_job_verification_dashboard')
                  ), false)
                """
            )
            phase3a_checks = cursor.fetchone()
            if phase3a_checks != (True, True, True, True, True, True):
                raise RuntimeError(f"phase 3A verification schema check failed: {phase3a_checks}")

            cursor.execute(
                """
                insert into ats_verification_runs (
                  scan_run_id, verification_kind, status, completed_at,
                  total_jobs, status_counts, config
                )
                values (
                  %s, 'job', 'completed', now(), 1,
                  '{"open": 1}'::jsonb,
                  '{"verification": "live-schema-check"}'::jsonb
                )
                returning id
                """,
                (result.run_id,),
            )
            verification_run_id = cursor.fetchone()[0]
            cursor.execute(
                """
                insert into ats_job_verifications (
                  verification_run_id, job_key, scan_run_id, content_hash,
                  verification_status, confidence, reasons, signals, evidence,
                  url, apply_url, url_status_code, apply_url_status_code
                )
                select
                  %s, rj.job_key, rj.run_id, rj.content_hash,
                  'open', 1,
                  '["live_schema_check"]'::jsonb,
                  '{"reachable": true}'::jsonb,
                  '{"source": "verify_ats_supabase"}'::jsonb,
                  j.url, j.apply_url, 200, 200
                from ats_run_jobs rj
                join ats_jobs j on j.job_key = rj.job_key
                where rj.run_id = %s and rj.job_key = %s
                """,
                (verification_run_id, result.run_id, job_key),
            )
            cursor.execute(
                """
                select exists(
                  select 1
                  from ats_job_verification_dashboard
                  where verification_run_id = %s
                    and job_key = %s
                    and verification_status = 'open'
                    and confidence = 1
                )
                """,
                (verification_run_id, job_key),
            )
            if cursor.fetchone() != (True,):
                raise RuntimeError("phase 3A verification dashboard readback failed")

            cursor.execute(
                "select evidence_hash from ats_fetch_observations where run_id = %s",
                (result.run_id,),
            )
            fetch_hashes = [row[0] for row in cursor.fetchall() if row[0]]
            if verification_run_id:
                cursor.execute("delete from ats_verification_runs where id = %s", (verification_run_id,))
            cursor.execute("delete from ats_scan_runs where id = %s", (result.run_id,))
            cursor.execute("delete from ats_jobs where job_key = %s", (job_key,))
            if fetch_hashes:
                cursor.execute("delete from ats_fetch_payloads where evidence_hash = any(%s)", (fetch_hashes,))
        connection.commit()

    print("ATS Supabase verification passed: schema, evidence, decisions, Phase 3A verification tables, write, read, and cleanup succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
