#!/usr/bin/env python3
"""Phase 3E closed text signal extraction for persisted ATS jobs.

This script inspects stored evidence (and optionally performs a lightweight GET)
to extract explicit closed or open text indicators from the job page.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ats_common import clean_text
from ats_crawl_policy import DEFAULT_CRAWL_POLICY
from ats_supabase import _database_url, _ensure_schema, _load_psycopg, persist_verification_results
from verify_ats_jobs import valid_http_url

CLOSED_SIGNALS_SCHEMA_VERSION = 1

GENERIC_CLOSED_PHRASES = [
    "job no longer available",
    "position no longer available",
    "posting is no longer available",
    "this job has expired",
    "this posting has expired",
    "job has been closed",
    "position has been filled",
    "no longer accepting applications",
    "application deadline has passed",
    "job not found",
    "posting not found",
    "role is closed",
    "vacancy is closed",
    "this job is no longer available",
    "this job is no longer accepting applications",
    "this posting is no longer available",
]

GENERIC_OPEN_PHRASES = [
    "apply now",
    "submit application",
    "apply for this job",
    "start your application",
    "job application",
]

PROVIDER_SPECIFIC_PHRASES = {
    "greenhouse": {
        "closed": ["this job is no longer available"],
        "open": ["apply for this job", "submit application"]
    },
    "lever": {
        "closed": ["this posting is no longer available"],
        "open": ["apply for this job"]
    },
    "ashby": {
        "closed": ["this job is no longer available"],
        "open": ["apply for this job"]
    },
    "workday": {
        "closed": ["this job is no longer accepting applications"],
        "open": ["apply"]
    }
}

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="ATS scan run UUID; defaults to latest combined scan")
    parser.add_argument("--company", help="Optional exact company filter")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--dry-run", action="store_true", help="Print results without writing verification rows")
    parser.add_argument("--fetch-missing", action="store_true", help="Perform lightweight HTTP GET for missing evidence")
    return parser.parse_args()

def normalize_page_text(text: str) -> str:
    if not text:
        return ""
    # Remove script and style tags and their contents
    text = re.sub(r'<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>', ' ', text, flags=re.IGNORECASE)
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Collapse whitespace and lowercase
    text = re.sub(r'\s+', ' ', text).strip().casefold()
    # Limit max characters just to be safe
    return text[:100000]

def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _rows(cursor) -> list[dict[str, Any]]:
    columns = [item.name for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]

def load_jobs_with_evidence(run_id: str | None = None, *, company: str | None = None, limit: int = 2000) -> tuple[str, list[dict[str, Any]]]:
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
            
            # Fetch jobs with their raw_job from ats_job_versions for the latest hash
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
                  j.url,
                  j.apply_url,
                  jv.raw_job as raw_evidence
                from ats_run_jobs rj
                join ats_jobs j on j.job_key = rj.job_key
                left join ats_job_versions jv on jv.job_key = j.job_key and jv.content_hash = coalesce(rj.content_hash, j.current_content_hash)
                where {' and '.join(conditions)}
                order by j.company, j.title
                limit %s
                """,
                params,
            )
            jobs = _rows(cursor)
    return selected_run_id, jobs

def fetch_lightweight_html(url: str) -> str:
    if not valid_http_url(url):
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "OpenClaw ATS text signal extractor",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_CRAWL_POLICY.request_timeout_seconds) as response:
            body = response.read()
            return body.decode("utf-8", errors="replace")
    except Exception:
        return ""

def extract_signals(normalized_text: str, provider: str) -> tuple[list[str], list[str]]:
    matched_closed = []
    matched_open = []

    # Check provider-specific first
    provider_phrases = PROVIDER_SPECIFIC_PHRASES.get(provider.casefold(), {})
    for phrase in provider_phrases.get("closed", []):
        if phrase in normalized_text:
            matched_closed.append(phrase)
    for phrase in provider_phrases.get("open", []):
        if phrase in normalized_text:
            matched_open.append(phrase)

    # Check generic
    for phrase in GENERIC_CLOSED_PHRASES:
        if phrase in normalized_text and phrase not in matched_closed:
            matched_closed.append(phrase)
    for phrase in GENERIC_OPEN_PHRASES:
        if phrase in normalized_text and phrase not in matched_open:
            matched_open.append(phrase)
            
    return matched_closed, matched_open

def verify_job_signals(job: Mapping[str, Any], fetch_missing: bool = False) -> dict[str, Any] | None:
    job_key = clean_text(job.get("job_key"))
    if not job_key:
        return None
        
    provider = clean_text(job.get("source"))
    url = clean_text(job.get("url"))
    
    raw_evidence = job.get("raw_evidence") or {}
    text_to_check = ""
    source_used = "stored_evidence"
    
    if raw_evidence:
        # If the raw evidence is a dict, convert it to a json string
        if isinstance(raw_evidence, dict):
            text_to_check = json.dumps(raw_evidence, ensure_ascii=False)
        else:
            text_to_check = str(raw_evidence)
            
    if not text_to_check and fetch_missing and url:
        fetched_html = fetch_lightweight_html(url)
        if fetched_html:
            text_to_check = fetched_html
            source_used = "http_get"

    if not text_to_check:
        # No evidence available to check
        return None
        
    normalized = normalize_page_text(text_to_check)
    matched_closed, matched_open = extract_signals(normalized, provider)
    
    reasons = []
    if matched_closed and not matched_open:
        reasons.append("closed_text_signal_found")
        status = "unknown" # Leave it unknown here, Phase 3D handles it
    elif matched_open and not matched_closed:
        reasons.append("open_text_signal_found")
        status = "unknown"
    elif matched_closed and matched_open:
        reasons.append("conflicting_text_signals")
        status = "unknown"
    else:
        reasons.append("no_explicit_text_signals")
        status = "unknown"
        
    checked_at = datetime.now(timezone.utc).isoformat()
    
    return {
        "job_key": job_key,
        "scan_run_id": clean_text(job.get("scan_run_id")),
        "content_hash": clean_text(job.get("content_hash")) or None,
        "verification_status": status,
        "confidence": 0.8 if matched_closed or matched_open else 0.5,
        "reasons": reasons,
        "signals": {
            "checker": "closed_text_signals",
            "schema_version": CLOSED_SIGNALS_SCHEMA_VERSION,
            "closed_text_found": bool(matched_closed),
            "open_text_found": bool(matched_open),
            "matched_closed_phrases": matched_closed,
            "matched_open_phrases": matched_open,
            "source": source_used
        },
        "evidence": {
            "checker": "closed_text_signals",
            "checked_at": checked_at,
            "text_sample_hash": _content_hash(normalized),
            "matched_rules": matched_closed + matched_open
        },
        "url": url,
        "apply_url": clean_text(job.get("apply_url")),
        "url_status_code": 0,
        "apply_url_status_code": 0,
        "final_url": "",
        "final_apply_url": "",
        "error": "",
    }

def main() -> int:
    args = parse_args()
    if not 1 <= args.limit <= 10000:
        raise SystemExit("--limit must be between 1 and 10000")

    run_id, jobs = load_jobs_with_evidence(args.run_id, company=args.company, limit=args.limit)
    
    results = []
    for job in jobs:
        result = verify_job_signals(job, fetch_missing=args.fetch_missing)
        if result:
            results.append(result)

    output: dict[str, Any] = {
        "scan_run_id": run_id,
        "verification_kind": "closed_text_signals",
        "dry_run": args.dry_run,
        "summary": {
            "total_jobs_checked": len(jobs),
            "total_signals_extracted": len(results),
        }
    }
    
    if args.dry_run:
        output["rows"] = results[:50]
    else:
        persisted = persist_verification_results(
            results,
            scan_run_id=run_id,
            verification_kind="closed_text_signals",
            config={
                "checker": "closed_text_signals",
                "schema_version": CLOSED_SIGNALS_SCHEMA_VERSION,
                "limit": args.limit,
                "company": args.company or "",
                "fetch_missing": args.fetch_missing,
            },
        )
        if persisted.status != "persisted":
            detail = persisted.error or persisted.skipped_reason or persisted.status
            raise RuntimeError(f"closed_text_signals verification persistence failed: {detail}")
        output["verification_run_id"] = persisted.verification_run_id
        output["verifications_inserted"] = persisted.verifications_inserted

    print(json.dumps(output, indent=2, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
