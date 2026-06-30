# TOOLS.md - Main Agent Local Notes

This file is Main's local cheat sheet for Bhawani's OpenClaw setup. Keep it practical, current, and free of secrets.

## Important Paths

- OpenClaw config: `/home/node/.openclaw/openclaw.json`
- Cron jobs: `/home/node/.openclaw/cron/jobs.json`
- Cron state: `/home/node/.openclaw/cron/jobs-state.json`
- Cron run logs: `/home/node/.openclaw/cron/runs/*.jsonl`
- Main workspace: `/home/node/.openclaw/workspace/main`
- Shared workspace: `/home/node/.openclaw/workspace`

## Hardcore Placements Cron Jobs

- 8 AM company careers scan:
  - Job ID: `ea20f08d-4cbe-4d4d-a688-24b792f08358`
  - Name: `hardcore-placements-daily-company-careers-check`
  - Schedule: `0 8 * * *`, `Asia/Kolkata`
  - Purpose: full company career-page and ATS scan
- 2 PM platform jobs scan:
  - Job ID: `4beef526-a976-4773-aa7f-1b0e810bba6c`
  - Name: `hardcore-placements-daily-it-platform-jobs-scan`
  - Schedule: `0 14 * * *`, `Asia/Kolkata`
  - Purpose: public platform scan for fresher, intern, junior, and 0-2 year roles

## Telegram Targets

- Placements group: `-1003843321870`
- Owner direct chat: `1708887445`
- Tweet/draft direct chat: `7560331721`

Do not store bot tokens, OAuth tokens, device tokens, or private message contents here.

## Job Search Files

- ATS scan script: `/home/node/.openclaw/workspace/scripts/fetch_jobs_ats.py`
- Provider scripts: `fetch_jobs_greenhouse.py`, `fetch_jobs_lever.py`, `fetch_jobs_ashby.py`, and `fetch_jobs_workday.py` in the same directory
- Shared ATS schema/normalizer: `/home/node/.openclaw/workspace/scripts/ats_common.py`
- ATS crawl/retry policy: `/home/node/.openclaw/workspace/scripts/ats_crawl_policy.py`
- Optional ATS Postgres persistence: `/home/node/.openclaw/workspace/scripts/ats_supabase.py`
- Phase 1 migration: `/home/node/.openclaw/workspace/data/migrations/001_ats_phase1.sql`
- Phase 2 evidence/security migrations: `002_ats_phase2_evidence.sql` and `003_ats_phase2_security.sql` in the same directory
- Phase 3A verification schema migration: `004_ats_phase3a_verification_schema.sql` in the same directory
- Supabase env vars: `SUPABASE_DATABASE_URL` and optional IPv4 fallback `SUPABASE_POOLER_HOST`
- Supabase verification: `/home/node/.openclaw/workspace/scripts/verify_ats_supabase.py`
- Evidence query: `/home/node/.openclaw/workspace/scripts/query_ats_evidence.py`
- Local job verification: `/home/node/.openclaw/workspace/scripts/verify_ats_jobs.py`
- URL reachability verification: `/home/node/.openclaw/workspace/scripts/verify_ats_urls.py`
- Open/closed job classification: `/home/node/.openclaw/workspace/scripts/verify_ats_open_closed.py`
- Verification query: `/home/node/.openclaw/workspace/scripts/query_ats_verifications.py`
- ATS source list: `/home/node/.openclaw/workspace/data/ats_api_sources.json`
- Career-page source list: `/home/node/.openclaw/workspace/data/career_page_sources.json`
- Latest ATS scan markdown: `/home/node/.openclaw/workspace/memory/job_api_scan_latest.md`
- Latest ATS scan JSON: `/home/node/.openclaw/workspace/memory/job_api_scan_latest.json`
- 8 AM checkpoint: `/home/node/.openclaw/workspace/memory/checkpoint_ea20f08d.md`
- 2 PM checkpoint: `/home/node/.openclaw/workspace/memory/checkpoint_4beef526.md`
- Token/run notes: `/home/node/.openclaw/workspace/memory/token_usage_history.json`

## Safe Commands

- Validate cron JSON: `python3 -m json.tool /home/node/.openclaw/cron/jobs.json`
- Inspect hardcore jobs: `node -e 'const fs=require("fs"); const j=JSON.parse(fs.readFileSync("/home/node/.openclaw/cron/jobs.json","utf8")).jobs.filter(x=>x.name.startsWith("hardcore-placements-")); console.log(JSON.stringify(j.map(x=>({id:x.id,name:x.name,schedule:x.schedule,delivery:x.delivery,model:x.payload.model})),null,2))'`
- Run ATS helper: `python3 /home/node/.openclaw/workspace/scripts/fetch_jobs_ats.py`
- Verify ATS persistence: `python3 /home/node/.openclaw/workspace/scripts/verify_ats_supabase.py`
- Run local ATS job verification: `python3 /home/node/.openclaw/workspace/scripts/verify_ats_jobs.py --limit 2000`
- Run ATS URL reachability verification: `python3 /home/node/.openclaw/workspace/scripts/verify_ats_urls.py --limit 200`
- Run ATS open/closed classification: `python3 /home/node/.openclaw/workspace/scripts/verify_ats_open_closed.py --limit 2000`
- Query job decisions: `python3 /home/node/.openclaw/workspace/scripts/query_ats_evidence.py --view jobs --limit 50`
- Query source failures: `python3 /home/node/.openclaw/workspace/scripts/query_ats_evidence.py --view fetches --outcome error --limit 50`
- Query job verification results: `python3 /home/node/.openclaw/workspace/scripts/query_ats_verifications.py --latest --limit 50`
- Test ATS adapters: `python3 -m unittest discover -s /home/node/.openclaw/workspace/scripts/tests -v`
- Check recent cron state: read `/home/node/.openclaw/cron/jobs-state.json` before making conclusions.
- Export editable cron JSON: `node /home/node/.openclaw/workspace/main/scripts/export-cron-editable.mjs`
- Apply editable cron JSON: `node /home/node/.openclaw/workspace/main/scripts/apply-cron-editable.mjs`

## Operating Notes

- Cron jobs are database-first in this install. Do not expect direct edits to `/home/node/.openclaw/cron/jobs.json` to persist; use `/home/node/.openclaw/cron/jobs.editable.json` plus the export/apply scripts above for editor-based edits.
- For cron edits, preserve schedule, delivery, model, timeout, and agent fields unless Bhawani explicitly asks to change them.
- For Telegram-ready output, never include draft markers, internal notes, raw logs, or delivery status unless requested.
- For placement results, prefer current-looking links with clear India/remote and early-career signals.
- Exclude stale, senior-only, vague, non-engineering, or weak job matches.
