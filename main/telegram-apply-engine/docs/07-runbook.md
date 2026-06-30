# Runbook

## Current Project

The apply engine lives at:

```text
workspace/main/telegram-apply-engine
```

Install dependencies:

```bash
npm --prefix workspace/main/telegram-apply-engine install
```

Run tests:

```bash
npm --prefix workspace/main/telegram-apply-engine test
```

Start current backend and bot:

```bash
npm --prefix workspace/main/telegram-apply-engine start
```

## Future Host Worker

The laptop host worker should run outside Docker and expose a local HTTP API.

Planned command:

```bash
npm --prefix workspace/main/telegram-apply-engine run host-worker
```

Default URL:

```text
http://localhost:4555
```

Docker/OpenClaw should call it through a configurable value such as:

```text
HOST_WORKER_URL=http://host.docker.internal:4555
```

## Environment Variables

Required or planned variables:

```text
TELEGRAM_BOT_TOKEN=
APPLY_ENGINE_URL=http://127.0.0.1:4000
HOST_WORKER_URL=http://127.0.0.1:4555
DB_PATH=
BROWSER_PROFILE_DIR=
DEFAULT_RESUME_PATH=
PORT=4000
HOST_WORKER_PORT=4555
```

Rules:

- Keep real secrets in `.env`.
- Keep `.env.example` placeholder-only.
- Rotate any token that has been exposed in local files or chat.

For Docker backend to laptop host worker, set:

```text
HOST_WORKER_URL=http://host.docker.internal:4555
```

For local laptop-only smoke tests, set:

```text
HOST_WORKER_URL=http://127.0.0.1:4555
```

## Normal Operation

1. Start OpenClaw/Docker.
2. Start apply engine backend and Telegram bot.
3. Start laptop host worker.
4. User sends apply URL in Telegram.
5. Laptop Chrome opens visibly.
6. User handles login or manual prompts.
7. Automation fills safe fields.
8. User approves final submit in Telegram.
9. Application status is saved.

## Local End-To-End Smoke Test

Start the host worker in one terminal:

```bash
npm --prefix workspace/main/telegram-apply-engine run host-worker
```

Start the backend in another terminal:

```bash
APPLY_ENGINE_URL=http://127.0.0.1:4000 \
HOST_WORKER_URL=http://127.0.0.1:4555 \
npx --prefix workspace/main/telegram-apply-engine tsx workspace/main/telegram-apply-engine/src/server.ts
```

Trigger a direct URL application:

```bash
curl -X POST http://127.0.0.1:4000/api/apply/start \
  -H 'Content-Type: application/json' \
  -d '{"telegram_user_id":"smoke_user","application_url":"https://example.com"}'
```

Expected result:

- API returns an `application_id`.
- API status is `opening`.
- `host_worker_requested` is `true`.
- Visible Chrome opens `https://example.com`.

## Troubleshooting

### Host Worker Unreachable

- Check the worker process is running.
- Check `HOST_WORKER_URL`.
- From Docker, verify whether `host.docker.internal` resolves.
- Try direct laptop URL `http://localhost:4555/health` from the host.

### Chrome Does Not Open

- Confirm Google Chrome is installed.
- Confirm Playwright can find the Chrome channel.
- Check `BROWSER_PROFILE_DIR` permissions.
- Try a fresh profile directory.

### Telegram Bot Does Not Respond

- Confirm `TELEGRAM_BOT_TOKEN` is set.
- Confirm the token has been rotated if previously exposed.
- Confirm only one bot polling process is running.
- Check backend logs for polling or callback errors.

### Application Stuck On Login

- Use visible Chrome to complete login manually.
- Solve OTP or CAPTCHA manually.
- Press resume in Telegram after login.
- Use one-time Telegram credentials only if the user explicitly chooses that flow.

### Application Stuck Awaiting Approval

- Check Telegram approval message was delivered.
- Verify the application status is `awaiting_submit_approval`.
- Re-send approval prompt if needed.
- Do not submit manually through the worker API unless user approval exists.

### Sensitive Data Exposure

- Stop the bot and worker.
- Rotate exposed Telegram token or site password.
- Delete affected logs/screenshots if they contain secrets.
- Confirm SQLite events do not contain raw credentials.
