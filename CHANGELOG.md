# Workspace Changelog

This file tracks the updates made to agent configuration files (Markdown) and automation scripts in the OpenClaw workspace. It serves as a version history to understand *when*, *what*, and *why* changes were made.

## [2026-06-30] - Agentic Visual UI and Oscillation Fixes

### Added
- **`scripts/ats_submit.py`**: A new script dedicated to sending the final submit command to the HostWorker API. This decouples the application filling from the submission, allowing the user to review the application first.

### Changed
- **`scripts/agentic_apply.py`**: Overhauled the script to inject visual DOM state (screenshots) into the LLM observation loop. Added a `CRITICAL RULE` forcing the agent to halt and call `finish` instead of submitting, giving the user a chance to review the filled form via a screenshot.
- **`jaskirat/TOOLS.md`**: Documented the separation between filling (`agentic_apply.py`) and submitting (`ats_submit.py`).
- **`jaskirat/AGENTS.md`**: 
  - Added the **Human Approval Workflow**, instructing Jaskirat to send the generated screenshot to the user on Telegram and wait for explicit approval (e.g., "op apply") before running `ats_submit.py`.
  - **Oscillation Fix**: Added strict constraints forbidding Jaskirat from using native browser tools or writing raw Python `urllib.request.urlopen` commands to manually interact with the HostWorker API. Jaskirat is now forced to stick to the established scripts to prevent infinite polling loops and tool hallucination.

### Why
- The web is highly visual and messy. The agent needed visual context (screenshots) alongside the raw DOM to make accurate decisions when filling applications (the "Better Eyes" architecture).
- Users required a way to verify the filled application before final submission to avoid sending incorrect data.
- Jaskirat was hallucinating raw backend HTTP requests to the HostWorker to inspect the page manually when it got confused, which led to infinite tool-calling loops (oscillations) and session crashes. Strict script enforcement resolves this.
