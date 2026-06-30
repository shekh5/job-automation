#!/usr/bin/env python3
"""Greenhouse Job Board API adapter."""

from __future__ import annotations

import re
import sys
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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

PROVIDER = "greenhouse"


def prepare_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    prepared = dict(source)
    repairs: list[str] = []
    api_url = str(prepared.get("api_url") or "")
    slug = str(prepared.get("slug") or "").strip()
    match = re.search(r"/boards/([^/]+)/jobs", api_url)
    if match and slug != match.group(1):
        repairs.append("slug corrected from api_url" if slug else "slug inferred from api_url")
        slug = match.group(1)
    if not slug:
        raise ValueError("Greenhouse source requires slug or a /boards/{slug}/jobs api_url")
    if not api_url:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
        repairs.append("api_url generated from slug")
    parsed = urlparse(api_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    if query.get("content") != "true":
        query["content"] = "true"
        repairs.append("content=true added for descriptions and organization fields")
    prepared.update(slug=slug, api_url=urlunparse(parsed._replace(query=urlencode(query))))
    return prepared, repairs


def metadata_values(job: dict[str, Any], allowed_names: set[str]) -> list[str]:
    values: list[Any] = []
    for item in job.get("metadata") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("name") or "").strip().lower() in allowed_names:
            value = item.get("value")
            values.extend(value if isinstance(value, list) else [value])
    return unique_values(values)


def normalize_job(raw: dict[str, Any], source: dict[str, Any], now=None) -> dict[str, Any]:
    metadata_locations = metadata_values(raw, {"job posting location", "location"})
    locations: list[Any] = metadata_locations + [nested(raw, "location.name", "location")]
    locations.extend(
        nested(office, "location", "name")
        for office in raw.get("offices") or []
        if isinstance(office, dict)
    )
    departments = unique_values([
        department.get("name") for department in raw.get("departments") or []
        if isinstance(department, dict)
    ])
    context = unique_values(
        metadata_values(raw, {"career site department", "cost center"}) + departments
    )
    return normalized_job(
        provider=PROVIDER,
        source=source,
        source_id=nested(raw, "id", "job_id", "requisition_id"),
        title=nested(raw, "title", "name"),
        locations=locations,
        url=nested(raw, "absolute_url", "apply_url", "url"),
        description=nested(raw, "content", "description", default=""),
        department="; ".join(context),
        published_at=nested(raw, "first_published", "published_at", "created_at"),
        updated_at=nested(raw, "updated_at", "last_updated"),
        now=now,
    )


def scan_source(source: dict[str, Any]) -> AdapterResult:
    prepared, repairs = prepare_source(source)
    payload = fetch_json(prepared["api_url"])
    raw_jobs = nested(payload, "jobs", "data.jobs", "results", default=payload if isinstance(payload, list) else [])
    if not isinstance(raw_jobs, list):
        raise ValueError("Greenhouse response has no jobs array")
    jobs: list[dict[str, Any]] = []
    current_jobs: list[dict[str, Any]] = []
    job_evidence: list[dict[str, Any]] = []
    current_count = dropped = 0
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        if not is_current(raw.get("first_published"), raw.get("updated_at")):
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
        if relevant(job["title"], job["location"], f"{job['department']} {job['description']}"):
            jobs.append(job)
    return AdapterResult(jobs, len(raw_jobs), current_count, dropped, repairs, current_jobs, job_evidence)


if __name__ == "__main__":
    sys.exit(provider_main(PROVIDER, scan_source))
