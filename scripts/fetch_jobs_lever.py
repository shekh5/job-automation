#!/usr/bin/env python3
"""Lever public Postings API adapter."""

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

PROVIDER = "lever"


def prepare_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    prepared = dict(source)
    repairs: list[str] = []
    api_url = str(prepared.get("api_url") or "")
    slug = str(prepared.get("slug") or "").strip()
    match = re.search(r"/postings/([^/?]+)", api_url)
    if match and slug != match.group(1):
        repairs.append("slug corrected from api_url" if slug else "slug inferred from api_url")
        slug = match.group(1)
    if not slug:
        raise ValueError("Lever source requires slug or a /postings/{slug} api_url")
    if not api_url:
        host = "api.eu.lever.co" if str(prepared.get("region") or "").lower() == "eu" else "api.lever.co"
        api_url = f"https://{host}/v0/postings/{slug}?mode=json"
        repairs.append("api_url generated from slug and region")
    elif "mode=json" not in api_url.lower():
        api_url += "&mode=json" if "?" in api_url else "?mode=json"
        repairs.append("mode=json added to api_url")
    prepared.update(slug=slug, api_url=api_url)
    return prepared, repairs


def normalize_job(raw: dict[str, Any], source: dict[str, Any], now=None) -> dict[str, Any]:
    categories = raw.get("categories") if isinstance(raw.get("categories"), dict) else {}
    locations = unique_values([
        categories.get("location"), categories.get("allLocations"),
        raw.get("location"), raw.get("locations"),
    ])
    description = nested(raw, "descriptionPlain", "descriptionBodyPlain", "description", "openingPlain", default="")
    return normalized_job(
        provider=PROVIDER,
        source=source,
        source_id=nested(raw, "id", "postingId", "requisitionId"),
        title=nested(raw, "text", "title", "name"),
        locations=locations,
        url=nested(raw, "applyUrl", "hostedUrl", "absolute_url", "url"),
        description=description,
        department=nested(categories, "department", default=raw.get("department")),
        team=nested(categories, "team", default=raw.get("team")),
        employment_type=nested(categories, "commitment", default=raw.get("commitment")),
        workplace_type=nested(raw, "workplaceType", "workplace_type"),
        published_at=nested(raw, "createdAt", "publishedAt", "created_at"),
        updated_at=nested(raw, "updatedAt", "updated_at"),
        now=now,
    )


def scan_source(source: dict[str, Any]) -> AdapterResult:
    prepared, repairs = prepare_source(source)
    payload = fetch_json(prepared["api_url"])
    raw_jobs = nested(
        payload, "data.postings", "data.jobs", "postings", "jobs",
        default=payload if isinstance(payload, list) else [],
    )
    if not isinstance(raw_jobs, list):
        raise ValueError("Lever response has no postings array")
    jobs: list[dict[str, Any]] = []
    current_jobs: list[dict[str, Any]] = []
    job_evidence: list[dict[str, Any]] = []
    current_count = dropped = 0
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        if not is_current(raw.get("createdAt"), raw.get("updatedAt")):
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
