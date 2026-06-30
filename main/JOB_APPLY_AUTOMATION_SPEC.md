# Job Apply Automation Spec For Telegram + OpenClaw

## Purpose Of This File

This file is a detailed implementation handoff for building the **job apply automation** part of a Telegram-based job helper.

The job finding part is already assumed to be strong and mostly complete.

This spec focuses only on:

- Applying to jobs.
- Opening job application pages.
- Filling forms.
- Handling login safely.
- Using human approval.
- Connecting Telegram, OpenClaw, browser automation, and user profile data.

---

## Previous Context Summary

The product idea:

> A Telegram bot helps users find jobs and apply to them.

Important clarification:

- Job discovery/finding is already handled well.
- The next goal is to automate the **job applying workflow**.
- The user wants the agent to apply on behalf of users.
- Some websites need username, password, OTP, CAPTCHA, or manual confirmation.
- Therefore the workflow must have **human in the loop**.
- The user should preferably not leave Telegram.
- Telegram cannot embed a full browser directly inside a normal chat message.
- The correct solution is to use a **Telegram Mini App / Telegram Web App** opened from the Telegram bot.
- That Mini App can show a browser-like interface, approval screens, and user controls.

The key architecture decided:

```text
Telegram Bot
  -> OpenClaw Agent
      -> Apply Automation Tool
          -> Playwright Browser Worker
          -> Form Understanding Engine
          -> User Profile Mapper
          -> Resume Upload Handler
          -> Application Tracker
      -> Telegram Mini App for browser/login/approval
```

OpenClaw should be the **brain/orchestrator**, not necessarily the low-level browser engine.

---

## Simple Explanation

OpenClaw will manage the workflow.

But OpenClaw should not do every low-level thing directly.

Think of it like this:

```text
OpenClaw = brain / manager
Playwright = hands that control browser
Telegram Bot = chat interface
Telegram Mini App = user control screen
Profile DB = user memory/profile
Apply Engine = code that fills job forms
```

OpenClaw decides:

- Which job to apply to.
- Which tool to call.
- When to ask the user.
- Whether a form answer is safe.
- When to pause.
- When to request final approval.

The Apply Engine does:

- Opens the browser.
- Reads form fields.
- Fills known fields.
- Uploads resume.
- Clicks next buttons.
- Stops before final submit.

The user does:

- Login.
- OTP.
- CAPTCHA.
- Sensitive answers.
- Final approval.

---

## What Should Be Automated

These parts can be automated well:

- Open application page.
- Detect known ATS platform.
- Fill first name, last name, email, phone.
- Upload resume.
- Fill LinkedIn, GitHub, portfolio.
- Fill education and experience.
- Fill common dropdowns.
- Draft answers for normal open-ended questions.
- Click next/continue buttons.
- Detect required missing fields.
- Save screenshots.
- Track application status.
- Avoid duplicate applications.

---

## What Should Stay Human-Controlled

These actions should not be fully automatic:

- Website login.
- Password entry.
- OTP.
- CAPTCHA.
- Final submit.
- Sensitive personal questions.
- Salary questions if user has not saved a default.
- Visa/work authorization questions if unclear.
- Diversity/equal opportunity questions.
- Criminal history/legal declarations.
- Any question where the agent is uncertain.

Rule:

> If unsure, ask the user.

---

## Recommended Automation Level

Do not start with full auto-apply.

Recommended version:

```text
Agent fills 70-85 percent of the application.
User handles login, sensitive fields, and final submit approval.
```

This gives strong automation but keeps the product safe.

---

## Main User Flow

### 1. User Selects Job In Telegram

The job finder sends a shortlisted job:

```text
Software Engineer Intern
Company: ExampleTech
Location: Remote India

[Apply] [Skip] [View Job]
```

User taps:

```text
Apply
```

---

### 2. OpenClaw Starts Apply Workflow

OpenClaw receives:

```json
{
  "action": "apply_to_job",
  "telegram_user_id": "12345",
  "job_id": "job_abc",
  "application_url": "https://company.com/jobs/apply/123"
}
```

OpenClaw:

- Loads user profile.
- Loads resume.
- Checks if user already applied.
- Creates application record.
- Starts browser apply session.

---

### 3. Telegram Mini App Opens

Bot sends button:

```text
[Open Apply Assistant]
```

Button opens Telegram Mini App.

Mini App shows:

```text
Applying to:
Software Engineer Intern - ExampleTech

Status:
Opening application page...

[Browser View]

[Pause] [Take Control] [Skip Job]
```

---

### 4. Browser Worker Opens Job Page

Backend starts Playwright:

```text
Browser context per user
Application page opened
Agent begins form detection
```

Browser worker reports events:

```json
{
  "type": "page_opened",
  "url": "https://company.com/jobs/apply/123",
  "title": "ExampleTech Careers"
}
```

---

### 5. Platform Detection

Apply Engine detects platform:

```text
Greenhouse
Lever
Ashby
Workday
LinkedIn
Naukri
Indeed
Generic custom form
```

Recommended implementation order:

1. Greenhouse
2. Lever
3. Ashby
4. Generic forms
5. Workday
6. LinkedIn/Naukri/Indeed later

---

### 6. Form Filling

Apply Engine maps fields:

```text
"First Name" -> user.first_name
"Last Name" -> user.last_name
"Email" -> user.email
"Phone" -> user.phone
"Resume" -> user.resume_file
"LinkedIn" -> user.linkedin_url
"GitHub" -> user.github_url
```

If confidence is high, fill automatically.

If confidence is low, ask user:

```text
I found a field:
"Current compensation"

Should I fill this?

[Enter Answer] [Skip] [Stop]
```

---

### 7. Login Handling

If website asks for login:

OpenClaw sends status:

```text
Login needed.
Please login inside the browser window.
I will wait.
```

Rules:

- Do not ask for password in Telegram chat.
- Do not store raw password.
- User types password directly into the browser.
- Agent pauses until login is complete.
- User handles OTP/CAPTCHA.

After login:

```text
Login detected. Continuing application.
```

---

### 8. Unknown Questions

If application asks:

```text
Why are you interested in this role?
```

OpenClaw can draft:

```text
Suggested answer:
I am interested in this role because it matches my software engineering skills,
and I am excited to contribute to backend systems and learn from the engineering team.

[Use This] [Edit] [Skip]
```

Sensitive questions should not be guessed.

---

### 9. Final Review

Before final submit:

```text
Ready to submit application.

Company: ExampleTech
Role: Software Engineer Intern
Resume: Resume_Backend.pdf

Fields filled:
- Name
- Email
- Phone
- Resume
- LinkedIn
- GitHub
- Education

Answers:
- Why this role: ...
- Notice period: Immediate

[Submit Application] [Edit] [Cancel]
```

OpenClaw must not submit until user approves.

---

### 10. Submission And Tracking

After user approves:

Apply Engine clicks submit.

Then it captures:

- Final page screenshot.
- Confirmation text.
- Application ID if available.
- Submitted timestamp.
- Final URL.

Tracker status:

```text
submitted
```

Telegram update:

```text
Application submitted.

Company: ExampleTech
Role: Software Engineer Intern
Status: Submitted
```

---

## OpenClaw Role

OpenClaw should manage:

- Conversation with Telegram user.
- Workflow state.
- Deciding next action.
- Calling tools.
- Human-in-loop approvals.
- Safety decisions.
- Answer drafting.
- Error handling.
- Application tracking updates.

OpenClaw should not directly own:

- Raw password collection.
- Browser rendering.
- CAPTCHA solving.
- Long-term secret storage.
- Blind final submission.

---

## Required Components

### 1. Telegram Bot

Responsibilities:

- Receive user commands.
- Show apply buttons.
- Send status updates.
- Open Mini App.
- Send approval prompts.
- Notify when user action is needed.

Main Telegram actions:

```text
/start
/profile
/resume
/applications
/stop
```

Buttons:

```text
[Apply]
[Open Apply Assistant]
[Approve Submit]
[Skip]
[Edit Answer]
[Take Control]
```

---

### 2. Telegram Mini App

Responsibilities:

- Show browser session.
- Show current job.
- Show current status.
- Let user control browser.
- Let user approve final submit.
- Let user pause/resume agent.
- Let user edit answers.

Important:

The Mini App must be served on HTTPS.

Telegram Mini App receives init data from Telegram. Backend must verify this init data before trusting user identity.

---

### 3. Backend API

Responsibilities:

- Verify Telegram users.
- Create apply sessions.
- Start browser workers.
- Store profile/resume/application data.
- Manage WebSocket connections.
- Send events between OpenClaw, Mini App, and browser worker.

Suggested API endpoints:

```text
POST /api/apply/start
GET  /api/apply/:application_id/status
POST /api/apply/:application_id/pause
POST /api/apply/:application_id/resume
POST /api/apply/:application_id/approve-submit
POST /api/apply/:application_id/cancel
POST /api/apply/:application_id/answer
GET  /api/applications
GET  /api/profile
POST /api/profile
POST /api/resume
```

WebSocket:

```text
WS /ws/apply/:application_id
```

WebSocket event examples:

```json
{
  "type": "status",
  "message": "Filling resume field"
}
```

```json
{
  "type": "needs_user",
  "reason": "login_required"
}
```

```json
{
  "type": "approval_required",
  "approval_type": "final_submit"
}
```

---

### 4. Browser Worker

Recommended:

```text
Playwright + Chromium
```

Responsibilities:

- Start browser context.
- Navigate to application URL.
- Detect platform.
- Fill forms.
- Upload resume.
- Pause for user.
- Capture screenshots.
- Submit after approval.

Browser context isolation:

```text
one user -> one browser context
one application -> one controlled page
```

Never mix user sessions.

---

### 5. Browser Streaming Layer

The user needs to see and control the browser inside Telegram Mini App.

Options:

#### Simple MVP Streaming

- Browser worker takes screenshots regularly.
- Mini App displays latest screenshot.
- User clicks screenshot.
- Backend maps click coordinates to browser click.
- User keystrokes are sent to browser.

Pros:

- Easier to build.
- Good for MVP.

Cons:

- Less smooth than real browser streaming.

#### Better Streaming

- Chrome DevTools Protocol screencast.
- WebRTC stream.
- noVNC with virtual display.

Pros:

- Smoother.
- More browser-like.

Cons:

- More complex.

Recommended:

```text
Start with screenshot + click mapping.
Upgrade later if needed.
```

---

### 6. Form Understanding Engine

Purpose:

Understand what each form field means.

It should combine:

- Code-based field detection.
- Known platform adapters.
- AI/OpenClaw fallback for unclear fields.

Detection inputs:

- input name
- input id
- placeholder
- label text
- aria-label
- nearby text
- field type
- required marker
- dropdown options

Example:

```json
{
  "selector": "#first_name",
  "type": "text",
  "label": "First Name",
  "required": true,
  "mapped_to": "profile.first_name",
  "confidence": 0.99
}
```

Confidence rule:

```text
confidence >= 0.85 -> fill automatically
confidence 0.50-0.84 -> ask OpenClaw/AI or user
confidence < 0.50 -> ask user
```

---

### 7. User Profile Mapper

Purpose:

Map form fields to stored user profile values.

Example user profile:

```json
{
  "first_name": "Bhawani",
  "last_name": "Singh",
  "email": "user@example.com",
  "phone": "+91...",
  "city": "Jaipur",
  "country": "India",
  "linkedin_url": "https://linkedin.com/in/...",
  "github_url": "https://github.com/...",
  "portfolio_url": "https://...",
  "experience_level": "fresher",
  "notice_period": "Immediate",
  "work_authorization": "India",
  "skills": ["Python", "JavaScript", "React", "Node.js"],
  "education": [
    {
      "degree": "B.Tech",
      "school": "Example University",
      "graduation_year": "2026"
    }
  ]
}
```

Mapper examples:

```text
First Name -> first_name
Surname -> last_name
Email Address -> email
Mobile Number -> phone
Current Location -> city
LinkedIn Profile -> linkedin_url
GitHub -> github_url
```

Sensitive values should need user confirmation unless saved as defaults.

---

### 8. Resume Upload Handler

Responsibilities:

- Store resume files securely.
- Let user choose resume version.
- Upload resume to forms.
- Track which resume was used.

Resume metadata:

```json
{
  "resume_id": "res_123",
  "label": "Backend Resume",
  "filename": "resume_backend.pdf",
  "created_at": "2026-06-23T00:00:00Z"
}
```

---

### 9. Application Tracker

Responsibilities:

- Save every application attempt.
- Prevent duplicates.
- Track status.
- Store evidence.
- Show user history.

Statuses:

```text
created
browser_started
login_required
filling_form
waiting_for_user
ready_for_review
submitted
failed
skipped
cancelled
```

---

## Database Schema Draft

### users

```sql
CREATE TABLE users (
  id TEXT PRIMARY KEY,
  telegram_user_id TEXT UNIQUE NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### user_profiles

```sql
CREATE TABLE user_profiles (
  user_id TEXT PRIMARY KEY REFERENCES users(id),
  profile_json JSONB NOT NULL,
  updated_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### resumes

```sql
CREATE TABLE resumes (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  label TEXT NOT NULL,
  file_path TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### jobs

```sql
CREATE TABLE jobs (
  id TEXT PRIMARY KEY,
  company TEXT NOT NULL,
  title TEXT NOT NULL,
  location TEXT,
  application_url TEXT NOT NULL,
  source TEXT,
  raw_json JSONB,
  discovered_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### applications

```sql
CREATE TABLE applications (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  job_id TEXT NOT NULL REFERENCES jobs(id),
  status TEXT NOT NULL,
  resume_id TEXT REFERENCES resumes(id),
  platform TEXT,
  current_step TEXT,
  final_url TEXT,
  confirmation_text TEXT,
  submitted_at TIMESTAMP,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  updated_at TIMESTAMP NOT NULL DEFAULT now(),
  UNIQUE(user_id, job_id)
);
```

### application_events

```sql
CREATE TABLE application_events (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL REFERENCES applications(id),
  event_type TEXT NOT NULL,
  event_json JSONB NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT now()
);
```

### approval_requests

```sql
CREATE TABLE approval_requests (
  id TEXT PRIMARY KEY,
  application_id TEXT NOT NULL REFERENCES applications(id),
  user_id TEXT NOT NULL REFERENCES users(id),
  approval_type TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt TEXT NOT NULL,
  payload_json JSONB,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  resolved_at TIMESTAMP
);
```

### browser_sessions

```sql
CREATE TABLE browser_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL REFERENCES users(id),
  application_id TEXT REFERENCES applications(id),
  status TEXT NOT NULL,
  encrypted_storage_path TEXT,
  created_at TIMESTAMP NOT NULL DEFAULT now(),
  expires_at TIMESTAMP
);
```

---

## Apply Engine Folder Structure

Suggested structure:

```text
apply-engine/
  src/
    index.ts
    types.ts
    browser/
      browserWorker.ts
      browserSession.ts
      screenshotStreamer.ts
      userInputBridge.ts
    adapters/
      baseAdapter.ts
      greenhouseAdapter.ts
      leverAdapter.ts
      ashbyAdapter.ts
      workdayAdapter.ts
      genericFormAdapter.ts
    form/
      detectFields.ts
      mapFields.ts
      fillFields.ts
      validateRequiredFields.ts
    profile/
      profileMapper.ts
      sensitiveFieldPolicy.ts
    approval/
      approvalManager.ts
    tracker/
      applicationTracker.ts
    safety/
      automationPolicy.ts
      duplicateCheck.ts
```

---

## Adapter Interface

Each platform adapter should follow the same interface.

```ts
export interface ApplyAdapter {
  name: string;

  canHandle(context: ApplyContext): Promise<boolean>;

  start(context: ApplyContext): Promise<ApplyResult>;

  fillForm(context: ApplyContext): Promise<ApplyResult>;

  getReview(context: ApplyContext): Promise<ApplicationReview>;

  submit(context: ApplyContext): Promise<ApplyResult>;
}
```

Apply result:

```ts
export type ApplyResult =
  | { status: "continue"; message?: string }
  | { status: "needs_user"; reason: NeedsUserReason; payload?: unknown }
  | { status: "approval_required"; approvalType: string; payload: unknown }
  | { status: "submitted"; confirmation?: string }
  | { status: "failed"; error: string }
  | { status: "skipped"; reason: string };
```

Needs user reasons:

```ts
type NeedsUserReason =
  | "login_required"
  | "otp_required"
  | "captcha_required"
  | "unknown_field"
  | "sensitive_question"
  | "manual_review";
```

---

## Form Field Detection Logic

For each input/select/textarea:

Collect:

- tag name
- type
- name
- id
- placeholder
- aria-label
- label text
- nearby text
- required
- options
- visible or hidden

Then classify:

```text
first_name
last_name
full_name
email
phone
resume
cover_letter
linkedin
github
portfolio
location
education
experience
salary
work_authorization
notice_period
unknown
```

Field filling rules:

- Fill high confidence fields.
- Do not fill hidden fields unless adapter requires it.
- Do not overwrite fields already filled by user unless needed.
- Validate required fields before next/submit.
- Pause for sensitive fields.

---

## Sensitive Field Policy

These fields should require user confirmation:

```text
current_salary
expected_salary
work_authorization
visa_sponsorship
disability_status
gender
race
veteran_status
criminal_history
relocation
bond/agreement
notice_period if not saved
```

Policy:

```text
If saved default exists -> show before final review.
If no saved default -> ask user.
Never guess.
```

---

## Browser Session Security

Rules:

1. One user cannot access another user's browser.
2. Browser sessions expire.
3. Cookies are encrypted if saved.
4. User can revoke saved sessions.
5. Do not log passwords.
6. Do not screenshot password fields if avoidable.
7. Do not store raw OTP.
8. Do not bypass CAPTCHA.

Browser session lifecycle:

```text
created
active
waiting_for_user
paused
completed
expired
destroyed
```

---

## Telegram Mini App Browser Controls

Mini App should show:

- Browser screen.
- Current status.
- Job details.
- Application progress.
- Agent activity log.
- Control buttons.

Buttons:

```text
[Pause Agent]
[Resume Agent]
[Take Control]
[Let Agent Continue]
[Approve Submit]
[Cancel Application]
[Skip Job]
```

When user clicks browser screen:

```json
{
  "type": "browser_click",
  "x": 512,
  "y": 344
}
```

When user types:

```json
{
  "type": "browser_keypress",
  "text": "hello"
}
```

---

## Approval System

OpenClaw should create approval requests for:

- final submit
- generated answer
- sensitive question
- batch apply
- saving login session

Approval request example:

```json
{
  "approval_type": "final_submit",
  "application_id": "app_123",
  "prompt": "Ready to submit application to ExampleTech?",
  "payload": {
    "company": "ExampleTech",
    "role": "Software Engineer Intern",
    "resume": "Backend Resume",
    "answers": []
  }
}
```

Allowed statuses:

```text
pending
approved
rejected
edited
expired
```

---

## OpenClaw Tool Design

Expose apply automation to OpenClaw as tools.

Suggested tools:

```text
apply_start(job_id, user_id)
apply_get_status(application_id)
apply_pause(application_id)
apply_resume(application_id)
apply_answer_question(application_id, answer)
apply_approve_submit(application_id)
apply_cancel(application_id)
application_tracker_update(application_id, status)
```

OpenClaw flow:

```text
User taps Apply
OpenClaw calls apply_start
Tool starts browser and returns application_id
OpenClaw sends Mini App link
Tool emits needs_user/approval events
OpenClaw sends Telegram messages
User responds
OpenClaw calls next tool
```

---

## Error Handling

Common errors:

```text
page_not_found
application_closed
login_required
captcha_required
unsupported_platform
resume_upload_failed
field_mapping_failed
submit_failed
network_timeout
user_cancelled
duplicate_application
```

Error handling policy:

- If recoverable, ask user.
- If unsupported, mark skipped.
- If duplicate, do not apply again.
- If submit unclear, capture screenshot and ask user.
- If page crashes, retry once.

---

## Logging And Audit

Save useful logs:

- status changes
- fields detected
- fields filled by category, not secret values
- approval events
- submit result
- screenshots after final submission

Do not save:

- passwords
- OTP
- raw cookies in logs
- secret tokens
- full sensitive answers unless user approved storing them

Example safe log:

```json
{
  "event": "field_filled",
  "field_type": "email",
  "confidence": 0.98
}
```

Unsafe log:

```json
{
  "email": "real@email.com",
  "password": "secret"
}
```

---

## MVP Implementation Plan

### Phase 1: Apply Session Skeleton

Build:

- application table
- apply_start API
- Playwright browser launch
- open application URL
- status events
- Telegram Mini App link

Success:

```text
User taps Apply, browser session starts, Mini App shows status.
```

---

### Phase 2: Mini App Browser View

Build:

- screenshot streaming
- click mapping
- keyboard input
- pause/resume
- user takeover mode

Success:

```text
User can see and interact with browser inside Telegram Mini App.
```

---

### Phase 3: Greenhouse Adapter

Build:

- detect Greenhouse form
- fill basic fields
- upload resume
- answer simple questions
- stop before submit

Success:

```text
Greenhouse applications can be filled with user approval.
```

---

### Phase 4: Lever Adapter

Build:

- detect Lever forms
- fill profile fields
- upload resume
- handle custom questions
- stop before submit

Success:

```text
Lever applications can be filled with user approval.
```

---

### Phase 5: Final Review And Submit

Build:

- final review UI
- approval request
- submit-after-approval
- confirmation capture
- tracker update

Success:

```text
Agent submits only after user approval and saves result.
```

---

### Phase 6: Generic Form Adapter

Build:

- generic field detection
- confidence scoring
- AI/OpenClaw mapping fallback
- sensitive question policy

Success:

```text
Unknown forms can be partially filled safely.
```

---

### Phase 7: Batch Apply

Build:

- user selects multiple jobs
- agent applies sequentially
- pauses when needed
- daily summary

Success:

```text
User approves a batch and agent handles applications one by one.
```

---

## Suggested MVP Scope

Best first production-like MVP:

```text
Telegram apply button
Mini App opens
Playwright browser session starts
Greenhouse + Lever support
Resume upload
Basic fields auto-fill
Unknown questions ask user
Final submit approval
Application tracker update
```

Do not include in first MVP:

- Full Workday automation.
- Full LinkedIn automation.
- Password storage.
- Auto-submit without review.
- CAPTCHA bypass.
- Mass apply without approval.

---

## Quality Checklist

Before submitting any application, check:

- Correct company.
- Correct role.
- Correct resume.
- Correct user profile.
- Required fields complete.
- No fake answers.
- Sensitive answers confirmed.
- User approved final submit.
- Screenshot captured.
- Tracker updated.

---

## Final Recommended Design

Use this design:

```text
OpenClaw as orchestrator
Telegram Bot as chat interface
Telegram Mini App as browser/approval UI
Playwright as browser automation
Adapters for known ATS platforms
Generic AI-assisted form mapper for unknown forms
Human approval before submit
Application tracker for history
```

The strongest version is not "fully automatic apply".

The strongest useful version is:

```text
Agent does the boring work.
User controls sensitive steps.
Agent never submits without approval.
```

That is the safest, most practical, and most scalable approach.

