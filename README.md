# Jaskirat - Agentic ATS Job Automation 🚀

Jaskirat is an OpenClaw agent designed to automate finding, parsing, and applying to jobs via ATS platforms (like Greenhouse, Lever, and Workday). It uses a "Better Eyes" visual architecture to take screenshots of the browser DOM and ask for human-in-the-loop approval before final submission.

## Installation

1. Install OpenClaw on your machine (see [docs.openclaw.ai](https://docs.openclaw.ai)).
2. Clone this repository into your OpenClaw workspace:
   ```bash
   git clone https://github.com/YOUR_USERNAME/jaskirat-agent.git ~/.openclaw/workspace
   ```
3. Rename `profile.example.json` to `profile.json` and fill in your real details.
4. Add your `resume.pdf` to the root of the workspace.
5. Rename `.env.example` to `.env` and configure your API keys.

## How to Use

Send Jaskirat a job link via Telegram (e.g., "Apply to this KLA role: https://link..."). Jaskirat will drive the browser, fill out the application, and send you a screenshot for final approval before clicking submit!

## Architecture

- **`scripts/agentic_apply.py`**: The core application engine. Reads the DOM and uses vision to navigate the application. Pauses and saves a screenshot before submission.
- **`scripts/ats_submit.py`**: A manual trigger script that finalizes the application after the user explicitly replies with "op apply".
- **`jaskirat/AGENTS.md`**: The strict behavior system prompt that prevents infinite looping/hallucination by enforcing script usage over raw API polling.
