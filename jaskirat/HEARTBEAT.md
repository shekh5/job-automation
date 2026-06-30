# HEARTBEAT.md - Jaskirat Job Checks

Use heartbeat turns for quiet job-automation monitoring. Stay silent with `HEARTBEAT_OK` when there is nothing useful to report.

## Check First

- Inspect Jaskirat job cron health using active OpenClaw cron state plus recent `cron/runs/*.jsonl` logs.
- Watch for repeated failures, missed deliveries, stale scan outputs, stuck checkpoints, model/tool errors, or broken ATS endpoints.
- Check shared job outputs:
  - `/home/node/.openclaw/workspace/memory/job_api_scan_latest.md`
  - `/home/node/.openclaw/workspace/memory/job_api_scan_latest.json`
  - `/home/node/.openclaw/workspace/memory/job_scans/`
  - `/home/node/.openclaw/workspace/memory/job_users.json`
- Notice weak results: stale links, senior-only results, duplicate posts, noisy platform results, or scans that return too few high-confidence jobs.
- Notice Telegram delivery issues only when they affect job alerts or placement reports.

## When To Notify Bhawani

Notify only for actionable job-automation issues:

- A Jaskirat job cron fails or misses delivery twice in a row.
- A scan output is stale, empty, noisy, or clearly below quality expectations.
- Telegram delivery fails for a job group post or personal job DM.
- ATS/API scans start failing for many sources.
- A personal preference digest cannot run because the user profile file is missing or malformed.
- Auth, model, browser, web, or network errors block job automation.

## How To Report

Keep reports short:

- What failed or changed.
- Affected job, category, file, or user profile.
- Last run time, next expected run time, and delivery status if known.
- Recommended next action.

Do not include secrets, raw tokens, private DMs, resumes, long logs, or full job outputs unless Bhawani asks.

## Quiet Rules

- Reply `HEARTBEAT_OK` if monitored job automation is healthy.
- Do not post jobs or send external messages during heartbeat unless explicitly instructed.
- Do not edit cron jobs, credentials, permissions, source lists, or user profiles during heartbeat unless explicitly instructed.
- Avoid late-night noise unless repeated failure or privacy/security risk needs attention.
