# Functional Specification

## Primary Flow

1. User sends a job apply URL in Telegram.
2. Bot validates that the message contains an HTTP or HTTPS URL.
3. Apply engine creates or reuses the Telegram user record.
4. Apply engine creates a job record for the URL if needed.
5. Apply engine creates an application record with status `created`.
6. Apply engine calls the laptop host worker to open visible Chrome.
7. Host worker opens the apply page and reports status.
8. Apply engine asks the worker to fill safe known fields.
9. Worker pauses when login, manual input, or uncertain answers are required.
10. When the form is ready, apply engine creates a submit approval request.
11. User approves or cancels in Telegram.
12. Worker clicks final submit only after approval.
13. Apply engine records the final outcome.

## Telegram Commands And Actions

- `/start`: register or refresh the user record and explain the basic workflow.
- Direct URL message: start an application for that URL.
- `Approve Submit`: approve the current application submission.
- `Cancel`: cancel the current application.
- `Pause`: stop automation and leave Chrome under user control.
- `Resume`: continue automation after manual user action.
- `Send One-Time Login`: begin a temporary credential prompt for one login attempt.

## Application Statuses

- `created`: application record exists but browser has not opened yet.
- `opening`: host worker is opening Chrome and navigating.
- `login_required`: the site requires login, OTP, CAPTCHA, or user action.
- `filling`: worker is filling known form fields.
- `needs_user_input`: a field or step needs user decision.
- `awaiting_submit_approval`: form appears ready and submit approval is pending.
- `submitted`: final submit was approved and completed.
- `failed`: the workflow cannot continue automatically.
- `cancelled`: user cancelled the application.

## Human-In-The-Loop Rules

The system must pause for:

- Login pages.
- Password entry unless the user explicitly chooses one-time Telegram credentials.
- OTP prompts.
- CAPTCHA.
- Legal, criminal history, or diversity questions.
- Work authorization questions without a saved default.
- Salary or notice period questions without a saved default.
- Any field with low confidence.
- Final submit.

## Form Filling Rules

- Fill only fields that can be matched to known profile or resume data.
- Prefer labels, `aria-label`, placeholders, input names, and input IDs for matching.
- Do not invent sensitive answers.
- Do not click submit during normal filling.
- Required fields that cannot be filled become user-input requests.
- Dropdowns and radio buttons are filled only when the match is high confidence.

## Credential Flow

Manual browser login is preferred. Telegram one-time credentials are allowed only when the user explicitly chooses that action.

For one-time Telegram credentials:

- Collect credentials only for the active application session.
- Use credentials immediately for one login attempt.
- Clear credentials from memory after the attempt.
- Do not store or log raw credential values.
- Record only non-sensitive state such as `one_time_login_attempted`.

## Approval Flow

Before final submit, Telegram shows:

- Company and role when known.
- Application URL.
- Resume selected.
- Filled field summary.
- Any fields that still need review.

The user may approve or cancel. Approval is required before the worker clicks the final submit button.
