# Full Handoff And Next Implementation Plan

## Purpose

This file is the complete handoff for the Telegram + laptop Chrome job apply automation project. It captures the previous context, current implementation state, how to run and test the system, what has already been completed, current limitations, and the next detailed implementation plan.

The goal is to let another Codex session or engineer continue without needing the previous chat history.

## Project Goal

Build a Telegram-driven job application assistant.

The intended user flow:

```text
User sends a job apply link in Telegram
-> Telegram bot detects the link
-> Apply Engine creates user/job/application state
-> Apply Engine calls laptop Host Chrome Worker
-> Host Worker opens visible Chrome through Playwright
-> Automation fills safe profile fields
-> User handles login, OTP, CAPTCHA, sensitive fields, and final approval
-> Application status is tracked locally
```

The system should reduce repetitive job application work while keeping the user in control of private and risky steps.

## Decisions Locked So Far

- Telegram is the main user interface.
- Browser automation runs on the laptop host, outside Docker.
- OpenClaw/Docker backend calls the laptop worker over HTTP.
- Visible Chrome is preferred over headless Chrome for reliability and manual intervention.
- Passwords should preferably be entered manually in visible Chrome.
- Telegram one-time credentials may be supported later with strict no-store/no-log rules.
- Final submit must always require explicit user approval.
- The first ATS targets are Lever, Greenhouse, and Ashby.
- Workday is deferred because it is more complex and fragile.
- Telegram Mini App browser streaming is deferred until the simpler laptop Chrome flow is solid.

## Existing Documentation

Detailed docs already exist here:

- `workspace/main/telegram-apply-engine/docs/01-requirements.md`
- `workspace/main/telegram-apply-engine/docs/02-functional-spec.md`
- `workspace/main/telegram-apply-engine/docs/03-technical-design.md`
- `workspace/main/telegram-apply-engine/docs/04-data-model.md`
- `workspace/main/telegram-apply-engine/docs/05-security-policy.md`
- `workspace/main/telegram-apply-engine/docs/06-testing-plan.md`
- `workspace/main/telegram-apply-engine/docs/07-runbook.md`

This file is the single consolidated continuation handoff.

## Architecture

```text
Telegram Bot
  -> Apply Engine API
      -> SQLite state store
      -> Host Worker HTTP client
  -> Host Chrome Worker on laptop
      -> Playwright persistent Chrome context
      -> Visible Chrome
      -> Generic form filler
```

Runtime modes:

- Local laptop mode:
  - backend and host worker both run on laptop
  - `HOST_WORKER_URL=http://127.0.0.1:4555`

- Docker backend to laptop worker mode:
  - OpenClaw/apply backend runs in Docker
  - host worker runs on laptop host
  - `HOST_WORKER_URL=http://host.docker.internal:4555`

## Implemented So Far

### Documentation Package

Created the base documentation set under `workspace/main/telegram-apply-engine/docs/`.

Docs cover:

- requirements
- functional spec
- technical design
- data model
- security policy
- test plan
- runbook

### Test Isolation Fix

The persistent SQLite duplicate issue was fixed.

Before:

- tests used the real/persistent `data/apply-engine.sqlite`
- repeated test runs could fail because `applications` has `UNIQUE(user_id, job_id)`

Now:

- `NODE_ENV=test` defaults DB to `:memory:`
- `resetDbForTests()` resets test DB safely
- repeated test runs are stable

Important file:

- `workspace/main/telegram-apply-engine/src/db/db.ts`

### Host Chrome Worker MVP

Implemented a laptop host worker.

Important files:

- `workspace/main/telegram-apply-engine/src/host-worker/server.ts`
- `workspace/main/telegram-apply-engine/src/host-worker/sessionManager.ts`

NPM script:

```bash
npm --prefix workspace/main/telegram-apply-engine run host-worker
```

Implemented endpoints:

```http
GET /health
GET /sessions
POST /sessions
GET /sessions/:id/status
POST /sessions/:id/navigate
POST /sessions/:id/fill
POST /sessions/:id/close
```

Behavior:

- launches Playwright persistent browser context
- uses visible Chrome by default
- supports `headless: true` for tests
- tracks browser session status
- supports navigation
- can close sessions cleanly

### Apply Engine To Host Worker Bridge

Backend now calls the host worker when `HOST_WORKER_URL` is configured.

Important files:

- `workspace/main/telegram-apply-engine/src/server.ts`
- `workspace/main/telegram-apply-engine/src/apply/hostWorkerClient.ts`
- `workspace/main/telegram-apply-engine/src/apply/events.ts`

Implemented backend behavior:

- `/api/apply/start` supports existing `job_id`
- `/api/apply/start` supports direct `application_url`
- direct URL flow auto-creates a job record
- direct URL flow auto-registers the user if missing
- application events are written to SQLite
- host worker failures update application status to `failed`
- retry endpoint exists

Backend endpoints:

```http
POST /api/apply/start
POST /api/apply/:id/open-browser
POST /api/apply/:id/fill
GET /api/apply/:id/status
```

### Telegram Bot Integration

The Telegram bot can now detect direct job apply links and start the apply workflow.

Important files:

- `workspace/main/telegram-apply-engine/src/bot/bot.ts`
- `workspace/main/telegram-apply-engine/src/bot/handlers.ts`
- `workspace/main/telegram-apply-engine/src/bot/applyEngineClient.ts`

Implemented behavior:

- `/start` registers Telegram user
- direct HTTP/HTTPS URL messages are detected
- bot calls Apply Engine `/api/apply/start`
- bot sends application ID and status
- bot sends inline controls:
  - `Check Status`
  - `Open Browser Again`
- callbacks call backend status/retry APIs

### Local End-To-End Smoke Test

The local backend-to-host-worker chain was verified.

Smoke setup used:

- host worker on `127.0.0.1:4555`
- backend on `127.0.0.1:4100` because port `4000` was already busy
- direct URL: `https://example.com`

Smoke request:

```bash
curl -X POST http://127.0.0.1:4100/api/apply/start \
  -H 'Content-Type: application/json' \
  -d '{"telegram_user_id":"smoke_user","application_url":"https://example.com"}'
```

Smoke response:

```json
{"application_id":"app_1782291748709_xx43v1","status":"opening","host_worker_requested":true}
```

Host worker confirmed:

```json
{
  "profile_id": "user_smoke_user",
  "status": "ready",
  "current_url": "https://example.com/",
  "error": null
}
```

Meaning:

```text
Backend API
-> Host Chrome Worker
-> Visible Chrome session
-> URL opened successfully
```

### Basic Form Filling MVP

Basic form filling now exists on the host worker.

Important file:

- `workspace/main/telegram-apply-engine/src/host-worker/formFiller.ts`

Supported profile fields:

- `first_name`
- `last_name`
- `full_name`
- `email`
- `phone`
- `location`
- `linkedin_url`
- `github_url`
- `portfolio_url`

Matching sources:

- label text
- placeholder
- `aria-label`
- input `name`
- input `id`

Supported elements:

- `input[type=text]`
- `input[type=email]`
- `input[type=tel]`
- `input[type=url]`
- `input[type=search]`
- `textarea`

Safety behavior:

- does not click submit
- skips disabled fields
- skips read-only fields
- skips already-filled fields
- skips unsupported input types

Current limitation:

- Telegram still does not expose a fill button or automatic fill trigger yet.
- Profile management is implemented as an MVP API plus Telegram guided setup, not a polished UI.

### Backend Profile-Based Fill Orchestration

Backend can now call the host worker fill endpoint using the user's saved profile.

Important files:

- `workspace/main/telegram-apply-engine/src/server.ts`
- `workspace/main/telegram-apply-engine/src/apply/hostWorkerClient.ts`

Implemented backend endpoint:

```http
POST /api/apply/:id/fill
```

Behavior:

- loads saved profile from `user_profiles.profile_json`
- calls host worker `POST /sessions/:id/fill`
- updates application status to `filling` while fill is running
- updates application status to `awaiting_review` after successful fill
- updates application status to `needs_user_input` when profile is missing or invalid
- updates application status to `failed` when host worker fill fails
- records privacy-safe application events with field names and labels only, not profile values

Events recorded:

- `form_fill_requested`
- `field_filled`
- `field_missing`
- `form_fill_completed`
- `form_fill_failed`
- `profile_missing`
- `profile_invalid`

### Profile Management

Backend and Telegram profile management are implemented.

Important files:

- `workspace/main/telegram-apply-engine/src/server.ts`
- `workspace/main/telegram-apply-engine/src/bot/applyEngineClient.ts`
- `workspace/main/telegram-apply-engine/src/bot/handlers.ts`
- `workspace/main/telegram-apply-engine/src/bot/bot.ts`

Implemented backend endpoints:

```http
GET /api/users/:telegramUserId/profile
PUT /api/users/:telegramUserId/profile
```

Behavior:

- `PUT` auto-registers a Telegram user if needed.
- profile data is normalized and stored in `user_profiles.profile_json`.
- string-like values are trimmed before storage.
- numbers and booleans are accepted and stored as strings for the MVP.
- unknown fields are rejected.
- URL fields must be `http` or `https`.
- `GET` returns `{ telegram_user_id, profile }`.

Supported profile fields:

- `first_name`
- `last_name`
- `full_name`
- `email`
- `phone`
- `location`
- `linkedin_url`
- `github_url`
- `portfolio_url`
- `work_authorization`
- `notice_period`
- `salary_expectation`

Telegram behavior:

- `/profile` shows the saved profile.
- `/setprofile` starts a guided setup flow for common profile fields.
- guided setup saves through the Apply Engine profile API.

### Resume Upload Automation

Resume upload automation is implemented for the MVP.

Important files:

- `workspace/main/telegram-apply-engine/src/server.ts`
- `workspace/main/telegram-apply-engine/src/host-worker/formFiller.ts`
- `workspace/main/telegram-apply-engine/src/host-worker/sessionManager.ts`
- `workspace/main/telegram-apply-engine/src/host-worker/server.ts`
- `workspace/main/telegram-apply-engine/src/bot/handlers.ts`

Implemented behavior:

- Telegram document handler accepts PDF uploads and records them in the `resumes` table.
- Backend fill flow looks up the latest readable resume path for the user and passes it to the host worker fill call.
- Backend validates that the resume path exists and is readable before passing it to the host worker.
- Host worker fill endpoint accepts optional `resume_path`.
- Host worker form filler can set a resume path on an `<input type="file">`.
- If a form asks for a file upload but no readable resume is available, the fill result reports missing `resume`.
- If multiple file inputs exist and none clearly looks like resume/CV, the filler skips with `ambiguous_file_input` instead of guessing.
- Fill still does not click submit.

Known limitation:

- Resume selection is currently "latest readable resume" and not an explicit user-selected default.

## Current Test Status

Latest known result:

```text
Test Files  5 passed (5)
Tests       38 passed (38)
```

Test files:

- `workspace/main/telegram-apply-engine/test/db.test.ts`
- `workspace/main/telegram-apply-engine/test/server.test.ts`
- `workspace/main/telegram-apply-engine/test/hostWorker.test.ts`
- `workspace/main/telegram-apply-engine/test/botHandlers.test.ts`
- `workspace/main/telegram-apply-engine/test/browser.test.ts`

Important note:

- Playwright and local HTTP binding may fail inside a restricted Codex sandbox.
- In that case, rerun tests with approved/elevated execution.
- On the user's laptop terminal, the browser/local server permission issue should not normally happen.

Run tests:

```bash
npm --prefix workspace/main/telegram-apply-engine test
```

## Important Files

Backend:

- `workspace/main/telegram-apply-engine/src/server.ts`
- `workspace/main/telegram-apply-engine/src/db/db.ts`
- `workspace/main/telegram-apply-engine/src/apply/hostWorkerClient.ts`
- `workspace/main/telegram-apply-engine/src/apply/events.ts`

Host worker:

- `workspace/main/telegram-apply-engine/src/host-worker/server.ts`
- `workspace/main/telegram-apply-engine/src/host-worker/sessionManager.ts`
- `workspace/main/telegram-apply-engine/src/host-worker/formFiller.ts`

Telegram:

- `workspace/main/telegram-apply-engine/src/bot/bot.ts`
- `workspace/main/telegram-apply-engine/src/bot/handlers.ts`
- `workspace/main/telegram-apply-engine/src/bot/applyEngineClient.ts`

Older browser stream prototype:

- `workspace/main/telegram-apply-engine/src/browser/browserWorker.ts`
- `workspace/main/telegram-apply-engine/src/ws/streamer.ts`
- `workspace/main/telegram-apply-engine/mini-app/`

The Mini App/browser streaming route is not the current MVP path.

## Environment Variables

Local `.env.example` exists:

- `workspace/main/telegram-apply-engine/.env.example`

Important variables:

```text
PORT=4000
HOST_WORKER_PORT=4555
APPLY_ENGINE_URL=http://127.0.0.1:4000
HOST_WORKER_URL=http://127.0.0.1:4555
BROWSER_PROFILE_DIR=./data/browser-profiles
DEFAULT_RESUME_PATH=
TELEGRAM_BOT_TOKEN=
```

For Docker backend calling laptop host worker:

```text
HOST_WORKER_URL=http://host.docker.internal:4555
```

Security note:

- A real Telegram token existed in `.env` earlier.
- Rotate that token before real deployment.
- Do not copy real tokens into docs, tests, logs, or chat.

## How To Run

Install dependencies:

```bash
npm --prefix workspace/main/telegram-apply-engine install
```

Run tests:

```bash
npm --prefix workspace/main/telegram-apply-engine test
```

Start host worker:

```bash
npm --prefix workspace/main/telegram-apply-engine run host-worker
```

Start backend and Telegram bot:

```bash
APPLY_ENGINE_URL=http://127.0.0.1:4000 \
HOST_WORKER_URL=http://127.0.0.1:4555 \
npm --prefix workspace/main/telegram-apply-engine start
```

Backend-only smoke test:

```bash
curl -X POST http://127.0.0.1:4000/api/apply/start \
  -H 'Content-Type: application/json' \
  -d '{"telegram_user_id":"smoke_user","application_url":"https://example.com"}'
```

Host worker health:

```bash
curl http://127.0.0.1:4555/health
```

Host worker sessions:

```bash
curl http://127.0.0.1:4555/sessions
```

## Current Limitations

- Telegram/backend flow can open Chrome and backend can fill via `POST /api/apply/:id/fill`, but Telegram does not yet expose a fill action button.
- Profile management is still MVP-level: API plus Telegram guided setup, no polished web UI.
- Resume selection is currently latest-readable-resume only, not an explicit default selector.
- Submit approval implementation is not complete in the current code.
- Controlled submit endpoint is not complete in the current code.
- No ATS-specific handlers yet.
- No Workday support yet.
- No robust login detection yet.
- No OTP/CAPTCHA detection beyond manual user control policy.
- Telegram one-time credential flow is not implemented yet.
- Mini App/browser streaming is deferred.

## Next Implementation Plan

### Phase 1: Wire Profile-Based Fill Into Backend Flow

Status: completed.

Goal:

After Chrome opens, backend should be able to call host worker fill using the user's saved profile.

Implementation:

- Extend backend host worker client with:
  ```ts
  fillSession(applicationId: string, profile: ApplicantProfile): Promise<FillResult>
  ```

- Add backend endpoint:
  ```http
  POST /api/apply/:id/fill
  ```

- Load profile from:
  ```sql
  user_profiles.profile_json
  ```

- If profile exists, call:
  ```http
  POST {HOST_WORKER_URL}/sessions/:id/fill
  ```

- If profile is missing, update status:
  ```text
  needs_user_input
  ```

- Record events:
  - `form_fill_requested`
  - `field_filled`
  - `field_missing`
  - `form_fill_completed`
  - `form_fill_failed`

- Update application status:
  - `filling`
  - `needs_user_input`
  - `awaiting_review`
  - `failed`

Tests:

- profile exists and fill succeeds
- profile missing creates `needs_user_input`
- host worker fill failure records event
- events contain field names only, not private values
- existing open-browser flow still works

Acceptance:

- API can open Chrome and fill a local fixture form through backend orchestration.

### Phase 2: Profile Management

Status: completed.

Goal:

Give user a way to create and update profile data used for filling.

Backend APIs:

```http
GET /api/users/:telegramUserId/profile
PUT /api/users/:telegramUserId/profile
```

Profile fields:

- `first_name`
- `last_name`
- `full_name`
- `email`
- `phone`
- `location`
- `linkedin_url`
- `github_url`
- `portfolio_url`
- `work_authorization`
- `notice_period`
- `salary_expectation`

Rules:

- Do not invent sensitive fields.
- Store profile JSON in `user_profiles.profile_json`.
- Validate profile shape lightly.
- Keep this simple first: JSON input is acceptable for MVP.

Telegram:

- `/profile` shows current profile summary.
- `/setprofile` can initially instruct user to provide JSON or use a simple guided flow later.

Tests:

- create profile
- update profile
- get profile
- reject invalid profile payload
- profile survives application start

### Phase 3: Resume Upload Automation

Status: completed.

Goal:

Support resume upload into application forms.

Backend:

- Use existing `resumes` table.
- Add default resume lookup per user.
- Validate path exists and is readable.

Host worker:

- Extend fill endpoint to accept:
  ```json
  {
    "profile": {},
    "resume_path": "/absolute/path/to/resume.pdf"
  }
  ```

- Detect:
  ```html
  <input type="file">
  ```

- Upload resume with Playwright `setInputFiles`.

Rules:

- Never upload if resume path missing.
- Never log full resume contents.
- Treat resume path as local-sensitive.

Tests:

- fixture file input upload
- missing resume path creates missing field result
- unsupported upload field is skipped safely
- no submit click

### Phase 4: Review And Approval

Status: next.

Goal:

User must approve final submit.

Backend endpoints:

```http
POST /api/apply/:id/request-submit-approval
POST /api/apply/:id/approve-submit
POST /api/apply/:id/cancel
```

Database:

- Use `approval_requests`.
- Status values:
  - `pending`
  - `approved`
  - `rejected`
  - `expired`

Telegram:

Send summary:

- application ID
- URL
- status
- filled fields
- missing fields
- resume used

Buttons:

- `Approve Submit`
- `Cancel`
- `Check Status`
- `Open Browser Again`

Host worker:

- Add submit detection.
- Add controlled endpoint:
  ```http
  POST /sessions/:id/submit
  ```

Rules:

- Fill endpoint must never submit.
- Submit endpoint only called after backend approval exists.
- If user cancels, submit is blocked.

Tests:

- submit rejected without approval
- submit rejected after cancel
- submit accepted after approval
- host worker submit called once
- application status becomes `submitted` or `failed`

### Phase 5: ATS-Specific Handlers

Goal:

Improve reliability for common job application platforms.

Order:

1. Lever
2. Greenhouse
3. Ashby
4. Workday later

Implementation:

- Detect platform by URL and DOM.
- Add platform-specific field/step handling.
- Support multi-page forms.
- Pause on unknown or sensitive fields.
- Reuse generic form filler as fallback.

Tests:

- Lever fixture
- Greenhouse fixture
- Ashby fixture
- multi-step fixture
- missing required field fixture
- no submit without approval

### Phase 6: Login And Credentials

Goal:

Handle login safely.

Default:

- manual login in visible Chrome

Flow:

```text
Site asks for login
-> automation pauses
-> Telegram says login needed
-> user logs in directly in Chrome
-> user clicks Resume
-> automation continues
```

Optional later:

- one-time Telegram credentials

Rules for one-time Telegram credentials:

- only after explicit user action
- never store credentials
- never write credentials to events/logs
- clear from memory after one attempt
- log only `one_time_login_attempted`

Tests:

- credential values never enter DB/events
- manual login state works
- failed login returns user control
- CAPTCHA/OTP always pauses

### Phase 7: Production Hardening

Goal:

Make the system reliable enough for repeated real use.

Add:

- session timeout
- stuck session detection
- better retry states
- event timeline API
- startup config validation
- port conflict guidance
- local-only host worker binding
- browser profile cleanup command
- token rotation checklist

Tests:

- worker unavailable
- browser crash
- backend restart
- duplicate application
- port conflict
- invalid host worker URL

## Suggested Next Immediate Task

Implement Phase 4: Review And Approval.

Why this is next:

- Phase 1, Phase 2, and Phase 3 are complete.
- The apply flow can now open Chrome, load profile data, fill common fields, and upload a resume.
- The next safety layer is explicit user approval before any final submit.

After Phase 4, the real workflow should become:

```text
Telegram link
-> Chrome opens
-> backend loads profile
-> host worker fills common fields
-> host worker uploads latest readable resume when present
-> user reviews manually
-> user approves final submit
```

## Acceptance Criteria For Usable MVP

The MVP is usable when:

- user sends job link in Telegram
- laptop Chrome opens visibly
- backend loads user profile
- host worker fills common fields
- resume upload works
- login/CAPTCHA/OTP pauses for manual user action
- final submit requires Telegram approval
- application status and events are saved
- no password or OTP is stored
- full test suite passes
