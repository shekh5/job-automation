#!/usr/bin/env python3
"""Workday public career-site CXS adapter."""

from __future__ import annotations

import re
import sys
from typing import Any
from urllib.parse import urlparse

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

PROVIDER = "workday"
PAGE_SIZE = 20


def prepare_source(source: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    prepared = dict(source)
    repairs: list[str] = []
    api_url = str(prepared.get("api_url") or "")
    career_url = str(prepared.get("career_url") or "")
    parsed = urlparse(api_url or career_url)
    host = str(prepared.get("host") or parsed.netloc).strip()
    tenant = str(prepared.get("tenant") or "").strip()
    site = str(prepared.get("site") or prepared.get("slug") or "").strip()
    cxs_match = re.search(r"/wday/cxs/([^/]+)/([^/]+)/jobs", parsed.path)
    if cxs_match:
        if tenant != cxs_match.group(1):
            repairs.append("tenant corrected from api_url" if tenant else "tenant inferred from api_url")
            tenant = cxs_match.group(1)
        if site != cxs_match.group(2):
            repairs.append("site corrected from api_url" if site else "site inferred from api_url")
            site = cxs_match.group(2)
    if not tenant and host:
        tenant = host.split(".", 1)[0]
        repairs.append("tenant inferred from Workday hostname")
    if not site and career_url:
        parts = [part for part in urlparse(career_url).path.split("/") if part]
        parts = [part for part in parts if not re.fullmatch(r"[a-z]{2}-[A-Z]{2}", part)]
        if parts:
            site = parts[-1]
            repairs.append("site inferred from career_url")
    if not host or not tenant or not site:
        raise ValueError("Workday source requires host, tenant, and site, or a parseable Workday URL")
    if not api_url:
        api_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
        repairs.append("api_url generated from host, tenant, and site")
    if not career_url:
        career_url = f"https://{host}/{site}"
        repairs.append("career_url generated from host and site")
    prepared.update(host=host, tenant=tenant, site=site, slug=site, api_url=api_url, career_url=career_url.rstrip("/"))
    return prepared, repairs


def normalize_job(raw: dict[str, Any], source: dict[str, Any], now=None) -> dict[str, Any]:
    external_path = str(nested(raw, "externalPath", "external_path", default=""))
    url = nested(raw, "applyUrl", "externalUrl", "jobUrl", "url")
    if not url and external_path:
        if re.match(r"^/[a-z]{2}-[A-Z]{2}/", external_path):
            url = f"https://{source['host']}{external_path}"
        else:
            url = f"{source['career_url']}/{external_path.lstrip('/')}"
    locations = unique_values([
        nested(raw, "locationsText", "location", "primaryLocation"),
        raw.get("locations"),
    ])
    bullet_fields = raw.get("bulletFields") or []
    context = " ".join(unique_values(bullet_fields if isinstance(bullet_fields, list) else [bullet_fields]))
    return normalized_job(
        provider=PROVIDER,
        source=source,
        source_id=nested(raw, "id", "jobId", "requisitionId", default=external_path),
        title=nested(raw, "title", "jobTitle", "name"),
        locations=locations,
        url=url,
        description=nested(raw, "jobDescription", "description", default=context),
        department=nested(raw, "department", "jobFamily"),
        employment_type=nested(raw, "timeType", "employmentType", default=context),
        workplace_type=nested(raw, "workplaceType", "remoteType"),
        published_at=nested(raw, "postedOn", "postedDate", "startDate"),
        updated_at=nested(raw, "updatedAt", "updated_at"),
        now=now,
    )


def scan_source(source: dict[str, Any]) -> AdapterResult:
    prepared, repairs = prepare_source(source)
    raw_jobs: list[Any] = []
    offset = 0
    total: int | None = None
    while total is None or offset < total:
        payload = fetch_json(prepared["api_url"], {
            "appliedFacets": prepared.get("applied_facets") or {},
            "limit": PAGE_SIZE,
            "offset": offset,
            "searchText": str(prepared.get("search_text") or ""),
        })
        page = nested(payload, "jobPostings", "data.jobPostings", "jobs", default=[])
        if not isinstance(page, list):
            raise ValueError("Workday response has no jobPostings array")
        raw_jobs.extend(page)
        total_value = nested(payload, "total", "data.total", default=len(raw_jobs))
        try:
            total = int(total_value)
        except (TypeError, ValueError):
            total = len(raw_jobs)
        if not page or len(page) < PAGE_SIZE:
            break
        offset += len(page)
    jobs: list[dict[str, Any]] = []
    current_jobs: list[dict[str, Any]] = []
    job_evidence: list[dict[str, Any]] = []
    current_count = dropped = 0
    for raw in raw_jobs:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        if not is_current(raw.get("postedOn"), raw.get("postedDate"), raw.get("updatedAt")):
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
        if relevant(job["title"], job["location"], f"{job['employment_type']} {job['description']}"):
            jobs.append(job)
    return AdapterResult(jobs, len(raw_jobs), current_count, dropped, repairs, current_jobs, job_evidence)


if __name__ == "__main__":
    sys.exit(provider_main(PROVIDER, scan_source))
