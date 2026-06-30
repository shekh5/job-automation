# Data Model

## Existing Tables

The current SQLite schema already provides the required base:

- `users`
- `user_profiles`
- `resumes`
- `jobs`
- `applications`
- `application_events`
- `approval_requests`

The MVP should extend this schema only when a behavior cannot be represented with the existing fields.

## Users

`users` maps Telegram identity to an internal user ID.

Required behavior:

- Create user on `/start` or first direct apply URL.
- Keep `telegram_user_id` unique.

## User Profiles

`user_profiles.profile_json` stores structured profile data used for filling.

Minimum profile fields:

- `first_name`
- `last_name`
- `full_name`
- `email`
- `phone`
- `location`
- `linkedin_url`
- `github_url`
- `portfolio_url`
- `education_summary`
- `experience_summary`
- `work_authorization`
- `notice_period`
- `salary_expectation`

Sensitive defaults such as work authorization and salary are optional. If missing, the system asks the user instead of guessing.

## Resumes

`resumes` stores local resume metadata and path.

Rules:

- MVP can use one default resume per user.
- Host worker must be able to read the resume path.
- Resume files should not be copied into logs or event payloads.

## Jobs

`jobs` stores application target metadata.

For direct URL MVP, `company`, `title`, and `location` may be unknown initially and enriched later from page extraction.

## Applications

`applications` tracks the active workflow.

Important fields:

- `status`
- `resume_id`
- `platform`
- `current_step`
- `final_url`
- `confirmation_text`
- `submitted_at`

Status values:

- `created`
- `opening`
- `login_required`
- `filling`
- `needs_user_input`
- `awaiting_submit_approval`
- `submitted`
- `failed`
- `cancelled`

## Application Events

`application_events` stores an append-only timeline.

Recommended event types:

- `application_started`
- `browser_opened`
- `navigation_failed`
- `platform_detected`
- `login_required`
- `one_time_login_attempted`
- `field_filled`
- `missing_field`
- `resume_uploaded`
- `approval_requested`
- `approval_granted`
- `approval_cancelled`
- `submitted`
- `failed`

Event payloads must not contain raw credentials.

## Approval Requests

`approval_requests` stores user decisions needed to continue.

Approval types:

- `submit`
- `manual_input`
- `sensitive_answer`
- `one_time_login`
- `resume_choice`

Statuses:

- `pending`
- `approved`
- `rejected`
- `expired`

## Credential Storage Rule

Raw usernames and passwords for external sites are not durable application data. They must not be stored in SQLite, files, logs, screenshots metadata, or event payloads.
