#!/usr/bin/env python3
"""Optional Postgres persistence for ATS scan results."""

from __future__ import annotations

import json
import hashlib
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence
from urllib.parse import quote, urlsplit, urlunsplit

from ats_crawl_policy import DEFAULT_CRAWL_POLICY

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "data" / "migrations"
MIGRATION_PATH = MIGRATIONS_DIR / "001_ats_phase1.sql"
SUPPORTED_ENV_VARS = ("SUPABASE_DATABASE_URL", "DATABASE_URL")
POOLER_HOST_ENV_VAR = "SUPABASE_POOLER_HOST"
LOCAL_ENV_FILES = (
    Path(__file__).resolve().parents[1] / ".env.local",
    Path(__file__).resolve().parents[1] / ".env",
)


@dataclass
class PersistResult:
    status: str
    run_id: str | None = None
    jobs_upserted: int = 0
    run_jobs_upserted: int = 0
    fetch_observations_inserted: int = 0
    job_evaluations_upserted: int = 0
    skipped_reason: str = ""
    error: str = ""


@dataclass
class VerificationPersistResult:
    status: str
    verification_run_id: str | None = None
    verifications_inserted: int = 0
    skipped_reason: str = ""
    error: str = ""


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_iso_datetime(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _content_hash(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _pooler_url(database_url: str, environment: Mapping[str, str]) -> str:
    pooler_host = _clean(environment.get(POOLER_HOST_ENV_VAR))
    if not pooler_host:
        return database_url
    if "://" in pooler_host or "/" in pooler_host or ":" in pooler_host:
        raise ValueError(f"{POOLER_HOST_ENV_VAR} must contain only a hostname")

    parsed = urlsplit(database_url)
    direct_host = parsed.hostname or ""
    if not direct_host.startswith("db.") or not direct_host.endswith(".supabase.co"):
        return database_url

    project_ref = direct_host.removeprefix("db.").removesuffix(".supabase.co")
    username = parsed.username or "postgres"
    if username == "postgres":
        username = f"postgres.{project_ref}"
    password = parsed.password or ""
    credentials = quote(username, safe="")
    if password:
        credentials += f":{quote(password, safe='')}"
    query = parsed.query
    if "sslmode=" not in query:
        query = f"{query}&sslmode=require" if query else "sslmode=require"
    return urlunsplit((parsed.scheme, f"{credentials}@{pooler_host}:5432", parsed.path, query, parsed.fragment))


def _local_environment() -> dict[str, str]:
    values: dict[str, str] = {}
    supported_keys = (*SUPPORTED_ENV_VARS, POOLER_HOST_ENV_VAR)
    for path in LOCAL_ENV_FILES:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            cleaned_key = _clean(key)
            if cleaned_key in supported_keys and cleaned_key not in values:
                values[cleaned_key] = _clean(value).strip("'\"")
    return values


def _database_url(env: Mapping[str, str] | None = None) -> str | None:
    environment = os.environ if env is None else env
    for key in SUPPORTED_ENV_VARS:
        candidate = _clean(environment.get(key))
        if not candidate:
            continue
        if "[YOUR-PASSWORD]" in candidate or "YOUR-PASSWORD" in candidate:
            return None
        return _pooler_url(candidate, environment)
    # An explicitly supplied environment is authoritative. This keeps tests and
    # callers deterministic instead of silently reading developer-local files.
    if env is not None:
        return None

    local_environment = _local_environment()
    for key in SUPPORTED_ENV_VARS:
        candidate = _clean(local_environment.get(key))
        if not candidate:
            continue
        if "[YOUR-PASSWORD]" in candidate or "YOUR-PASSWORD" in candidate:
            return None
        return _pooler_url(candidate, local_environment)
    return None


def _job_key(job: Mapping[str, Any]) -> str:
    provider = _clean(job.get("source"))
    source_id = _clean(job.get("source_id"))
    if not provider or not source_id:
        raise ValueError("job requires source and source_id")
    return f"{provider}:{source_id}"


def _ensure_schema(cursor) -> None:
    cursor.execute(
        """
        create table if not exists ats_schema_migrations (
          version text primary key,
          applied_at timestamptz not null default now()
        )
        """
    )
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        cursor.execute("select 1 from ats_schema_migrations where version = %s", (path.name,))
        if cursor.fetchone():
            continue
        cursor.execute(path.read_text(encoding="utf-8"))
        cursor.execute("insert into ats_schema_migrations (version) values (%s)", (path.name,))


def _load_psycopg():
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on local install
        raise RuntimeError("psycopg is not installed") from exc
    return psycopg


def _scan_kind(report: Mapping[str, Any]) -> str:
    provider = _clean(report.get("provider"))
    return provider or "combined"


def _provider_counts(report: Mapping[str, Any]) -> dict[str, Any]:
    providers = report.get("providers")
    if isinstance(providers, dict) and providers:
        return providers
    provider = _clean(report.get("provider"))
    if provider:
        return {
            provider: {
                "attempted": report.get("attempted", 0),
                "successful": report.get("successful", 0),
                "total_raw_jobs": report.get("total_raw_jobs", 0),
                "total_current_jobs": report.get("total_current_jobs", 0),
                "total_dropped_jobs": report.get("total_dropped_jobs", 0),
            }
        }
    return {}


def _run_payload(report: Mapping[str, Any], scan_kind: str) -> dict[str, Any]:
    return {
        "scan_kind": scan_kind,
        "schema_version": int(report.get("schema_version", 2)),
        "generated_at": _parse_iso_datetime(report.get("generated_at")) or datetime.now(timezone.utc),
        "freshness_days": int(report.get("freshness_days", 14)),
        "strategy": _clean(report.get("strategy")),
        "total_raw_jobs": int(report.get("total_raw_jobs", 0)),
        "total_current_jobs": int(report.get("total_current_jobs", 0)),
        "total_dropped_jobs": int(report.get("total_dropped_jobs", 0)),
        "match_count": len(report.get("matches") or []),
        "provider_counts": _provider_counts(report),
        "checked_sources": report.get("checked") or [],
        "errors": report.get("errors") or [],
        "source_repairs": report.get("source_repairs") or [],
        "report": report,
        "crawl_policy": DEFAULT_CRAWL_POLICY.as_dict(),
    }


def _job_payload(job: Mapping[str, Any], evidence: Mapping[str, Any] | None = None) -> dict[str, Any]:
    updated_at = _parse_iso_datetime(job.get("updated_at"))
    first_published = _parse_iso_datetime(job.get("first_published"))
    evidence_document = {
        "normalized_job": dict(job),
        "raw_job": dict((evidence or {}).get("raw_job") or job),
    }
    return {
        "job_key": _job_key(job),
        "provider": _clean(job.get("source")),
        "source_id": _clean(job.get("source_id")),
        "company": _clean(job.get("company")),
        "title": _clean(job.get("title")),
        "location": _clean(job.get("location")),
        "locations": list(job.get("locations") or []),
        "department": _clean(job.get("department")),
        "team": _clean(job.get("team")),
        "employment_type": _clean(job.get("employment_type")),
        "workplace_type": _clean(job.get("workplace_type")),
        "description": _clean(job.get("description")),
        "url": _clean(job.get("url")),
        "apply_url": _clean(job.get("apply_url")),
        "freshness_days": int(job.get("freshness_days", 14)),
        "updated_at": updated_at,
        "first_published": first_published,
        "raw_job": job,
        "raw_evidence": evidence_document["raw_job"],
        "content_hash": _content_hash(evidence_document),
    }


def persist_report(
    report: Mapping[str, Any],
    jobs: Sequence[Mapping[str, Any]] | None = None,
    *,
    scan_kind: str | None = None,
    env: Mapping[str, str] | None = None,
    fetch_evidence: Sequence[Mapping[str, Any]] | None = None,
    job_evidence: Sequence[Mapping[str, Any]] | None = None,
    job_evaluations: Sequence[Mapping[str, Any]] | None = None,
) -> PersistResult:
    database_url = _database_url(env)
    if not database_url:
        return PersistResult(status="skipped", skipped_reason="SUPABASE_DATABASE_URL is not configured")

    try:
        psycopg = _load_psycopg()
    except RuntimeError as exc:
        return PersistResult(status="skipped", skipped_reason=str(exc))

    scan_label = scan_kind or _scan_kind(report)
    run_payload = _run_payload(report, scan_label)
    evidence_by_job_key = {
        _clean(item.get("job_key")): item
        for item in (job_evidence or [])
        if _clean(item.get("job_key"))
    }
    job_rows = [
        _job_payload(job, evidence_by_job_key.get(_job_key(job)))
        for job in (jobs if jobs is not None else report.get("matches") or [])
    ]
    valid_job_keys = {row["job_key"] for row in job_rows}
    evaluation_rows = [
        item for item in (job_evaluations or [])
        if _clean(item.get("job_key")) in valid_job_keys
    ]

    fetch_payloads: dict[str, dict[str, Any]] = {}
    fetch_observations: list[dict[str, Any]] = []
    for item in fetch_evidence or []:
        response_payload = item.get("response_payload")
        evidence_hash = None
        if item.get("outcome") == "success" and response_payload is not None:
            payload_document = {
                "method": _clean(item.get("method")),
                "url": _clean(item.get("url")),
                "request_payload": item.get("request_payload"),
                "response_payload": response_payload,
            }
            evidence_hash = _content_hash(payload_document)
            fetch_payloads[evidence_hash] = {
                "evidence_hash": evidence_hash,
                **payload_document,
                "status_code": int(item.get("status_code") or 0),
            }
        fetch_observations.append({
            "run_id": None,
            "evidence_hash": evidence_hash,
            "company": _clean(item.get("company")),
            "provider": _clean(item.get("provider")),
            "source_slug": _clean(item.get("source_slug")),
            "url": _clean(item.get("url")),
            "method": _clean(item.get("method")),
            "fetched_at": _parse_iso_datetime(item.get("fetched_at")) or datetime.now(timezone.utc),
            "outcome": _clean(item.get("outcome")) or "error",
            "status_code": int(item.get("status_code") or 0),
            "attempt_count": int(item.get("attempt_count") or 0),
            "elapsed_ms": int(item.get("elapsed_ms") or 0),
            "error": _clean(item.get("error")),
        })

    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cursor:
                _ensure_schema(cursor)
                cursor.execute(
                    """
                    insert into ats_scan_runs (
                      scan_kind, schema_version, generated_at, freshness_days, strategy,
                      total_raw_jobs, total_current_jobs, total_dropped_jobs, match_count,
                      provider_counts, checked_sources, errors, source_repairs, report,
                      crawl_policy
                    )
                    values (
                      %(scan_kind)s,
                      %(schema_version)s,
                      %(generated_at)s,
                      %(freshness_days)s,
                      %(strategy)s,
                      %(total_raw_jobs)s,
                      %(total_current_jobs)s,
                      %(total_dropped_jobs)s,
                      %(match_count)s,
                      %(provider_counts)s::jsonb,
                      %(checked_sources)s::jsonb,
                      %(errors)s::jsonb,
                      %(source_repairs)s::jsonb,
                      %(report)s::jsonb,
                      %(crawl_policy)s::jsonb
                    )
                    returning id
                    """,
                    {
                        **run_payload,
                        "provider_counts": _json_text(run_payload["provider_counts"]),
                        "checked_sources": _json_text(run_payload["checked_sources"]),
                        "errors": _json_text(run_payload["errors"]),
                        "source_repairs": _json_text(run_payload["source_repairs"]),
                        "report": _json_text(run_payload["report"]),
                        "crawl_policy": _json_text(run_payload["crawl_policy"]),
                    },
                )
                run_id = str(cursor.fetchone()[0])
                if job_rows:
                    cursor.execute(
                        "select job_key, current_content_hash from ats_jobs where job_key = any(%s)",
                        ([row["job_key"] for row in job_rows],),
                    )
                    previous_hashes = dict(cursor.fetchall())
                    for row in job_rows:
                        previous_hash = previous_hashes.get(row["job_key"])
                        row["observation_status"] = (
                            "new" if previous_hash is None
                            else "unchanged" if previous_hash == row["content_hash"]
                            else "changed"
                        )
                    cursor.executemany(
                        """
                        insert into ats_jobs (
                          job_key, provider, source_id, company, title, location, locations,
                          department, team, employment_type, workplace_type, description,
                          url, apply_url, freshness_days, updated_at, first_published,
                          raw_job, first_seen_run_id, last_seen_run_id, first_seen_at,
                          last_seen_at, updated_at_db, current_content_hash
                        )
                        values (
                          %(job_key)s,
                          %(provider)s,
                          %(source_id)s,
                          %(company)s,
                          %(title)s,
                          %(location)s,
                          %(locations)s,
                          %(department)s,
                          %(team)s,
                          %(employment_type)s,
                          %(workplace_type)s,
                          %(description)s,
                          %(url)s,
                          %(apply_url)s,
                          %(freshness_days)s,
                          %(updated_at)s,
                          %(first_published)s,
                          %(raw_job)s::jsonb,
                          %(first_seen_run_id)s,
                          %(last_seen_run_id)s,
                          now(),
                          now(),
                          now(),
                          %(content_hash)s
                        )
                        on conflict (job_key) do update set
                          provider = excluded.provider,
                          source_id = excluded.source_id,
                          company = excluded.company,
                          title = excluded.title,
                          location = excluded.location,
                          locations = excluded.locations,
                          department = excluded.department,
                          team = excluded.team,
                          employment_type = excluded.employment_type,
                          workplace_type = excluded.workplace_type,
                          description = excluded.description,
                          url = excluded.url,
                          apply_url = excluded.apply_url,
                          freshness_days = excluded.freshness_days,
                          updated_at = excluded.updated_at,
                          first_published = excluded.first_published,
                          raw_job = excluded.raw_job,
                          first_seen_run_id = coalesce(ats_jobs.first_seen_run_id, excluded.first_seen_run_id),
                          last_seen_run_id = excluded.last_seen_run_id,
                          last_seen_at = now(),
                          updated_at_db = now(),
                          current_content_hash = excluded.current_content_hash
                        """,
                        [
                            {
                                **row,
                                "first_seen_run_id": run_id,
                                "last_seen_run_id": run_id,
                                "raw_job": _json_text(row["raw_job"]),
                            }
                            for row in job_rows
                        ],
                    )
                    cursor.executemany(
                        """
                        insert into ats_job_versions (
                          job_key, content_hash, normalized_job, raw_job,
                          first_seen_run_id, last_seen_run_id,
                          first_seen_at, last_seen_at, expires_at
                        )
                        values (
                          %(job_key)s,
                          %(content_hash)s,
                          %(normalized_job)s::jsonb,
                          %(raw_evidence)s::jsonb,
                          %(run_id)s,
                          %(run_id)s,
                          now(),
                          now(),
                          now() + interval '90 days'
                        )
                        on conflict (job_key, content_hash) do update set
                          last_seen_run_id = excluded.last_seen_run_id,
                          last_seen_at = now(),
                          expires_at = now() + interval '90 days'
                        """,
                        [
                            {
                                **row,
                                "normalized_job": _json_text(row["raw_job"]),
                                "raw_evidence": _json_text(row["raw_evidence"]),
                                "run_id": run_id,
                            }
                            for row in job_rows
                        ],
                    )
                    cursor.executemany(
                        """
                        insert into ats_run_jobs (
                          run_id, job_key, provider, company, title, url,
                          job_snapshot, content_hash, observation_status
                        )
                        values (
                          %s,
                          %s,
                          %s,
                          %s,
                          %s,
                          %s,
                          null,
                          %s,
                          %s
                        )
                        on conflict (run_id, job_key) do update set
                          provider = excluded.provider,
                          company = excluded.company,
                          title = excluded.title,
                          url = excluded.url,
                          job_snapshot = null,
                          content_hash = excluded.content_hash,
                          observation_status = excluded.observation_status,
                          seen_at = now()
                        """,
                        [
                            (
                                run_id,
                                row["job_key"],
                                row["provider"],
                                row["company"],
                                row["title"],
                                row["url"],
                                row["content_hash"],
                                row["observation_status"],
                            )
                            for row in job_rows
                        ],
                    )
                if evaluation_rows:
                    cursor.executemany(
                        """
                        insert into ats_job_evaluations (
                          run_id, job_key, decision, reasons, signals
                        )
                        values (%s, %s, %s, %s::jsonb, %s::jsonb)
                        on conflict (run_id, job_key) do update set
                          decision = excluded.decision,
                          reasons = excluded.reasons,
                          signals = excluded.signals,
                          evaluated_at = now()
                        """,
                        [
                            (
                                run_id,
                                _clean(row.get("job_key")),
                                _clean(row.get("decision")),
                                _json_text(row.get("reasons") or []),
                                _json_text(row.get("signals") or {}),
                            )
                            for row in evaluation_rows
                        ],
                    )
                if fetch_payloads:
                    cursor.executemany(
                        """
                        insert into ats_fetch_payloads (
                          evidence_hash, method, url, request_payload, response_payload,
                          status_code, first_seen_at, last_seen_at, expires_at
                        )
                        values (
                          %(evidence_hash)s,
                          %(method)s,
                          %(url)s,
                          %(request_payload)s::jsonb,
                          %(response_payload)s::jsonb,
                          %(status_code)s,
                          now(),
                          now(),
                          now() + interval '90 days'
                        )
                        on conflict (evidence_hash) do update set
                          last_seen_at = now(),
                          expires_at = now() + interval '90 days'
                        """,
                        [
                            {
                                **row,
                                "request_payload": _json_text(row["request_payload"]),
                                "response_payload": _json_text(row["response_payload"]),
                            }
                            for row in fetch_payloads.values()
                        ],
                    )
                if fetch_observations:
                    cursor.executemany(
                        """
                        insert into ats_fetch_observations (
                          run_id, evidence_hash, company, provider, source_slug,
                          url, method, fetched_at, outcome, status_code,
                          attempt_count, elapsed_ms, error
                        )
                        values (
                          %(run_id)s,
                          %(evidence_hash)s,
                          %(company)s,
                          %(provider)s,
                          %(source_slug)s,
                          %(url)s,
                          %(method)s,
                          %(fetched_at)s,
                          %(outcome)s,
                          %(status_code)s,
                          %(attempt_count)s,
                          %(elapsed_ms)s,
                          %(error)s
                        )
                        """,
                        [{**row, "run_id": run_id} for row in fetch_observations],
                    )
                cursor.execute("select * from ats_cleanup_evidence(interval '90 days')")
                conn.commit()
        return PersistResult(
            status="persisted",
            run_id=run_id,
            jobs_upserted=len(job_rows),
            run_jobs_upserted=len(job_rows),
            fetch_observations_inserted=len(fetch_observations),
            job_evaluations_upserted=len(evaluation_rows),
        )
    except Exception as exc:  # pragma: no cover - guarded against live DB failure
        return PersistResult(status="error", error=str(exc))


def persist_verification_results(
    verifications: Sequence[Mapping[str, Any]],
    *,
    scan_run_id: str | None = None,
    verification_kind: str = "local_quality",
    config: Mapping[str, Any] | None = None,
    errors: Sequence[Mapping[str, Any]] | None = None,
    env: Mapping[str, str] | None = None,
) -> VerificationPersistResult:
    database_url = _database_url(env)
    if not database_url:
        return VerificationPersistResult(status="skipped", skipped_reason="SUPABASE_DATABASE_URL is not configured")

    try:
        psycopg = _load_psycopg()
    except RuntimeError as exc:
        return VerificationPersistResult(status="skipped", skipped_reason=str(exc))

    rows: list[dict[str, Any]] = []
    status_counts: dict[str, int] = {}
    for item in verifications:
        job_key = _clean(item.get("job_key"))
        if not job_key:
            continue
        verification_status = _clean(item.get("verification_status")) or "unknown"
        status_counts[verification_status] = status_counts.get(verification_status, 0) + 1
        rows.append({
            "job_key": job_key,
            "scan_run_id": _clean(item.get("scan_run_id")) or scan_run_id,
            "content_hash": _clean(item.get("content_hash")) or None,
            "verification_status": verification_status,
            "confidence": float(item.get("confidence") or 0),
            "reasons": item.get("reasons") or [],
            "signals": item.get("signals") or {},
            "evidence": item.get("evidence") or {},
            "url": _clean(item.get("url")),
            "apply_url": _clean(item.get("apply_url")),
            "url_status_code": int(item.get("url_status_code") or 0),
            "apply_url_status_code": int(item.get("apply_url_status_code") or 0),
            "final_url": _clean(item.get("final_url")),
            "final_apply_url": _clean(item.get("final_apply_url")),
            "error": _clean(item.get("error")),
        })

    run_status = "completed" if not errors else "failed"
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cursor:
                _ensure_schema(cursor)
                cursor.execute(
                    """
                    insert into ats_verification_runs (
                      scan_run_id, verification_kind, schema_version, status,
                      started_at, completed_at, total_jobs, status_counts,
                      config, errors
                    )
                    values (
                      %s, %s, 1, %s, now(), now(), %s, %s::jsonb, %s::jsonb, %s::jsonb
                    )
                    returning id
                    """,
                    (
                        scan_run_id,
                        verification_kind,
                        run_status,
                        len(rows),
                        _json_text(status_counts),
                        _json_text(config or {}),
                        _json_text(list(errors or [])),
                    ),
                )
                verification_run_id = str(cursor.fetchone()[0])
                if rows:
                    cursor.executemany(
                        """
                        insert into ats_job_verifications (
                          verification_run_id, job_key, scan_run_id, content_hash,
                          verification_status, confidence, reasons, signals, evidence,
                          url, apply_url, url_status_code, apply_url_status_code,
                          final_url, final_apply_url, error
                        )
                        values (
                          %(verification_run_id)s, %(job_key)s, %(scan_run_id)s,
                          %(content_hash)s, %(verification_status)s, %(confidence)s,
                          %(reasons)s::jsonb, %(signals)s::jsonb, %(evidence)s::jsonb,
                          %(url)s, %(apply_url)s, %(url_status_code)s,
                          %(apply_url_status_code)s, %(final_url)s, %(final_apply_url)s,
                          %(error)s
                        )
                        on conflict (verification_run_id, job_key) do update set
                          scan_run_id = excluded.scan_run_id,
                          content_hash = excluded.content_hash,
                          verification_status = excluded.verification_status,
                          confidence = excluded.confidence,
                          reasons = excluded.reasons,
                          signals = excluded.signals,
                          evidence = excluded.evidence,
                          url = excluded.url,
                          apply_url = excluded.apply_url,
                          url_status_code = excluded.url_status_code,
                          apply_url_status_code = excluded.apply_url_status_code,
                          final_url = excluded.final_url,
                          final_apply_url = excluded.final_apply_url,
                          error = excluded.error,
                          checked_at = now()
                        """,
                        [
                            {
                                **row,
                                "verification_run_id": verification_run_id,
                                "reasons": _json_text(row["reasons"]),
                                "signals": _json_text(row["signals"]),
                                "evidence": _json_text(row["evidence"]),
                            }
                            for row in rows
                        ],
                    )
                conn.commit()
        return VerificationPersistResult(
            status="persisted",
            verification_run_id=verification_run_id,
            verifications_inserted=len(rows),
        )
    except Exception as exc:  # pragma: no cover - guarded against live DB failure
        return VerificationPersistResult(status="error", error=str(exc))
