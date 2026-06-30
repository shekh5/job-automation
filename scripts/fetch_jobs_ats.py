#!/usr/bin/env python3
"""Run all supported ATS adapters and write one backward-compatible report."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

from ats_common import (
    FRESHNESS_DAYS,
    PROVIDERS,
    ROOT,
    deduplicate_jobs,
    deduplicate_jobs_by_source,
    load_source_database,
    scan_provider,
)
from ats_supabase import persist_report
from fetch_jobs_ashby import scan_source as scan_ashby
from fetch_jobs_greenhouse import scan_source as scan_greenhouse
from fetch_jobs_lever import scan_source as scan_lever
from fetch_jobs_workday import scan_source as scan_workday

OUT = ROOT / "memory" / "job_api_scan_latest.json"
MD_OUT = ROOT / "memory" / "job_api_scan_latest.md"
SCANNERS = {
    "greenhouse": scan_greenhouse,
    "lever": scan_lever,
    "ashby": scan_ashby,
    "workday": scan_workday,
}


def scan(
    *,
    persistence_jobs: list[dict] | None = None,
    persistence_context: dict[str, list[dict]] | None = None,
) -> dict:
    sources, source_errors = load_source_database()
    provider_reports = {
        provider: scan_provider(provider, SCANNERS[provider], sources)
        for provider in PROVIDERS
    }
    checked = [item for report in provider_reports.values() for item in report["checked"]]
    errors = source_errors + [item for report in provider_reports.values() for item in report["errors"]]
    repairs = [item for report in provider_reports.values() for item in report["source_repairs"]]
    matches = deduplicate_jobs([
        item for report in provider_reports.values() for item in report["matches"]
    ])
    current_jobs = deduplicate_jobs_by_source([
        item for report in provider_reports.values() for item in report.get("_current_jobs", [])
    ])
    if persistence_jobs is not None:
        persistence_jobs.extend(current_jobs)
    if persistence_context is not None:
        persistence_context["jobs"] = current_jobs
        for key in ("fetch_evidence", "job_evidence", "job_evaluations"):
            report_key = f"_{key}"
            persistence_context[key] = [
                item
                for provider_report in provider_reports.values()
                for item in provider_report.get(report_key, [])
            ]
    total_raw = sum(report["total_raw_jobs"] for report in provider_reports.values())
    total_current = sum(report["total_current_jobs"] for report in provider_reports.values())
    greenhouse = provider_reports["greenhouse"]
    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "strategy": "Direct public ATS APIs with provider-specific adapters: Greenhouse, Lever, Ashby, and Workday.",
        "providers": {
            provider: {
                key: report[key]
                for key in (
                    "attempted", "successful", "total_raw_jobs", "total_current_jobs",
                    "total_dropped_jobs",
                )
            }
            for provider, report in provider_reports.items()
        },
        "checked": checked,
        "errors": errors,
        "source_repairs": repairs,
        "total_raw_jobs": total_raw,
        "total_current_jobs": total_current,
        "freshness_days": FRESHNESS_DAYS,
        "matches": matches,
        # Compatibility for consumers of the previous Greenhouse-only report.
        "skipped_non_greenhouse": [],
        "total_greenhouse_jobs": greenhouse["total_raw_jobs"],
        "total_recent_greenhouse_jobs": greenhouse["total_current_jobs"],
    }


def write_markdown(report: dict) -> None:
    attempted = sum(item["attempted"] for item in report["providers"].values())
    successful = sum(item["successful"] for item in report["providers"].values())
    lines = [
        f"# ATS API Job Scan - {report['generated_at']}", "", report["strategy"], "",
        f"ATS sources attempted: {attempted}",
        f"Successful ATS sources: {successful}",
        f"Total jobs fetched: {report['total_raw_jobs']}",
        f"Current or undated open jobs: {report['total_current_jobs']}",
        f"Matching jobs: {len(report['matches'])}",
        f"Endpoint/configuration errors: {len(report['errors'])}", "", "## Provider Coverage",
    ]
    for provider in PROVIDERS:
        item = report["providers"][provider]
        lines.append(
            f"- {provider.title()}: attempted {item['attempted']}, successful {item['successful']}, "
            f"fetched {item['total_raw_jobs']}, current/open {item['total_current_jobs']}"
        )
    lines.extend(["", "## Matches"])
    if not report["matches"]:
        lines.append("No matching India/remote early-career software roles found from mapped ATS APIs.")
    lines.extend(
        f"- {job['company']} - {job['title']} - {job['location']} - {job['source']} - {job['url']}"
        for job in report["matches"][:40]
    )
    if report["source_repairs"]:
        lines.extend(["", "## Automatic Source Normalization"])
        for item in report["source_repairs"][:30]:
            lines.append(f"- {item['company']} ({item['source']}): {'; '.join(item['repairs'])}")
    if report["errors"]:
        lines.extend(["", "## Endpoint and Configuration Errors"])
        for error in report["errors"][:40]:
            lines.append(
                f"- {error['company']} ({error['source']}:{error.get('slug', '')}): {error['error']}"
            )
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    persistence_context: dict[str, list[dict]] = {}
    report = scan(persistence_context=persistence_context)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_markdown(report)
    result = persist_report(
        report,
        persistence_context.get("jobs") or [],
        scan_kind="combined",
        fetch_evidence=persistence_context.get("fetch_evidence") or [],
        job_evidence=persistence_context.get("job_evidence") or [],
        job_evaluations=persistence_context.get("job_evaluations") or [],
    )
    if result.status == "error":
        print(f"ATS persistence error for combined scan: {result.error}", file=sys.stderr)
    elif result.status == "persisted":
        import logging
        logging.getLogger(__name__).info(f"Persisted {result.jobs_inserted} jobs to {result.scan_run_id}")
    print(MD_OUT.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
