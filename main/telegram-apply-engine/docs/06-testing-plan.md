# Testing Plan

## Phase Gates

Each phase should have a small acceptance test set before moving forward.

## Phase 1: Documentation

Validate:

- All seven docs exist.
- Docs use the same architecture and phase assumptions.
- Security policy covers one-time Telegram credentials.
- No secret values are copied into docs.

Command:

```bash
find workspace/main/telegram-apply-engine/docs -maxdepth 1 -type f | sort
```

## Phase 2: Host Chrome Worker

Automated tests:

- `GET /health` returns ready state.
- `POST /sessions` creates a session.
- A local HTML form opens in visible or test headless mode.
- Fill endpoint fills name, email, phone, and links on a fixture form.
- Submit is not clicked by fill endpoint.

Manual tests:

- Chrome opens visibly on the laptop.
- The configured persistent profile is reused.
- User can take over the browser manually.

## Phase 3: Apply Engine Orchestration

Automated tests:

- Direct apply URL creates user, job, and application records.
- Duplicate applications are handled cleanly.
- Mock host worker receives expected session request.
- Application status transitions are persisted.
- Application events do not contain credentials.

## Phase 4: Telegram Bot Flow

Automated tests with mocked Telegram client:

- `/start` registers user.
- Direct URL starts application.
- Invalid URL returns a helpful error.
- Approve callback calls submit approval endpoint.
- Cancel callback updates application status.
- One-time credential flow does not write raw credentials to DB/events.

## Phase 5: Form Filling

Fixture tests:

- Lever-style form.
- Greenhouse-style form.
- Ashby-style form.
- Generic label/placeholder form.
- Resume upload input.
- Required missing fields.
- Dropdown with clear profile match.
- Dropdown with unclear match creates user-input request.

Safety tests:

- Fill operation never clicks final submit.
- Sensitive/legal fields are skipped unless user saved defaults.
- Unknown fields are reported, not guessed.

## Phase 6: Approval And Submit

Automated tests:

- Submit endpoint rejects when approval is missing.
- Submit endpoint rejects expired or cancelled approval.
- Approved submit calls host worker once.
- Submitted status and event are recorded.

Manual tests:

- User reviews Chrome before approving.
- Telegram approval submits the application.
- Telegram cancel leaves browser open or closes it according to current session policy.

## Phase 7: Reliability

Tests:

- Host worker unavailable returns `failed` with clear reason.
- Browser navigation timeout creates retryable failure.
- Worker crash does not corrupt application record.
- Restarted backend can read existing application state.

## Standard Commands

Backend tests:

```bash
npm --prefix workspace/main/telegram-apply-engine test
```

Mini app build, when the Mini App is touched:

```bash
npm --prefix workspace/main/telegram-apply-engine/mini-app run build
```
