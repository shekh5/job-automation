# Telegram Job Helper: Browser-Based Job Finder And Applier

## Goal

Build a Telegram bot that helps users find jobs and apply to them.

The bot should act like a job assistant:

- Find suitable jobs.
- Ask the user what kind of jobs they want.
- Open job websites in a browser.
- Fill application forms.
- Ask the user before doing sensitive actions.
- Let the user log in safely when username, password, OTP, or CAPTCHA is needed.
- Submit applications only after user approval.

The important idea is:

> The agent can do the boring work, but the user should stay in control of login, private data, and final submission.

---

## Very Simple Explanation

Telegram itself cannot show a full browser directly inside a normal chat message.

But Telegram can open a small web app inside Telegram. This is called a Telegram Web App or Telegram Mini App.

So the flow can be:

1. User talks to your Telegram bot.
2. Bot says: "I found some jobs. Tap here to apply."
3. User taps a button.
4. A web app opens inside Telegram.
5. That web app shows a browser screen.
6. The agent uses that browser to open job websites.
7. If login is needed, the user types username, password, OTP, or CAPTCHA.
8. Agent fills the application.
9. Before final submit, user checks and approves.
10. Agent submits the application.

Think of it like this:

```text
Telegram chat
  -> opens your mini app
      -> mini app shows a browser
          -> agent controls browser
          -> user helps with login and approval
```

---

## Why Not Just Ask For Username And Password In Telegram?

Do not ask users to send passwords in chat.

That is unsafe because:

- Telegram messages can be copied, forwarded, or exposed.
- Users may accidentally share private credentials.
- Your bot would become responsible for handling raw passwords.
- Job websites may detect suspicious login behavior.

Better approach:

- User logs in directly inside a browser window.
- Agent does not need to know the password.
- OTP and CAPTCHA are handled by the user.
- Your system can save the logged-in browser session only if the user allows it.

---

## What Telegram Can And Cannot Do

### Telegram Can Do This

- Send job matches in chat.
- Show buttons like `Apply`, `Approve`, `Skip`, `Edit Answer`.
- Open a Telegram Mini App.
- Identify the Telegram user securely inside your web app.
- Send updates like:
  - "Application started"
  - "Login needed"
  - "Waiting for approval"
  - "Application submitted"

### Telegram Cannot Directly Do This

- Put a real Chrome browser inside a normal chat message.
- Automatically log in to websites without user involvement.
- Bypass CAPTCHA or OTP.
- Safely collect passwords in normal chat.
- Guarantee that every job website will allow automation.

---

## Recommended Product Flow

### Step 1: User Starts The Bot

User sends:

```text
/start
```

Bot replies:

```text
Hi. I can help you find and apply to jobs.

What kind of jobs are you looking for?
```

Bot asks simple questions:

- Role: software, AI, data, cloud, QA, security, product engineering.
- Experience: fresher, intern, 0-1 years, 0-2 years.
- Location: India, remote, specific city.
- Resume: ask user to upload resume.
- Skills: Python, React, Java, Node.js, SQL, etc.
- Salary or preference if needed.

---

### Step 2: Bot Finds Jobs

The job finder searches:

- Company career pages.
- ATS platforms like Greenhouse, Lever, Ashby, Workday.
- Public job boards if allowed.
- Saved job sources.

The bot filters bad matches:

- Too senior.
- Expired.
- Non-engineering if user wants tech.
- Wrong location.
- Weak or vague job posts.
- Jobs that look fake.

Bot sends a shortlist:

```text
I found 8 good matches.

1. Software Engineer Intern - Company A - Remote India
2. Associate Software Engineer - Company B - Bengaluru
3. Backend Developer Fresher - Company C - Hyderabad

Tap a job to view or apply.
```

---

### Step 3: User Selects Jobs

Each job can have buttons:

```text
[View Job] [Apply] [Skip]
```

When user taps `Apply`, the bot opens your Telegram Mini App.

---

### Step 4: Telegram Mini App Opens

The Mini App is your own web page opened inside Telegram.

It can show:

- Job title.
- Company.
- Resume being used.
- Application progress.
- Browser window.
- Agent activity.
- Buttons for approval.

Example screen:

```text
Applying to: Associate Software Engineer - Company B

Status: Opening company career page...

[Browser screen here]

[Pause Agent] [Take Control] [Approve Submit]
```

---

### Step 5: Remote Browser Starts

Your backend starts a browser session using Playwright or Chrome.

The browser runs on your server.

The user sees the browser through the Mini App.

The user can:

- Click.
- Type.
- Log in.
- Solve CAPTCHA.
- Enter OTP.
- Review final form.

The agent can:

- Navigate pages.
- Fill fields.
- Upload resume.
- Select dropdowns.
- Answer standard questions.
- Stop and ask the user when unsure.

---

### Step 6: Login Handling

If the job website asks for login:

Bot or Mini App says:

```text
Login needed.

Please type your username and password directly in the browser.
I will wait.
```

Important:

- User types credentials into the website, not into Telegram chat.
- Agent pauses while user logs in.
- If OTP is needed, user enters OTP.
- If CAPTCHA appears, user solves it.
- After login, agent continues.

---

### Step 7: Agent Fills Application

Agent fills fields using known user profile data:

- Name.
- Email.
- Phone.
- Location.
- Education.
- Experience.
- Skills.
- Resume.
- LinkedIn.
- GitHub.
- Portfolio.
- Work authorization.
- Notice period.

For questions it knows, it fills automatically.

For questions it does not know, it asks:

```text
The form asks:

"Why do you want to join this company?"

Suggested answer:
"I am interested in this role because it matches my backend development skills..."

[Use This] [Edit] [Skip Application]
```

---

### Step 8: Final Human Approval

Before submitting, the agent must stop.

Show a final review:

```text
Ready to submit application.

Company: Company B
Role: Associate Software Engineer
Resume: Bhawani_Resume_Backend.pdf
Location: Bengaluru

Answers:
- Experience: Fresher
- Notice period: Immediate
- Work authorization: India

[Submit Application] [Edit] [Cancel]
```

Only submit if user taps `Submit Application`.

---

### Step 9: Confirmation

After submission:

```text
Application submitted.

Company: Company B
Role: Associate Software Engineer
Time: 23 Jun, 2:15 PM

I saved this in your application tracker.
```

Save:

- Job title.
- Company.
- URL.
- Date applied.
- Resume used.
- Status.
- Confirmation screenshot if available.
- Any application ID if available.

---

## System Architecture

```text
User
  |
  v
Telegram Bot
  |
  | opens
  v
Telegram Mini App
  |
  | WebSocket
  v
Your Backend API
  |
  | controls
  v
Remote Browser Worker
  |
  | opens
  v
Job Websites
```

### Main Parts

1. Telegram Bot
2. Telegram Mini App frontend
3. Backend API
4. Browser automation worker
5. Job discovery system
6. User profile and resume storage
7. Application tracker
8. Human approval system

---

## Telegram Bot Responsibilities

The Telegram bot should handle:

- Onboarding user.
- Asking job preferences.
- Receiving resume.
- Showing job matches.
- Sending apply buttons.
- Sending status updates.
- Asking quick approvals.
- Notifying user when login or action is needed.

Example bot buttons:

```text
[Find Jobs]
[Apply To Selected]
[Open Browser]
[Pause]
[Approve Submit]
[View Tracker]
```

---

## Telegram Mini App Responsibilities

The Mini App should handle:

- Showing the browser view.
- Showing current application progress.
- Showing agent status.
- Letting user take control.
- Letting user approve final submit.
- Letting user edit answers.
- Letting user stop the process.

The Mini App is needed because normal Telegram chat is not enough for browser login.

---

## Backend Responsibilities

Backend should handle:

- Verify Telegram user identity.
- Create browser sessions.
- Connect user to their browser session.
- Run the agent.
- Save user profile securely.
- Store application history.
- Manage resumes.
- Handle approvals.
- Log safe audit events.

Do not store raw passwords.

---

## Browser Worker Responsibilities

The browser worker should handle:

- Open job application pages.
- Detect forms.
- Fill known fields.
- Upload files.
- Click next buttons.
- Pause for user on login, OTP, CAPTCHA, or unclear fields.
- Take screenshots for review.
- Stop before final submit.

Recommended tool:

- Playwright.

---

## How Browser Streaming Can Work

There are two possible ways.

### Option A: Browser Streaming

Run a real Chrome browser on the server.

Stream the browser screen to the Mini App.

Send user clicks and keyboard input back to the browser.

This is the best approach when websites block iframes.

Possible technologies:

- Chrome DevTools Protocol screencast.
- Playwright screenshots plus click mapping.
- noVNC with a browser inside a virtual display.
- WebRTC-based browser streaming.

### Option B: Iframe

Open the job website inside an iframe.

This is simpler but usually unreliable.

Many job sites block iframe loading for security.

So iframe should not be the main plan.

Recommended choice:

> Use server-side browser streaming, not iframe.

---

## What Can Be Fully Automated?

These parts can be mostly automated:

- Job search.
- Job filtering.
- Ranking jobs.
- Creating application shortlist.
- Detecting application forms.
- Filling basic profile fields.
- Uploading resume.
- Selecting common dropdowns.
- Writing draft answers.
- Tracking application status.
- Sending reminders.
- Avoiding duplicate applications.

---

## What Should Be Human-In-The-Loop?

These parts should ask the user:

- Website login.
- Password entry.
- OTP.
- CAPTCHA.
- Consent to save logged-in session.
- Final application submission.
- Any legally sensitive question.
- Any question about salary, relocation, disability, work authorization, criminal history, or equal opportunity information.
- Any question where the agent is unsure.

---

## What Should Not Be Automated Without Permission?

Do not automatically:

- Submit applications without approval.
- Invent answers.
- Fake experience.
- Fake education.
- Fake skills.
- Apply to jobs the user did not approve.
- Use the same cover letter everywhere without review.
- Store passwords.
- Bypass CAPTCHA.
- Spam hundreds of applications.
- Apply to roles that clearly do not match the user.

---

## Levels Of Automation

### Level 1: Job Finder Only

Bot only finds jobs and sends links.

Automation level:

```text
Low
```

Easy to build.

No login handling needed.

---

### Level 2: Job Finder Plus Draft Assistant

Bot finds jobs and prepares answers or cover letters.

User applies manually.

Automation level:

```text
Medium-low
```

Useful and safe.

---

### Level 3: Assisted Apply

Agent opens the browser and fills forms.

User logs in and approves submit.

Automation level:

```text
Medium-high
```

This is the best practical version.

Recommended for your product.

---

### Level 4: Semi-Automatic Batch Apply

User approves a group of jobs.

Agent applies one by one.

Agent pauses only when needed.

Automation level:

```text
High
```

Needs strong safety checks.

Good only after Level 3 is reliable.

---

### Level 5: Fully Automatic Apply

Agent applies to many jobs without user review.

Automation level:

```text
Very high
```

Not recommended.

Problems:

- Risk of wrong applications.
- Risk of fake answers.
- Risk of account lock.
- Risk of spam behavior.
- Risk of violating job site terms.

---

## Recommended Automation Limit

For a serious product, automate up to:

```text
Level 3 first, then carefully Level 4.
```

Do not start with full auto-apply.

The safest strong workflow is:

```text
Agent finds jobs
Agent fills forms
User handles login
User approves final submit
Agent tracks applications
```

---

## Example User Journey

```text
User:
Find backend fresher jobs in India.

Bot:
I found 12 good jobs. Top 5 are ready.

User:
Apply to top 3.

Bot:
Opening application assistant.

Mini App:
Browser opened. Applying to Company A.

Agent:
I need login for Workday.

User:
Logs in inside browser.

Agent:
I filled the form. Please review.

User:
Clicks Submit.

Bot:
Application submitted. Moving to next job.
```

---

## Data You Need From User

Basic profile:

- Full name.
- Email.
- Phone.
- Current city.
- Preferred cities.
- Remote preference.
- Experience level.
- Education.
- Graduation year.
- Skills.
- Resume.
- LinkedIn.
- GitHub.
- Portfolio.

Job preferences:

- Role types.
- Location.
- Minimum salary if any.
- Internship/full-time preference.
- Work mode: remote, hybrid, onsite.
- Companies to avoid.
- Already applied companies.

Application answers:

- Notice period.
- Work authorization.
- Willing to relocate.
- Expected salary.
- Current salary if applicable.
- Preferred start date.

Sensitive fields should be optional and user-controlled.

---

## Security Rules

Use these rules from day one:

1. Never ask for passwords in Telegram chat.
2. Never store raw passwords.
3. Encrypt user resumes and profile data.
4. Encrypt browser session cookies if stored.
5. Let users delete their data.
6. Let users log out job websites.
7. Require approval before final submit.
8. Keep audit logs without secrets.
9. Do not expose browser sessions publicly.
10. Use HTTPS only.

---

## Human Approval Rules

The agent should pause and ask when:

- It is about to submit.
- It sees login.
- It sees CAPTCHA.
- It sees OTP.
- It sees a question it cannot answer confidently.
- It sees sensitive personal questions.
- It wants to use a generated answer.
- It detects that the job may not match the user.

Approval buttons:

```text
[Approve]
[Edit]
[Skip]
[Take Control]
[Stop]
```

---

## Application Quality Rules

The agent should not apply blindly.

Before applying, check:

- Is the role current?
- Is the role entry-level or matching user experience?
- Is the location acceptable?
- Is the company real?
- Is the application link working?
- Has the user already applied?
- Is the role relevant to user skills?

If quality is low, skip or ask user.

---

## MVP Plan

### Phase 1: Telegram Job Finder

Build:

- Telegram bot.
- User onboarding.
- Resume upload.
- Job preference collection.
- Job search.
- Job shortlist.
- Application tracker.

Output:

```text
User can get good job matches in Telegram.
```

---

### Phase 2: Mini App

Build:

- Telegram Mini App.
- Telegram user verification.
- Job details page.
- Resume/profile page.
- Application approval screen.

Output:

```text
User can open a web app inside Telegram.
```

---

### Phase 3: Browser Session

Build:

- Playwright browser worker.
- Browser session per user.
- Browser streaming or remote control.
- Pause/resume controls.
- Login handoff.

Output:

```text
User can see and control a browser from Telegram Mini App.
```

---

### Phase 4: Form Filling Agent

Build:

- Form detection.
- Field mapping.
- Resume upload.
- Dropdown handling.
- Draft answer generation.
- Screenshot review.

Output:

```text
Agent can fill most job application forms.
```

---

### Phase 5: Human Approval And Submit

Build:

- Final review screen.
- Submit approval button.
- Sensitive field detection.
- Application result tracking.

Output:

```text
Agent submits only after user approval.
```

---

### Phase 6: Batch Apply

Build:

- Apply to selected jobs one by one.
- Pause only when needed.
- Skip bad forms.
- Daily application report.

Output:

```text
User can approve a batch, and agent handles most work.
```

---

## Suggested Tech Stack

### Telegram

- Telegram Bot API.
- Inline keyboard buttons.
- Telegram Web App / Mini App.
- BotFather domain setup.

### Frontend

- React or simple HTML app.
- Telegram Web App SDK.
- WebSocket connection to backend.

### Backend

- Node.js or Python.
- PostgreSQL for data.
- Redis for browser session state.
- Object storage for resumes.

### Browser Automation

- Playwright.
- Chromium.
- Browser worker queue.

### Browser Streaming

Start simple:

- Screenshot every few hundred milliseconds.
- User clicks are mapped to browser coordinates.

Later improve:

- Chrome DevTools screencast.
- WebRTC streaming.
- noVNC if needed.

---

## Database Tables

Simple starting schema:

```text
users
  id
  telegram_user_id
  name
  created_at

user_profiles
  user_id
  email
  phone
  location
  skills
  preferences

resumes
  id
  user_id
  file_path
  label
  created_at

jobs
  id
  company
  title
  location
  url
  source
  discovered_at

applications
  id
  user_id
  job_id
  status
  resume_id
  submitted_at
  notes

browser_sessions
  id
  user_id
  status
  created_at
  expires_at

approval_requests
  id
  user_id
  application_id
  type
  status
  created_at
```

---

## Status States

Application status can be:

```text
found
shortlisted
user_approved
browser_started
login_needed
filling_form
waiting_user_answer
ready_to_submit
submitted
failed
skipped
```

---

## Agent Rules

The agent should follow these rules:

1. Never submit without user approval.
2. Never lie.
3. Never invent experience.
4. Never answer sensitive questions without user input.
5. Stop for login, OTP, and CAPTCHA.
6. Prefer quality over quantity.
7. Explain what it is doing in simple status messages.
8. Save application evidence.
9. Skip suspicious job posts.
10. Let user take over any time.

---

## Main Risks

### Risk 1: Job Sites Block Automation

Solution:

- Use human-visible browser.
- Slow down actions.
- Do not spam.
- Let user take over.

### Risk 2: Login Problems

Solution:

- User logs in manually.
- Agent waits.
- User handles OTP and CAPTCHA.

### Risk 3: Wrong Applications

Solution:

- Strong filters.
- Final review.
- User approval.

### Risk 4: Privacy Issues

Solution:

- Do not collect passwords.
- Encrypt user data.
- Allow deletion.
- Minimize stored data.

### Risk 5: Low-Quality Mass Apply

Solution:

- Limit daily applications.
- Prefer matched jobs.
- Ask approval for batches.

---

## Best First Version

The best first version should be:

```text
Telegram bot finds jobs
User selects jobs
Mini App opens browser
User logs in if needed
Agent fills form
User approves submit
Bot tracks application
```

This gives strong automation but keeps the user safe.

---

## Final Recommendation

Yes, you can build this with Telegram.

But do it like this:

- Use Telegram bot for chat and updates.
- Use Telegram Mini App for browser and approvals.
- Use Playwright for browser automation.
- Keep user in control for login and final submit.
- Automate job finding, filtering, form filling, resume upload, and tracking.
- Do not fully auto-submit applications without user approval.

Best automation limit:

```text
Automate 80 percent of the work.
Keep 20 percent human-controlled for safety.
```

That 20 percent should include:

- Login.
- OTP.
- CAPTCHA.
- Sensitive answers.
- Final submit.

