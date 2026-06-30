# Job Apply Automation Requirements

## Goal

Build a Telegram-driven job application assistant where a user sends a job apply link, the system opens the page in the user's laptop Chrome browser, fills safe known fields from the user's profile, uploads the resume, and waits for explicit approval before final submission.

## Users

- Primary user: job seeker using Telegram and a laptop.
- Operator/developer: person running OpenClaw in Docker and the laptop host worker.

## Core User Stories

- As a user, I can send a job apply URL in Telegram and have the system start an application session.
- As a user, I can see status updates while Chrome opens, forms are filled, or manual input is needed.
- As a user, I can log in manually in the visible Chrome browser when a site asks for login, OTP, or CAPTCHA.
- As a user, I can optionally provide one-time login credentials through Telegram for a single login attempt.
- As a user, I can review the filled application before anything is submitted.
- As a user, I can approve, cancel, pause, or resume an application.
- As a user, I can keep a default profile and resume for form filling.
- As an operator, I can inspect application status and failure reasons without exposing secrets.

## MVP Scope

- Telegram bot receives direct job apply URLs.
- Apply engine runs inside OpenClaw/Docker and manages users, jobs, applications, approvals, and events.
- Laptop host worker controls visible Chrome through Playwright.
- Docker calls host worker through a configurable local HTTP URL.
- Chrome uses a persistent user profile so login sessions can be reused.
- Form filling supports common profile fields and resume upload.
- Initial ATS targets are Lever, Greenhouse, and Ashby.
- Final submit always requires explicit user approval.
- Application status is stored in SQLite.

## Out Of Scope For MVP

- CAPTCHA bypass, OTP bypass, or anti-bot evasion systems.
- Fully automatic login without user involvement.
- Fully automatic final submit.
- Native mobile browser automation.
- Full Telegram Mini App browser streaming.
- Workday support in the first implementation phase.
- Storing raw passwords or long-lived third-party credentials.

## Success Criteria

- A user can send a supported apply link in Telegram.
- Visible laptop Chrome opens the apply page.
- The system fills known fields from profile data.
- The system uploads the configured resume where the form supports file upload.
- The system pauses for login, OTP, CAPTCHA, sensitive questions, and uncertain fields.
- The user can approve or cancel from Telegram.
- No final submit occurs without approval.
- No password is written to SQLite, files, event payloads, or logs.
