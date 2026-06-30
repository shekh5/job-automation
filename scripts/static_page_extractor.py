#!/usr/bin/env python3
"""Static Page Extractor for Phase 4 ATS Pipeline.
Handles extracting job links and data from HTML content.
Priority: JSON-LD -> NEXT_DATA -> HTML Cards -> Anchor links
"""

import json
import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from ats_common import clean_text

def extract_jobs_from_html(html: str, base_url: str, company: str) -> List[Dict[str, Any]]:
    """Extract jobs from raw HTML using prioritized strategies."""
    soup = BeautifulSoup(html, "html.parser")
    
    # 1. JSON-LD Strategy
    jobs = _extract_from_jsonld(soup, base_url, company)
    if jobs:
        return jobs
        
    # 2. NEXT_DATA Strategy
    jobs = _extract_from_next_data(soup, base_url, company)
    if jobs:
        return jobs
        
    # 3. HTML Job Cards Strategy
    jobs = _extract_from_html_cards(soup, base_url, company)
    if jobs:
        return jobs
        
    # 4. Fallback: Anchor links
    return _extract_from_anchor_links(soup, base_url, company)

def _build_job(company: str, title: str, apply_url: str, location: str = "") -> Dict[str, Any]:
    return {
        "company": company,
        "title": clean_text(title),
        "location": clean_text(location) or "Unknown",
        "apply_url": apply_url,
        "job_url": apply_url,
        "source_id": apply_url.split("/")[-1] or apply_url,
        "provider": "static_career_page"
    }

def _extract_from_jsonld(soup: BeautifulSoup, base_url: str, company: str) -> List[Dict[str, Any]]:
    jobs = []
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict):
                data = [data]
            for item in data:
                if item.get("@type") == "JobPosting":
                    title = item.get("title", "")
                    url = item.get("url", "")
                    if not url:
                        # Sometimes JSON-LD is on the page itself
                        url = base_url
                    else:
                        url = urljoin(base_url, url)
                        
                    location = ""
                    loc_data = item.get("jobLocation")
                    if isinstance(loc_data, dict):
                        addr = loc_data.get("address", {})
                        if isinstance(addr, dict):
                            parts = [addr.get(k) for k in ("addressLocality", "addressRegion", "addressCountry") if addr.get(k)]
                            location = ", ".join(parts)
                    
                    if title and url:
                        jobs.append(_build_job(company, title, url, location))
        except json.JSONDecodeError:
            continue
    return jobs

def _extract_from_next_data(soup: BeautifulSoup, base_url: str, company: str) -> List[Dict[str, Any]]:
    jobs = []
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return jobs
        
    try:
        data = json.loads(script.string)
        # Deep search for arrays of items that look like jobs
        def find_job_arrays(obj: Any) -> None:
            if isinstance(obj, dict):
                # Check if this object looks like a job
                if "title" in obj and ("url" in obj or "id" in obj):
                    # Found a job-like dict
                    title = obj.get("title", "")
                    url = obj.get("url") or f"/jobs/{obj.get('id')}"
                    location = obj.get("location", "")
                    if title and isinstance(title, str) and url and isinstance(url, str):
                        full_url = urljoin(base_url, url)
                        jobs.append(_build_job(company, title, full_url, location))
                else:
                    for v in obj.values():
                        find_job_arrays(v)
            elif isinstance(obj, list):
                for item in obj:
                    find_job_arrays(item)

        find_job_arrays(data)
    except json.JSONDecodeError:
        pass
        
    return jobs

def _looks_like_job_link(url: str) -> bool:
    url_lower = url.lower()
    return "/job/" in url_lower or "/jobs/" in url_lower or "/careers/" in url_lower or "/position/" in url_lower or "/roles/" in url_lower

def _extract_from_html_cards(soup: BeautifulSoup, base_url: str, company: str) -> List[Dict[str, Any]]:
    jobs = []
    
    # Simple heuristic: find elements containing an anchor that looks like a job link,
    # along with some surrounding text indicating location/department.
    # Group them by common parent classes to identify "cards".
    
    links = soup.find_all("a", href=True)
    potential_job_links = []
    for a in links:
        href = a["href"]
        if _looks_like_job_link(href) and clean_text(a.get_text()):
            potential_job_links.append(a)
            
    if not potential_job_links:
        return jobs

    seen_urls = set()
    for a in potential_job_links:
        url = urljoin(base_url, a["href"])
        if url in seen_urls:
            continue
            
        title = a.get_text()
        
        # Try to find location by looking at siblings or parent siblings
        location = ""
        parent = a.find_parent(["div", "li", "tr"])
        if parent:
            # Look for typical location classes or text
            loc_elem = parent.find(["span", "div", "p"], class_=re.compile(r"loc|city|state|country", re.I))
            if loc_elem:
                location = loc_elem.get_text()
                
        jobs.append(_build_job(company, title, url, location))
        seen_urls.add(url)
        
    return jobs

def _extract_from_anchor_links(soup: BeautifulSoup, base_url: str, company: str) -> List[Dict[str, Any]]:
    # Very basic fallback: just grab all anchor links that match job patterns
    jobs = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = clean_text(a.get_text())
        if title and _looks_like_job_link(href):
            url = urljoin(base_url, href)
            if url not in seen:
                jobs.append(_build_job(company, title, url))
                seen.add(url)
    return jobs
