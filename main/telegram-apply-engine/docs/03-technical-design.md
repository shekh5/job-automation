# Technical Design

## Architecture

```text
Telegram Bot
  -> Apply Engine API inside OpenClaw/Docker
  -> Host HTTP Chrome Worker on laptop
  -> Visible Chrome via Playwright persistent profile
  -> SQLite tracking
```

## Components

### Telegram Bot

- Receives direct apply URLs and callback actions.
- Sends status updates and approval prompts.
- Never persists raw credentials.
- Calls the apply engine API for session actions.

### Apply Engine API

- Existing Node/TypeScript Express service.
- Owns users, profiles, resumes, jobs, applications, approvals, and events.
- Calls the host worker over HTTP.
- Stores durable state in SQLite.
- Does not perform low-level browser automation directly for the laptop Chrome mode.

### Host Chrome Worker

- Runs on the laptop host, outside Docker.
- Exposes a local HTTP API.
- Controls visible Chrome with Playwright.
- Uses a persistent Chrome profile directory.
- Reports status and errors back to the apply engine.

### SQLite Store

- Tracks users, jobs, applications, events, resumes, and approval requests.
- Stores non-sensitive event payloads only.
- Never stores passwords.

## Host Bridge

The apply engine calls the host worker through:

```text
HOST_WORKER_URL=http://host.docker.internal:4555
```

The value must be configurable because host networking differs by platform and Docker setup.

## Host Worker API

Minimum API for the first implementation:

- `GET /health`: returns readiness and Chrome configuration status.
- `POST /sessions`: creates a browser session for an application.
- `POST /sessions/:id/navigate`: navigates to the application URL.
- `POST /sessions/:id/fill`: fills known fields from the provided profile data.
- `POST /sessions/:id/login`: performs one approved one-time login attempt.
- `POST /sessions/:id/pause`: pauses automation.
- `POST /sessions/:id/resume`: resumes automation.
- `POST /sessions/:id/approve-submit`: clicks final submit after approval.
- `GET /sessions/:id/status`: returns current URL, step, and non-sensitive errors.

## Chrome Configuration

Host worker should use:

```ts
chromium.launchPersistentContext(profileDir, {
  channel: "chrome",
  headless: false,
  viewport: { width: 1280, height: 900 }
})
```

The browser profile directory must be configurable through `BROWSER_PROFILE_DIR`.

## ATS Strategy

Implement in this order:

1. Lever.
2. Greenhouse.
3. Ashby.
4. Generic form fallback.
5. Workday later.

Each ATS handler should be small and focused. Shared utilities should cover label matching, field filling, dropdown selection, resume upload, and submit detection.

## Deferred Mini App

The existing Mini App can remain a later control surface. The MVP should not depend on browser streaming through the Mini App. Telegram callbacks plus visible laptop Chrome are the first target.
