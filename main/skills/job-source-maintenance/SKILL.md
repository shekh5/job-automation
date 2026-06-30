---
name: "job-source-maintenance"
description: "Maintain ATS, career-page, and platform sources for fresh early-career job scans."
---

# Job Source Maintenance

Use this skill when the job scan pipeline needs cleaner sources, fresher links, better ATS coverage, or a maintained company watchlist.

## What this skill does

- Keeps ATS source lists current.
- Keeps company career-page lists current.
- Keeps public job-platform sources current.
- Removes dead, stale, duplicate, or low-signal sources.
- Verifies that source URLs still point to relevant job pages.
- Preserves a clean source inventory for downstream scans.

## When to use

Use this skill when:

- a company career page changes
- an ATS endpoint breaks or moves
- a platform source starts returning stale results
- a source list grows noisy or duplicated
- scans are missing obvious early-career jobs because sources are outdated

## Maintenance workflow

1. Read the current source files before changing anything.
2. Check whether each source is still current-looking and relevant.
3. Verify the source type: ATS, company career page, or public platform.
4. Prefer official URLs and stable listing paths.
5. Remove or flag broken, stale, duplicated, or vague sources.
6. Keep only sources that help find India or globally remote early-career roles.
7. Save the updated source list and record what changed.

## Source quality rules

Keep sources that:

- are official or strongly specific
- return current-looking openings
- support software, AI, data, cloud, security, QA/SDET, or product-engineering roles
- have clear company identity and a usable URL

Remove sources that:

- are dead or redirect loops
- only show senior roles
- are vague category pages with no useful filters
- duplicate another source with no added coverage
- repeatedly produce stale or weak results

## Output style

When reporting source maintenance:

- be concise
- list what changed
- mention broken or removed sources clearly
- mention any newly added source and why it helps
- say when no changes were needed

## Downstream compatibility

Keep maintained source files compatible with the job discovery workflow.
Do not introduce source shapes that break current scans unless the scan pipeline is updated at the same time.

## Self-check loop

Before finishing, verify:

- Did I inspect current source files first?
- Did I keep only useful sources?
- Did I remove dead or noisy entries?
- Did I preserve coverage for early-career roles?
- Did I avoid introducing duplicates or ambiguous URLs?

If any answer is no, revise once before finishing.

## Skill boundaries

This skill is for source inventory hygiene and maintenance.
It is not for writing scan prompts, personal user profiling, or final Telegram job reports.
