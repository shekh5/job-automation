# Security Policy

## Principles

- Prefer user-controlled login in visible Chrome.
- Keep the user in control of sensitive answers and final submission.
- Store the minimum data required to run the workflow.
- Treat Telegram messages, logs, screenshots, browser sessions, and SQLite data as sensitive.

## Credentials

Manual browser login is the preferred login method.

Telegram one-time credentials are allowed only when the user explicitly chooses that flow for the active application. The implementation must:

- Use credentials only for one login attempt.
- Keep credentials in memory only.
- Clear credentials immediately after use or failure.
- Never persist passwords.
- Never include raw credentials in application events.
- Never print raw credentials to console logs.
- Never send raw credentials back to Telegram.

If there is any uncertainty about credential safety, pause and ask the user to log in manually in Chrome.

## Telegram Token

The Telegram bot token is a secret.

Requirements:

- Real tokens must live only in local `.env` or a secret manager.
- `.env.example` must contain placeholders only.
- Existing exposed tokens should be rotated before real use.
- Documentation must not copy token values.

## Screenshots And Browser State

- Avoid screenshots on login, password, OTP, payment, or sensitive profile pages when possible.
- If screenshots are needed for debugging, store them outside version control and treat them as sensitive.
- Browser profile directories contain login cookies and must not be committed.

## Application Submission

Final submit must always require explicit user approval.

The system must not:

- Submit automatically after filling.
- Submit when approval is expired.
- Submit after user cancellation.
- Submit if the active browser URL does not match the expected application session.

## Logging

Logs may include:

- Application ID.
- Status.
- Platform.
- Non-sensitive error category.
- Field names filled.

Logs must not include:

- Passwords.
- OTPs.
- Session cookies.
- Authorization headers.
- Full resume contents.
- Sensitive answers unless the user explicitly saved them as profile defaults.

## Data Handling

- Keep SQLite databases local unless the user explicitly chooses sync.
- Keep resumes and browser profiles outside tracked source files.
- Do not edit runtime databases manually unless there is a backup and a specific recovery task.
