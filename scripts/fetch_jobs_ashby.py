#!/usr/bin/env python3
"""Ashby public Job Postings API adapter."""

from __future__ import annotations

import re
import sys
from typing import Any

from ats_common import (
    AdapterResult,
    fetch_json,
    is_current,
    nested,
    normalized_job,
    provider_main,
    relevant,
    unique_values,
)

PROVIDER = "ashby"


def prepare_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    prepared = dict(source)
    repairs: list[str] = []
    api_url = str(prepared.get("api_url") or "")
    slug = str(prepared.get("slug") or prepared.get("job_board_name") or "").strip()
    url = api_url or str(prepared.get("career_url") or "")
    match = re.search(r"/(?:job-board/)?([^/?]+)(?:\?|$)", url.rstrip("/"))
    if match and slug != match.group(1):
        repairs.append("job board name corrected from URL" if slug else "job board name inferred from URL")
        slug = match.group(1)
    if not slug:
        raise ValueError("Ashby source requires slug/job_board_name or an Ashby URL")
    if not api_url:
        api_url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
        repairs.append("api_url generated from job board name")
    prepared.update(slug=slug, api_url=api_url)
    return prepared, repairs


def normalize_job(raw: dict[str, Any], source: dict[str, Any], now=None) -> dict[str, Any]:
    secondary = [
        item.get("location") for item in raw.get("secondaryLocations") or []
        if isinstance(item, dict)
    ]
    locations = unique_values([raw.get("location"), secondary])
    return normalized_job(
        provider=PROVIDER,
        source=source,
        source_id=nested(raw, "id", "jobId", "jobPostingId"),
        title=nested(raw, "title", "name"),
        locations=locations,
        url=nested(raw, "applyUrl", "jobUrl", "url"),
        description=nested(raw, "descriptionPlain", "descriptionHtml", "description", default=""),
        department=nested(raw, "department", "departmentName"),
        team=nested(raw, "team", "teamName"),
        employment_type=nested(raw, "employmentType", "employment_type"),
        workplace_type=nested(raw, "workplaceType", "workplace_type", default="Remote" if raw.get("isRemote") else ""),
        published_at=nested(raw, "publishedAt", "published_at", "createdAt"),
        updated_at=nested(raw, "updatedAt", "updated_at"),
        now=now,
    )


def scan_source(source: dict[str, Any]) -> AdapterResult:
    prepared, repairs = prepare_source(source)
    payload = fetch_json(prepared["api_url"])
    raw_jobs = nested(payload, "jobs", "data.jobs", "results", default=payload if isinstance(payload, list) else [])
    if not isinstance(raw_jobs, list):
        raise ValueError("Ashby response has no jobs array")
    jobs: list[dict[str, Any]] = []
    current_jobs: list[dict[str, Any]] = []
    job_evidence: list[dict[str, Any]] = []
    current_count = dropped = 0
    for raw in raw_jobs:
        if not isinstance(raw, dict) or raw.get("isListed") is False:
            dropped += 1
            continue
        if not is_current(raw.get("publishedAt"), raw.get("updatedAt")):
            continue
        current_count += 1
        try:
            job = normalize_job(raw, prepared)
        except ValueError:
            dropped += 1
            continue
        current_jobs.append(job)
        job_evidence.append({
            "job_key": f"{job['source']}:{job['source_id']}",
            "normalized_job": job,
            "raw_job": raw,
        })
        context = f"{job['department']} {job['team']} {job['employment_type']} {job['description']}"
        if relevant(job["title"], job["location"], context):
            jobs.append(job)
    return AdapterResult(jobs, len(raw_jobs), current_count, dropped, repairs, current_jobs, job_evidence)


if __name__ == "__main__":
    sys.exit(provider_main(PROVIDER, scan_source))
