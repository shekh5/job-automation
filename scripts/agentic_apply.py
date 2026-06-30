import sys
import json
import urllib.request
import urllib.error
import time
import os
import base64
from pathlib import Path

HOST_WORKER_URL = os.environ.get("HOST_WORKER_URL", "http://host.docker.internal:4555")
OPENCLAW_API_URL = os.environ.get("OPENCLAW_API_URL", "http://host.docker.internal:18789/v1/chat/completions")
# Using a fixed model that maps to whatever OpenClaw has loaded
MODEL = "openai/gpt-5.4" 
DEFAULT_PROFILE_PATH = "/home/node/.openclaw/workspace/profile.json"
DEFAULT_RESUME_CANDIDATES = [
    "/home/node/.openclaw/workspace/main/telegram-apply-engine/data/resumes/bhawani_resume.pdf",
    "/home/node/.openclaw/workspace/resume.pdf",
    "/home/node/.openclaw/workspace/jaskirat/resume.pdf",
]

def get_openclaw_token():
    config_path = os.path.expanduser("~/.openclaw/openclaw.json")
    try:
        with open(config_path, "r") as f:
            config = json.load(f)
            return config.get("gateway", {}).get("auth", {}).get("token")
    except Exception:
        return "8fa1c447ae1913c3c53dca17b62e6be160fae538249d702683eec90c83cb5b6b"

def post(url, data=None, headers=None):
    if headers is None:
        headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="POST")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on {url}: {e.read().decode()}")
        sys.exit(1)

def get(url):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on {url}: {e.read().decode()}")
        sys.exit(1)

def get_binary(url):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on {url} (screenshot): {e}")
        return None

def query_llm(messages, token):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "click_element",
                "description": "Click an element on the screen using a CSS selector (e.g. 'button#submit' or 'input[type=\"submit\"]')",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"}
                    },
                    "required": ["selector"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "type_element",
                "description": "Type text into an input field using a CSS selector.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "selector": {"type": "string"},
                        "text": {"type": "string"}
                    },
                    "required": ["selector", "text"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "finish",
                "description": "Call this when the job application is fully submitted or you are blocked.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "message": {"type": "string"}
                    },
                    "required": ["success", "message"]
                }
            }
        }
    ]

    data = {
        "model": MODEL,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        "temperature": 0.0
    }
    
    return post(OPENCLAW_API_URL, data=data, headers=headers)

def load_profile():
    profile_path = os.environ.get("AGENTIC_PROFILE_PATH", DEFAULT_PROFILE_PATH)
    try:
        with open(profile_path, "r") as f:
            profile = json.load(f)
            if isinstance(profile, dict):
                return profile
    except Exception:
        pass
    return None

def detect_resume_path():
    env_resume = os.environ.get("AGENTIC_RESUME_PATH")
    candidates = [env_resume] if env_resume else []
    candidates.extend(DEFAULT_RESUME_CANDIDATES)
    for candidate in candidates:
      if candidate and os.path.exists(candidate):
        return candidate
    return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 agentic_apply.py <job_url>")
        sys.exit(1)

    url = sys.argv[1]
    token = get_openclaw_token()
    headless = os.environ.get("AGENTIC_HEADLESS", "true").strip().lower() not in {"0", "false", "no"}
    
    print(f"Starting Agentic Application for: {url}")
    print(f"Headless mode: {headless}")
    
    # 1. Create Session
    session_res = post(f"{HOST_WORKER_URL}/sessions", {
        "application_id": f"agentic-{int(time.time())}",
        "url": url,
        "headless": headless
    })
    session_id = session_res["session"]["application_id"]
    print(f"Session created: {session_id}. Waiting 5 seconds for page load...")
    time.sleep(5)

    profile = load_profile()
    resume_path = detect_resume_path()
    if profile:
        fill_payload = {"profile": profile}
        if resume_path:
            fill_payload["resume_path"] = resume_path
        print(f"Pre-filling profile fields{'' if not resume_path else f' and resume from {resume_path}'}...")
        try:
            fill_res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/fill", fill_payload)
            print(json.dumps(fill_res, indent=2))
        except Exception as e:
            print(f"Pre-fill step failed: {e}")
            sys.exit(1)
    else:
        print("No profile.json found; continuing without prefill.")

    messages = [
        {
            "role": "system",
            "content": (
                "You are an autonomous browser agent applying for a job on behalf of the user. "
                "You will be provided with a JSON dump of the current web page containing title, url, inputs, and buttons, along with a screenshot of the page. "
                "Your job is to look at the DOM and the screenshot, decide what to click or type next, and use your tools to navigate the page. "
                "CRITICAL RULE: Always verify that your previous action (click/type) actually worked by observing the new page state before taking the next action. "
                "CRITICAL RULE: DO NOT click the final submit button yourself. When the application is completely filled and ready to submit, call the finish tool with success=true and message='Ready for human review'."
            )
        }
    ]

    log_dir = Path(os.path.join(os.path.dirname(__file__), "..", "logs", f"agentic_apply_{session_id}"))
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"Logging session to {log_dir}/")

    step = 1
    while step < 15: # Safety limit
        print(f"\n--- Step {step} ---")
        
        # Observe
        print("Observing DOM...")
        inspect_res = get(f"{HOST_WORKER_URL}/sessions/{session_id}/inspect")
        dom = inspect_res.get("inspection", {})
        
        with open(log_dir / f"step_{step}_dom.json", "w") as f:
            json.dump(dom, f, indent=2)
            
        print("Taking screenshot...")
        screenshot_data = get_binary(f"{HOST_WORKER_URL}/sessions/{session_id}/screenshot")
        
        message_content = []
        message_content.append({
            "type": "text",
            "text": f"Current Page State:\n{json.dumps(dom, indent=2)}\n\nWhat is your next action?"
        })
        
        if screenshot_data:
            with open(log_dir / f"step_{step}_screenshot.png", "wb") as f:
                f.write(screenshot_data)
            b64_image = base64.b64encode(screenshot_data).decode("utf-8")
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_image}"
                }
            })
            
        messages.append({
            "role": "user",
            "content": message_content
        })

        # Think & Act
        print("LLM is thinking...")
        llm_res = query_llm(messages, token)
        
        choice = llm_res["choices"][0]
        message = choice["message"]
        messages.append(message) # Append assistant message
        
        with open(log_dir / f"step_{step}_llm.json", "w") as f:
            json.dump(llm_res, f, indent=2)

        if "tool_calls" in message and message["tool_calls"]:
            tool_call = message["tool_calls"][0]
            func_name = tool_call["function"]["name"]
            args = json.loads(tool_call["function"]["arguments"])
            
            print(f"LLM decided to: {func_name}({args})")
            
            tool_result_msg = {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": func_name,
                "content": "Success"
            }

            try:
                if func_name == "click_element":
                    post(f"{HOST_WORKER_URL}/sessions/{session_id}/click", {"selector": args["selector"]})
                    time.sleep(2)
                elif func_name == "type_element":
                    post(f"{HOST_WORKER_URL}/sessions/{session_id}/type", {"selector": args["selector"], "text": args["text"]})
                    time.sleep(1)
                elif func_name == "finish":
                    print(f"\n======================================")
                    print(f"Agent finished! Success: {args.get('success')}. Message: {args.get('message')}")
                    print(f"SESSION_ID: {session_id}")
                    print(f"SCREENSHOT_PATH: {log_dir / f'step_{step-1}_screenshot.png'}")
                    print(f"======================================\n")
                    sys.exit(0)
            except Exception as e:
                print(f"Tool execution failed: {e}")
                tool_result_msg["content"] = f"Failed: {e}"
                
            messages.append(tool_result_msg)
        else:
            print("LLM returned text instead of a tool call:")
            print(message.get("content"))
            messages.append({"role": "user", "content": "Please use a tool to take an action."})
            
        step += 1

    print("\nMaximum steps reached. Closing session...")
    post(f"{HOST_WORKER_URL}/sessions/{session_id}/close")
    print("Done!")

if __name__ == "__main__":
    main()
