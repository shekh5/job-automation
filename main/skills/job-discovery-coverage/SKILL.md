---
name: "job-discovery-coverage"
description: "Maximize job discovery coverage with ATS, scraping, fallback search, and gap logging."
---

# Job Discovery Coverage

Use this skill when the goal is to find as many relevant jobs as possible without losing quality.

## What this skill does

- Pulls jobs from ATS APIs carefully and consistently.
- Scrapes official career pages in a controlled way.
- Uses targeted search only when source data is incomplete.
- Deduplicates results across ATS, career pages, and platforms.
- Detects coverage gaps and records missed sources.
- Keeps the search focused on current, early-career roles.

## Core principle

Coverage matters, but only if quality stays intact.
Do not pad results with stale or weak jobs just to raise the count.

## Discovery order

Prefer sources in this order:

1. Official ATS APIs.
2. Official company career pages.
3. Specific public job-platform listings.
4. Targeted search snippets when the page or API is unclear.

If one source is weak, try another before dropping the company.
If all sources fail, log the gap so the next run can improve coverage.

## ATS workflow

When using ATS sources:

- load the current ATS source list first
- verify the ATS endpoint still responds
- check whether the source returns current-looking roles
- keep the query narrow enough to avoid noise
- keep only roles with clear title, company, location, and apply path
- flag sources that repeatedly return nothing useful

## Career-page scraping workflow

When using career pages:

- open the official company career page first
- follow internal job listings rather than broad marketing pages
- prefer listing pages with stable apply URLs
- use search only if the page is hard to navigate or hides jobs behind filters
- avoid over-scraping when a listing page already gives enough signal

## Fallback search workflow

Use search only when needed:

- to find a current listing URL
- to confirm location or early-career status
- to recover from broken ATS or career-page navigation
- to cross-check stale or ambiguous results

Do not let search become the default source when a direct source exists.

## Deduplication rules

Remove duplicates across all sources using:

- company name
- title
- apply URL
- listing ID when available

If two sources describe the same role, keep the stronger and more direct source.

## Gap logging

When coverage is missing, record a short gap note:

- company or source name
- what failed
- what was tried
- what to try next run

This should help future scans recover the missing coverage instead of repeating the same failure.

## Quality rules

Keep only jobs that are:

- current-looking
- software, AI, data, cloud, security, QA/SDET, or product-engineering related
- early-career or clearly suitable for juniors
- backed by a current-looking URL or listing path

Exclude jobs that are:

- stale or expired
- senior-only or unrelated
- vague category pages with no actual jobs
- duplicates or weak snippets with no clear apply path

## Output style

When reporting discovery work:

- say what sources were checked
- note which sources failed or were thin
- note whether fallback search was used
- say how many jobs were kept
- keep the report compact and operational

## Self-check loop

Before finishing, verify:

- Did I check ATS sources first?
- Did I scrape official career pages when needed?
- Did I use search only as fallback?
- Did I deduplicate across source types?
- Did I keep only current, relevant, early-career roles?
- Did I log coverage gaps that matter next time?

If any answer is no, revise once.

## Skill boundary

This skill is for coverage and discovery quality.
It is not for personal onboarding, final Telegram formatting, or long-term source list editing.
