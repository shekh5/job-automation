# HEARTBEAT.md - Main Agent Checks

Use heartbeat turns for quiet operational monitoring. Stay silent with `HEARTBEAT_OK` when there is nothing useful to report.

## Check First

- Inspect cron health: `cron/jobs-state.json`, recent `cron/runs/*.jsonl`, and delivery status.
- Watch the hardcore placements jobs:
  - `hardcore-placements-daily-company-careers-check`
  - `hardcore-placements-daily-it-platform-jobs-scan`
- Check for repeated failures, missed deliveries, stuck checkpoints, or stale job-scan outputs.
- Notice pending device or permission issues only when they affect operations.

## When To Notify Bhawani

Notify only for actionable items:

- A cron job fails or misses delivery twice in a row.
- The 8 AM or 2 PM hardcore placements job returns weak/stale/noisy results.
- Telegram delivery fails for a placement job.
- Auth/model/tool errors block automation.
- A pending device/admin request needs an explicit decision.

## How To Report

Keep reports short:

- what failed or changed
- affected job or file
- last run time, next run time, and delivery status if relevant
- recommended next action

Do not include secrets, raw tokens, long logs, or full job outputs unless asked.

## Quiet Rules

- Reply `HEARTBEAT_OK` if all monitored jobs are healthy.
- Do not post to Telegram or external services during heartbeat.
- Do not modify cron jobs, credentials, permissions, or public behavior without clear instruction.
- Avoid late-night noise unless a repeated failure or security-sensitive issue needs attention.
