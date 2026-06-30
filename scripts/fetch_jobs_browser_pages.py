#!/usr/bin/env python3
"""Phase 5 Stateful Browser Fallback Crawler

Runs the static crawler first. If zero jobs are extracted AND the page has a JS app shell
AND browser fallback is enabled, it spins up Playwright to extract jobs.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from ats_common import clean_text
from ats_crawl_policy import DEFAULT_CRAWL_POLICY
from fetch_jobs_static_pages import fetch_html, extract_jobs_from_html, load_sources
from browser_page_extractor import extract_jobs_from_dom
from ats_supabase import persist_report

logger = logging.getLogger(__name__)

def has_js_app_shell(html: str) -> bool:
    """Detect if the page appears to be a Javascript Single Page Application."""
    indicators = [
        "__next_data__",
        'id="root"',
        'id="app"',
        "window.__initial_state__",
        "bundle.js",
        "vite",
        "webpack",
        "<script", # almost all pages use scripts, so if static jobs == 0 and browser_allowed, fallback is likely needed
        "react",
        "angular"
    ]
    html_lower = html.lower()
    return any(indicator.lower() in html_lower for indicator in indicators)

def fetch_with_browser(url: str, timeout_ms: int = 20000) -> tuple[str, str]:
    """Fetch URL using Playwright. Returns (html, final_url)."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="OpenClaw ATS Browser Extractor",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        try:
            # Wait for domcontentloaded to avoid timeouts on sites with endless analytics requests
            response = page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
            
            # Simple heuristic: wait an extra bit for React/Vue rendering
            page.wait_for_timeout(3000)
            
            html = page.content()
            final_url = page.url
            
            return html, final_url
        except PlaywrightTimeoutError:
            logger.warning(f"Browser timeout while fetching {url}")
            return "", url
        except Exception as e:
            logger.error(f"Browser error fetching {url}: {e}")
            return "", url
        finally:
            browser.close()

def process_company(company_config: Dict[str, Any], dry_run: bool) -> tuple[int, int, Dict[str, Any]]:
    company = company_config.get("company", "")
    url = company_config.get("career_url") or company_config.get("url", "")
    browser_allowed = company_config.get("browser_fallback_allowed", False)
    
    if not company or not url:
        return 0, 0, {}
        
    logger.info(f"Checking {company} at {url}")
    
    # 1. Static fetch first
    html = fetch_html(url)
    if not html:
        return 0, 1, {}

    jobs = extract_jobs_from_html(html, url, company)
    provider = "static_career_page"
    
    # 2. Browser fallback evaluation
    if len(jobs) == 0 and browser_allowed and has_js_app_shell(html):
        logger.info(f"0 static jobs found + JS app shell detected. Engaging browser fallback for {company}...")
        browser_html, final_url = fetch_with_browser(url)
        if browser_html:
            html = browser_html
            extraction = extract_jobs_from_dom(html, final_url, company)
            
            if extraction["status"] == "blocked":
                logger.warning(f"Browser access blocked for {company}: {extraction['reason']}")
                return 0, 1, {}
                
            jobs = extraction.get("jobs", [])
            provider = "browser_rendered_page"

    # Bundle evidence
    fetch_payload = {
        "company": company,
        "url": url,
        "provider": provider,
        "response_payload": {"html_length": len(html), "raw_job": html[:500000]}
    }
    
    job_evidence = []
    for job in jobs:
        job_evidence.append({
            "job_key": job.get("job_url", ""),
            "raw_job": job
        })

    logger.info(f"Extracted {len(jobs)} jobs for {company} via {provider}")
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
            time.sleep(1.0)
            
        jobs_count, errs, payload = process_company(source, args.dry_run)
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
            scan_kind="hybrid_career_pages",
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
