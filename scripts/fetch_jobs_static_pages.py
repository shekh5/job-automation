#!/usr/bin/env python3
"""Phase 4 Static/HTTP Career Page Crawler

Iterates over configured sources, fetches static HTML, extracts jobs using static_page_extractor,
and persists payloads and jobs.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from ats_common import clean_text
from ats_crawl_policy import DEFAULT_CRAWL_POLICY
from static_page_extractor import extract_jobs_from_html
from verify_ats_jobs import valid_http_url
from ats_supabase import persist_report

logger = logging.getLogger(__name__)

def load_sources() -> List[Dict[str, Any]]:
    path = Path(__file__).resolve().parent.parent / "data" / "career_page_sources.json"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
            return data.get("companies", [])
        return data

def fetch_html(url: str) -> str:
    if not valid_http_url(url):
        return ""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "OpenClaw ATS Static Page Extractor",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=DEFAULT_CRAWL_POLICY.request_timeout_seconds) as response:
            body = response.read()
            return body.decode("utf-8", errors="replace")
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return ""

def crawl_company(company_config: Dict[str, Any], dry_run: bool) -> tuple[int, int, Dict[str, Any]]:
    company = company_config.get("company", "")
    url = company_config.get("career_url") or company_config.get("url", "")
    
    if not company or not url:
        return 0, 0, {}
        
    logger.info(f"Crawling {company} at {url}")
    
    html = fetch_html(url)
    if not html:
        return 0, 1, {}

    jobs = extract_jobs_from_html(html, url, company)
    
    # Bundle fetch evidence
    fetch_payload = {
        "company": company,
        "url": url,
        "provider": "static_career_page",
        "response_payload": {"html_length": len(html), "raw_job": html[:500000]}
    }
    
    job_evidence = []
    for job in jobs:
        job_evidence.append({
            "job_key": job.get("job_url", ""),
            "raw_job": job
        })

    logger.info(f"Extracted {len(jobs)} jobs for {company}")
    return len(jobs), 0, {
        "jobs": jobs,
        "fetch_evidence": [fetch_payload],
        "job_evidence": job_evidence
    }

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Scan Run ID")
    parser.add_argument("--company", help="Optional exact company filter")
    parser.add_argument("--limit", type=int, default=10, help="Limit number of companies to crawl")
    parser.add_argument("--dry-run", action="store_true", help="Print stats, don't save to DB")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    sources = load_sources()
    if args.company:
        sources = [s for s in sources if s.get("company", "").lower() == args.company.lower()]
        
    sources = sources[:args.limit]
    
    total_jobs = 0
    total_errors = 0
    
    all_jobs = []
    all_fetch_evidence = []
    all_job_evidence = []
    
    for idx, source in enumerate(sources):
        if idx > 0:
            time.sleep(1.0) # hardcoded 1s delay
            
        jobs_count, errs, payload = crawl_company(source, args.dry_run)
        total_jobs += jobs_count
        total_errors += errs
        
        if payload:
            all_jobs.extend(payload.get("jobs", []))
            all_fetch_evidence.extend(payload.get("fetch_evidence", []))
            all_job_evidence.extend(payload.get("job_evidence", []))
            
    if not args.dry_run and all_jobs:
        report = {
            "metadata": {
                "scan_run_id": args.run_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
        res = persist_report(
            report=report,
            jobs=all_jobs,
            scan_kind="static_career_pages",
            fetch_evidence=all_fetch_evidence,
            job_evidence=all_job_evidence
        )
        if res.status != "persisted":
            logger.error(f"Failed to persist: {res.skipped_reason or res.error}")
            return 1
        logger.info(f"Persisted {res.jobs_inserted} jobs to {res.scan_run_id}")

    print(f"Finished. Extracted {total_jobs} jobs. Errors: {total_errors}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
