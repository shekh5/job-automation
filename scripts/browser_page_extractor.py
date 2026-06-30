#!/usr/bin/env python3
"""Browser Page Extractor for Phase 5 ATS Pipeline.

Parses fully rendered HTML (from Playwright) to extract jobs and detect
access controls (CAPTCHA, login walls, rate limits).
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from ats_common import clean_text

def looks_like_captcha(soup: BeautifulSoup) -> bool:
    """Detect common CAPTCHA / anti-bot challenges in the rendered DOM."""
    # Look for common captcha identifiers
    captcha_classes = soup.find_all(class_=re.compile(r"captcha|cf-turnstile", re.I))
    if captcha_classes:
        return True
        
    text = soup.get_text().lower()
    bot_phrases = [
        "please verify you are human",
        "checking if the site connection is secure",
        "pardon the interruption",
        "one more step",
        "we need to make sure you're not a robot",
        "cloudflare ray id",
        "are you a robot"
    ]
    for phrase in bot_phrases:
        if phrase in text:
            return True
            
    return False

def looks_like_login_wall(soup: BeautifulSoup) -> bool:
    """Detect if the page is just a login wall instead of a public career page."""
    # Look for generic sign-in requirements if there are no job links
    text = soup.get_text().lower()
    login_phrases = [
        "you must sign in to view this page",
        "please log in to continue",
        "sign in to your account"
    ]
    for phrase in login_phrases:
        if phrase in text:
            return True
            
    # Check for prominent password fields without other content
    password_fields = soup.find_all("input", type="password")
    if password_fields and len(soup.get_text()) < 1000: # Very small page with password field
        return True
        
    return False

def extract_jobs_from_dom(html: str, base_url: str, company: str) -> dict[str, Any]:
    """Parse the fully rendered DOM to find job listings."""
    soup = BeautifulSoup(html, "html.parser")
    
    # 1. Check for access blocks
    if looks_like_captcha(soup):
        return {"status": "blocked", "reason": "captcha_detected", "jobs": []}
        
    if looks_like_login_wall(soup):
        return {"status": "blocked", "reason": "login_wall_detected", "jobs": []}
        
    jobs = []
    seen_urls = set()
    
    # 2. Extract using anchor heuristics (similar to static extraction but on rendered DOM)
    links = soup.find_all("a", href=True)
    for a in links:
        href = a["href"]
        href_lower = href.lower()
        if "/job/" in href_lower or "/jobs/" in href_lower or "/careers/" in href_lower or "/position/" in href_lower or "/roles/" in href_lower:
            url = urljoin(base_url, href)
            
            # Skip pagination or sorting links
            if "?" in href and ("page=" in href_lower or "sort=" in href_lower):
                continue
                
            if url in seen_urls:
                continue
                
            title = clean_text(a.get_text())
            if not title:
                continue
                
            location = ""
            parent = a.find_parent(["div", "li", "tr", "td"])
            if parent:
                loc_elem = parent.find(["span", "div", "p", "td"], class_=re.compile(r"loc|city|state|country", re.I))
                if loc_elem:
                    location = loc_elem.get_text()
            
            job = {
                "company": company,
                "title": title,
                "location": clean_text(location) or "Unknown",
                "apply_url": url,
                "job_url": url,
                "source_id": url.split("/")[-1].split("?")[0] or url,
                "provider": "browser_rendered_page"
            }
            jobs.append(job)
            seen_urls.add(url)
            
    return {"status": "success", "jobs": jobs}
