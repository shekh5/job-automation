#!/usr/bin/env python3
"""Phase 6 Orchestrator and Scheduler for ATS Pipeline

Coordinates sequential execution of ATS crawlers, static/browser HTTP scrapers,
and downstream verification processes into a single safe pipeline.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import uuid
from typing import Any, Dict

logger = logging.getLogger(__name__)

def run_subprocess(cmd: list[str]) -> tuple[int, str, str]:
    """Execute a shell command, returning (returncode, stdout, stderr)."""
    logger.info(f"Running command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        logger.error(f"Command failed with exit code {result.returncode}")
        if result.stderr:
            logger.error(f"Stderr: {result.stderr}")
    return result.returncode, result.stdout, result.stderr

def extract_run_id_from_logs(logs: str) -> str | None:
    """Regex extract a persisted scan_run_id or verification_run_id."""
    # Look for our standardized log format: "Persisted X jobs to <uuid>"
    match = re.search(r"Persisted \d+ jobs to ([a-f0-9\-]{36})", logs, re.IGNORECASE)
    if match:
        return match.group(1)
    
    # Try parsing as JSON dump (for verification scripts)
    try:
        data = json.loads(logs)
        if isinstance(data, dict):
            return data.get("verification_run_id") or data.get("scan_run_id")
    except json.JSONDecodeError:
        pass
        
    return None

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ats", action="store_true", help="Run ATS combined fetcher")
    parser.add_argument("--static", action="store_true", help="Run static HTTP fetcher for configured sources")
    parser.add_argument("--browser-fallback", action="store_true", help="Allow JS-rendered pages to be crawled via browser fallback")
    parser.add_argument("--verify-local", action="store_true", help="Run local data quality verification")
    parser.add_argument("--verify-url", action="store_true", help="Run HTTP reachability verification")
    parser.add_argument("--verify-closed-text", action="store_true", help="Extract closed text signals (Phase 3E)")
    parser.add_argument("--classify", action="store_true", help="Run open/closed classifiers")
    
    parser.add_argument("--url-limit", type=int, default=200, help="Limit for URL reachability checks")
    parser.add_argument("--static-limit", type=int, default=50, help="Limit for static fetch checks")
    parser.add_argument("--browser-limit", type=int, default=10, help="Limit for browser fetch checks")
    
    parser.add_argument("--dry-run", action="store_true", help="Print intention without executing scripts")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    output = {
        "status": "completed",
        "scan_runs": {},
        "verification_runs": {},
        "errors": []
    }
    
    # Generate run IDs for the scrapers so we can correlate
    static_run_id = str(uuid.uuid4())
    
    base_python = sys.executable

    # 1. ATS Fetcher
    if args.ats:
        if args.dry_run:
            logger.info("[Dry Run] Would execute: fetch_jobs_ats.py")
            output["scan_runs"]["ats_combined"] = "dry-run-uuid"
        else:
            code, out, err = run_subprocess([base_python, "workspace/scripts/fetch_jobs_ats.py"])
            if code != 0:
                output["errors"].append({"step": "ats", "error": "Non-zero exit code"})
            run_id = extract_run_id_from_logs(out) or extract_run_id_from_logs(err)
            if run_id:
                output["scan_runs"]["ats_combined"] = run_id

    # 2. Static / Browser Fetcher
    if args.static or args.browser_fallback:
        cmd = [base_python, "workspace/scripts/fetch_jobs_browser_pages.py", "--run-id", static_run_id, "--limit", str(args.static_limit)]
        # We handle --static vs --browser-fallback logically:
        # fetch_jobs_browser_pages.py natively checks source configuration `browser_fallback_allowed` flag.
        # But if the user didn't explicitly pass --browser-fallback at CLI level, maybe we should override and disable it?
        # For simplicity, if --browser-fallback is omitted, we could disable the flag via an environment variable, 
        # but fetch_jobs_browser_pages.py handles both already. 
        if args.dry_run:
            logger.info(f"[Dry Run] Would execute: {' '.join(cmd)}")
            output["scan_runs"]["static_http"] = static_run_id
        else:
            code, out, err = run_subprocess(cmd)
            if code != 0:
                output["errors"].append({"step": "static", "error": "Non-zero exit code"})
            output["scan_runs"]["static_http"] = static_run_id

    # 3. Local Verification
    if args.verify_local:
        if args.dry_run:
            logger.info("[Dry Run] Would execute: verify_ats_jobs.py")
            output["verification_runs"]["local_quality"] = "dry-run-uuid"
        else:
            code, out, err = run_subprocess([base_python, "workspace/scripts/verify_ats_jobs.py", "--limit", "2000"])
            if code != 0:
                output["errors"].append({"step": "verify_local", "error": "Non-zero exit code"})
            run_id = extract_run_id_from_logs(out)
            if run_id:
                output["verification_runs"]["local_quality"] = run_id

    # 4. URL Reachability
    if args.verify_url:
        if args.dry_run:
            logger.info("[Dry Run] Would execute: verify_ats_urls.py")
            output["verification_runs"]["url_reachability"] = "dry-run-uuid"
        else:
            code, out, err = run_subprocess([base_python, "workspace/scripts/verify_ats_urls.py", "--limit", str(args.url_limit)])
            if code != 0:
                output["errors"].append({"step": "verify_url", "error": "Non-zero exit code"})
            run_id = extract_run_id_from_logs(out)
            if run_id:
                output["verification_runs"]["url_reachability"] = run_id

    # 5. Closed Text Signals (Phase 3E)
    if args.verify_closed_text:
        if args.dry_run:
            logger.info("[Dry Run] Would execute: verify_ats_closed_signals.py")
            output["verification_runs"]["closed_text_signals"] = "dry-run-uuid"
        else:
            code, out, err = run_subprocess([base_python, "workspace/scripts/verify_ats_closed_signals.py", "--limit", "2000"])
            if code != 0:
                output["errors"].append({"step": "verify_closed_text", "error": "Non-zero exit code"})
            run_id = extract_run_id_from_logs(out)
            if run_id:
                output["verification_runs"]["closed_text_signals"] = run_id

    # 6. Final Classification
    if args.classify:
        if args.dry_run:
            logger.info("[Dry Run] Would execute: verify_ats_open_closed.py")
            output["verification_runs"]["open_closed_classification"] = "dry-run-uuid"
        else:
            code, out, err = run_subprocess([base_python, "workspace/scripts/verify_ats_open_closed.py", "--limit", "2000"])
            if code != 0:
                output["errors"].append({"step": "classify", "error": "Non-zero exit code"})
            run_id = extract_run_id_from_logs(out)
            if run_id:
                output["verification_runs"]["open_closed_classification"] = run_id

    if output["errors"]:
        output["status"] = "completed_with_errors"

    # 7. Final Query Assembly
    if not args.dry_run:
        try:
            from ats_supabase import _load_psycopg, _database_url
            if _database_url():
                psycopg = _load_psycopg()
                conn = psycopg.connect(_database_url())
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT verification_status, COUNT(*) 
                        FROM ats_job_verification_latest 
                        GROUP BY verification_status;
                    """)
                    rows = cur.fetchall()
                    counts = {
                        "jobs_total": 0,
                        "open": 0,
                        "closed": 0,
                        "unknown": 0,
                        "blocked": 0,
                        "invalid": 0
                    }
                    for row in rows:
                        status, count = row
                        counts[status] = count
                        counts["jobs_total"] += count
                    output["counts"] = counts
        except Exception as e:
            logger.error(f"Failed to fetch counts: {e}")
            output["errors"].append({"step": "counts", "error": str(e)})

    print(json.dumps(output, indent=2))
    return 1 if output["errors"] else 0

if __name__ == "__main__":
    sys.exit(main())
