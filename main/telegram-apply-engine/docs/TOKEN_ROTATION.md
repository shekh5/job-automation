# Token Rotation Runbook

This document details the procedure for safely rotating credentials (such as the Telegram Bot Token, Database Encryption Keys, or Host Worker credentials) without causing unplanned downtime or silent failures.

## 1. Telegram Bot Token Rotation

If the `TELEGRAM_BOT_TOKEN` is compromised or needs regular rotation, follow these steps:

### Zero-Downtime Rotation Process
Currently, the Telegram Apply Engine relies on a single Telegram Bot token to connect to the Telegram API via long polling. To rotate the token with minimal downtime:

1. **Obtain the New Token**: 
   - Open Telegram and talk to [@BotFather](https://t.me/BotFather).
   - Use the `/token` command and select your bot to generate a new token.
   - *Note*: Generating a new token will immediately invalidate the old token. Any running instances using the old token will begin throwing 401 Unauthorized errors and crash.

2. **Update the Environment Variable**:
   - On your server, open your `.env` file (e.g. `nano .env`).
   - Replace the `TELEGRAM_BOT_TOKEN` value with the new token.
   - *Important*: Do not leave the old token in the file or commit it to source control.

3. **Restart the Engine**:
   - The engine validates the token on startup. If it is missing or invalid, it will fail fast.
   - Restart the engine using your process manager (e.g., `pm2 restart telegram-apply-engine` or `systemctl restart telegram-bot`).
   - The bot process will automatically reconnect using the new token and resume processing user messages.

### What about active Host Worker sessions?
The Host Worker (Chromium engine) and the backend API operate independently of the Telegram Bot's connection. 
- If the bot process crashes due to a revoked token, **active browser application sessions will NOT be interrupted**. 
- The backend will continue to orchestrate the automation, and any required user input will queue in the database (`approval_requests`).
- Once the bot restarts with the new token, it will resume polling, and any pending interactive prompts will be sent to the user.

## 2. Host Worker Security

The Host Worker provides an internal URL (`HOST_WORKER_URL`) that the backend uses to request browser automation.

- **Port Binding**: The Host Worker is strictly bound to `127.0.0.1`. It will reject connections originating from the public internet.
- **Port Conflicts**: If the `HOST_WORKER_PORT` (default 4001) is already in use, the worker will refuse to start and print an actionable `EADDRINUSE` error.
- **Secret Rotation**: If you add authentication (e.g., bearer tokens) to the Host Worker in the future, rotate them by stopping the backend API, updating both `.env` files (if separated), and starting the Host Worker first, followed by the Backend API.

## 3. Database Management

The SQLite database (`apply-engine.sqlite`) is the source of truth.
- **Backups**: Run `sqlite3 apply-engine.sqlite ".backup apply-engine.backup"` before performing major credential rotations or structural migrations.
- **Automated Cleanup**: The engine runs an automated daily cleanup task to prune unused/stale `jobs` older than 30 days. No manual maintenance is required to prevent basic bloat.
