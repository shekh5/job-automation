import asyncio
import os
import yaml
from langchain_openai import ChatOpenAI
from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig

from buglesstack_reporter import report_crash_to_buglesstack
import state_manager

# 1. Load prompts (Configuration as Code)
def load_prompt(resume_path="dummy_resume.txt"):
    with open("../prompts/job_prompts.yaml", "r") as f:
        prompts = yaml.safe_load(f)
    
    # In a real scenario, load the actual resume text from file
    # For now, using a dummy string
    resume_text = "Name: Bhawani Singh\nExperience: AI Engineer, Python, OpenClaw"
    
    return prompts["job_application_prompt"].format(resume_text=resume_text)

async def run_stealth_application(job_url: str):
    print("🚀 Launching Stealth AI Job Applier...")
    
    # 0. State Management (Idempotency Check)
    state_manager.init_db()
    if state_manager.is_job_processed(job_url):
        print(f"⏭️ Skipping {job_url} - Already applied!")
        return
    
    # 2. Configure Camofox (The Stealth Engine)
    # The camoufox package should be available in our path after pip install
    stealth_browser = Browser(
        config=BrowserConfig(
            # We tell browser-use to launch Camofox instead of standard Chromium
            chrome_instance_path='/Users/bhawanisingh/.openclaw/workspace/.venv/bin/camoufox' 
        )
    )
    
    task_prompt = load_prompt()
    full_task = f"Navigate to {job_url}. {task_prompt}"

    # Initialize the Agent
    llm = ChatOpenAI(model="gpt-4o", temperature=0.0) # Or your preferred model
    agent = Agent(
        task=full_task,
        llm=llm,
        browser=stealth_browser
    )

    try:
        # 3. Execute with Deterministic Boundaries
        print("🧠 Handing control to Browser-Use (AI)...")
        result = await agent.run()
        print("✅ Application submitted successfully!")
        
        # State Management: Log success to the database
        state_manager.mark_job_completed(job_url)
        print("💾 State saved to SQLite.")
        
    except Exception as e:
        # 4. Observability & Chaos Recovery (Buglesstack)
        print("💥 Agent encountered a critical failure!")
        
        try:
            # Capture the visual state at the moment of failure
            screenshot = await stealth_browser.take_screenshot()
            dom = await stealth_browser.get_dom()
            
            report_crash_to_buglesstack(str(e), screenshot, dom)
        except Exception as capture_e:
            print(f"Failed to capture crash state: {capture_e}")
            
    finally:
        # Always close the stealth browser
        await stealth_browser.close()

if __name__ == "__main__":
    import sys
    # Dummy testing URL
    target_job = "https://example.com/apply" 
    if len(sys.argv) > 1:
        target_job = sys.argv[1]
        
    asyncio.run(run_stealth_application(target_job))
