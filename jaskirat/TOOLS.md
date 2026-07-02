# TOOLS.md - Jaskirat Job Operations Notes

Keep this file practical, current, and free of secrets. Do not store bot tokens, OAuth tokens, device tokens, private DMs, resumes, or credentials here.

## Important Paths

- OpenClaw config: `/home/node/.openclaw/openclaw.json`
- Cron state and logs: `/home/node/.openclaw/cron/`
- Jaskirat workspace: `/home/node/.openclaw/workspace/jaskirat`
- Shared workspace: `/home/node/.openclaw/workspace`
- Shared job scripts: `/home/node/.openclaw/workspace/scripts/`
- Shared job data: `/home/node/.openclaw/workspace/data/`
- Shared job memory: `/home/node/.openclaw/workspace/memory/`

Note: cron files in this install may be migrated into OpenClaw shared state. Use active OpenClaw cron CLI/state APIs when editing or inspecting active cron jobs. Treat `.migrated` and `.bak` cron files as historical reference unless confirmed active.

## Telegram Targets

- Hardcore Placements group: `-1003843321870`
- Owner direct chat: `1708887445`

Personal job preference results should go to the user's private DM, not the group.

## Job Source Files

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
- Planned platform source list: `/home/node/.openclaw/workspace/data/job_platform_sources.json`
- Latest ATS scan markdown: `/home/node/.openclaw/workspace/memory/job_api_scan_latest.md`
- Latest ATS scan JSON: `/home/node/.openclaw/workspace/memory/job_api_scan_latest.json`
- Planned category outputs: `/home/node/.openclaw/workspace/memory/job_scans/`
- Planned user profiles: `/home/node/.openclaw/workspace/memory/job_users.json`
- Token/run notes: `/home/node/.openclaw/workspace/memory/token_usage_history.json`

## Job Categories

- Services: Accenture, Capgemini, Cognizant, LTIMindtree, Persistent, Mphasis, Hexaware, Virtusa, KPIT, and similar.
- Data/cloud/devtools: Databricks, Snowflake, MongoDB, Elastic, GitLab, HashiCorp, Vercel, Netlify, Postman, ClickHouse, and similar.
- AI: OpenAI, Anthropic, Cohere, Mistral AI, Hugging Face, Perplexity AI, LangChain, Scale AI, Glean, and similar.
- Cybersecurity: CrowdStrike, Palo Alto Networks, Fortinet, Zscaler, Cloudflare, Okta, SentinelOne, Check Point, Sophos, and similar.
- Gaming/media/creator-tech: gaming studios, creator platforms, streaming/media tech, and related engineering teams.
- Web3/fintech: Coinbase, Razorpay, PhonePe, Groww, Stripe, Brex, Mercury, and similar.
- ATS APIs: Greenhouse, Lever, Ashby, and Workday public endpoints.
- Platforms: Cutshort, Naukri, Wellfound, and similar public job platforms.
- Personal preference digest: filter all category results against stored DM user preferences.

## Safe Commands

- Validate JSON: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python -m json.tool /Users/bhawanisingh/.openclaw/workspace/data/ats_api_sources.json`
- Validate career sources: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python -m json.tool /Users/bhawanisingh/.openclaw/workspace/data/career_page_sources.json`
- Syntax-check ATS helpers: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python -m py_compile /Users/bhawanisingh/.openclaw/workspace/scripts/ats_common.py /Users/bhawanisingh/.openclaw/workspace/scripts/fetch_jobs_*.py`
- Run ATS helper: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/fetch_jobs_ats.py`
- Verify ATS persistence: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/verify_ats_supabase.py`
- Run local ATS job verification: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/verify_ats_jobs.py --limit 2000`
- Run ATS URL reachability verification: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/verify_ats_urls.py --limit 200`
- Run ATS open/closed classification: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/verify_ats_open_closed.py --limit 2000`
- Query job decisions: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/query_ats_evidence.py --view jobs --limit 50`
- Query source failures: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/query_ats_evidence.py --view fetches --outcome error --limit 50`
- Query job verification results: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/query_ats_verifications.py --latest --limit 50`
- Test ATS adapters: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python -m unittest discover -s /Users/bhawanisingh/.openclaw/workspace/scripts/tests -v`
- Inspect Jaskirat workspace changes: `git -C /Users/bhawanisingh/.openclaw/workspace/jaskirat status --short`
- Automate Application to ATS Job: `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/ats_apply.py <job_url>`
- Agentic Application (Universal LLM Browser): `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/stealth_applier/src/stealth_apply.py <job_url>`
- Submit Final Application (After Human Approval): `/Users/bhawanisingh/.openclaw/workspace/.venv/bin/python /Users/bhawanisingh/.openclaw/workspace/scripts/ats_submit.py <session_id>`

## STRICT BROWSER & APPLICATION RULES (CRITICAL)

- **DO NOT USE NATIVE BROWSER TOOLS**: Never attempt to use OpenClaw's native `web_fetch`, `web_search`, or `openclaw browser` CLI commands to visit the job link yourself! You MUST pass the URL directly as an argument to the python script!
- **DO NOT worry about missing Linux libraries or Chromium!** The browser actually runs completely outside your sandbox via the HostWorker on port 4555, so the python scripts WILL work perfectly. 
- **STRICT FAILURE HANDLING:** If the `agentic_apply.py` or `ats_apply.py` script fails for ANY reason (e.g., "Network is unreachable", "Connection refused", or any crash), DO NOT attempt any alternative methods, fallback scripts, or native CLI commands (like `openclaw browser open`). Immediately stop, tell the user on Telegram that the script failed, and provide them the exact error output so they can fix their local backend.
- **RESUME REQUIREMENT:** If there is no real `resume.pdf` in the workspace, you must politely demand that the user uploads their resume first before you run the application script.

If a command needs network and fails with a likely sandbox or network restriction, rerun only with the needed approval path.

## Output Rules

- Cron final responses must be the exact Telegram message to send.
- Do not include `[DRAFT]`, "ready for delivery", internal notes, tool logs, or delivery status text in cron outputs.
- Include company, title, location/remote eligibility, why it matches, and apply link.
- Deduplicate by company, title, and URL.
- Prefer official apply links and current-looking platform URLs.
- Say clearly when no strong current matches were found.

## Application Tailoring Templates

Use these shapes when helping a user apply to a specific role. Keep outputs concise enough for chat unless the user asks for a full document.

### JD Analysis

- Role snapshot: title, company, location/remote, seniority, likely team/domain.
- Must-have requirements: strongest explicit requirements from the JD.
- Nice-to-have requirements: optional or repeated preference signals.
- ATS keywords: tools, languages, frameworks, cloud, methods, degrees, certifications, domain terms.
- Responsibilities: what the person will actually do.
- Fit signals: what the recruiter is likely screening for.
- Risk flags: unclear location, high seniority, strong degree requirement, niche tool mismatch, or vague posting.

### Resume Customization

- Start with a 2-3 line tailored summary.
- Rewrite only bullets and skills that can be supported by the user's real background.
- Keep bullets in action + task + result form.
- Use `[ADD METRIC]` for missing numbers and `[ADD DETAIL]` for missing specifics.
- Add an "Do not claim unless true" note for skills or achievements implied by the JD but absent from the user's background.

### Role-Fit Matrix

Use compact bullets or a simple text matrix:

- Requirement: JD requirement.
- Evidence: matching user experience.
- Strength: strong, partial, weak, or missing.
- Resume focus: what to emphasize.
- Cover letter/interview story: how to frame it.

### Recruiter-Style Review

Give:

- Verdict: shortlist, maybe, or reject.
- Why: 3-5 concrete reasons.
- Fast fixes: highest-impact edits.
- Missing proof: metrics, projects, links, tools, or domain examples the user should add.
- Risk: any honest gap that may hurt screening.

### Interview Prep

Group likely questions into:

- Technical.
- Project/deep dive.
- Behavioral.
- Culture/company fit.

For each question, include what a strong answer should cover. For STAR answers, keep the structure explicit: Situation, Task, Action, Result. Do not invent the underlying story.

### Full Application Pack

When requested, produce:

1. JD analysis.
2. Tailored resume summary.
3. Rewritten bullets.
4. Skills alignment.
5. Cover letter.
6. Role-fit matrix.
7. Recruiter DM.
8. Follow-up email.
9. Likely interview questions.
10. STAR answer outlines.

If the user provides only a JD and no resume/background, produce the JD analysis first and ask for resume/background before writing personalized material.

## Quality Filters

Include:

- Software, AI, data, cloud, cybersecurity, QA/SDET, product-engineering, and related technical roles.
- Intern, fresher, graduate, new grad, junior, entry-level, 0-1, 0-2, and clearly suitable 0-3 year roles.
- India or globally remote roles.

Exclude:

- Senior, staff, principal, lead, manager, director roles.
- Sales, marketing, support-only, recruiter, finance, and unrelated roles.
- Expired, stale, duplicate, fake-looking, vague, or weak listings.
- Salary speculation and hype.

## Cron Editing Notes

Before modifying active cron behavior:

- Inspect active cron state and recent run logs.
- Preserve working schedule, delivery target, model, timeout, and agent fields unless Bhawani asks to change them.
- Avoid duplicate group posts when moving jobs from Main to Jaskirat.
- Validate JSON or CLI output after changes.
