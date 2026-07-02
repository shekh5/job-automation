import sys
import json
import urllib.request
import urllib.error
import time
import os
import base64
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

HOST_WORKER_URL = os.environ.get("HOST_WORKER_URL", "http://127.0.0.1:4555")
OPENCLAW_API_URL = os.environ.get("OPENCLAW_API_URL", "http://127.0.0.1:18789/v1/chat/completions")
# Using a fixed model that maps to whatever OpenClaw has loaded
MODEL = "openclaw" 
DEFAULT_PROFILE_PATH = "/Users/bhawanisingh/.openclaw/workspace/profile.json"
DEFAULT_RESUME_CANDIDATES = [
    "/Users/bhawanisingh/.openclaw/workspace/main/telegram-apply-engine/data/resumes/bhawani_resume.pdf",
    "/Users/bhawanisingh/.openclaw/workspace/resume.pdf",
    "/Users/bhawanisingh/.openclaw/workspace/jaskirat/resume.pdf",
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
                "name": "click_coordinate",
                "description": "Click a specific X,Y pixel coordinate on the screen. Calculate the center of the element using the provided 'box' (x + width/2, y + height/2).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"}
                    },
                    "required": ["x", "y"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "type_coordinate",
                "description": "Type text into a specific X,Y pixel coordinate on the screen. Calculate the center of the element using the provided 'box' (x + width/2, y + height/2).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer"},
                        "y": {"type": "integer"},
                        "text": {"type": "string"}
                    },
                    "required": ["x", "y", "text"]
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
        },
        {
            "type": "function",
            "function": {
                "name": "request_info",
                "description": "Call this if you absolutely do not know the answer to a required form field (e.g., visa requirements, specific background questions) and need to ask the user.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "missing_fields": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["missing_fields"]
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
    
    result = post(OPENCLAW_API_URL, data=data, headers=headers)
    return result

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

def known_greenhouse_answers(profile):
    if not profile:
        return {}
    clojure_ability = profile.get("clojure_ability")
    if isinstance(clojure_ability, str) and clojure_ability.strip().lower() in {"none", "no", "n/a"}:
        clojure_ability = "No"
    answers = {
        "country": profile.get("country_residence") or profile.get("location"),
        "degree--0": profile.get("degree"),
        "discipline--0": profile.get("discipline_major"),
        "end-year--0": profile.get("graduation_end_year"),
        "question_4824417008": profile.get("linkedin_url"),
        "question_4824418008": profile.get("currently_working_in_saas_or_product_company"),
        "question_13887930008": profile.get("uses_ai_coding_tools"),
        "question_13887931008": profile.get("comfortable_with_30_45_lpa_compensation"),
        "question_4824419008": profile.get("has_2_plus_years_full_stack_experience"),
        "question_4824420008": profile.get("can_join_within_45_days"),
        "question_4846730008": clojure_ability,
        "question_4824421008": profile.get("can_work_remotely_based_in_india") or "Yes",
        "question_13887932008": profile.get("loom_url"),
        "question_36707269002": profile.get("linkedin_url"),
        "question_36707276002": profile.get("country_residence"),
        "question_36707271002": profile.get("country_residence"),
        "question_36749075002": profile.get("location") or profile.get("city"),
        "question_36707270002": profile.get("first_name") or profile.get("full_name"),
        "question_36749076002": "No" if profile.get("graphql_experience") == "No" else profile.get("python_proficiency"),
        "question_36749077002": profile.get("llm_ecosystem_experience"),
        "question_36707272002": profile.get("employment_restrictions"),
        "question_36707273002": profile.get("interview_accommodations", "No adjustments needed."),
        "question_36707274002": profile.get("visa_sponsorship"),
        "question_36707275002": profile.get("previous_gitlab"),
    }
    return {key: value for key, value in answers.items() if value}

def prefill_known_greenhouse_questions(session_id, profile):
    answers = known_greenhouse_answers(profile)
    if not answers:
        return None
    script = f"""
(() => {{
  const answers = {json.dumps(answers)};
  const filled = [];
  for (const [id, value] of Object.entries(answers)) {{
    const element = document.getElementById(id);
    if (!element) continue;
    const prototype = element.tagName === 'TEXTAREA'
      ? window.HTMLTextAreaElement.prototype
      : window.HTMLInputElement.prototype;
    const valueSetter = Object.getOwnPropertyDescriptor(prototype, 'value')?.set;
    element.focus();
    if (valueSetter) {{
      valueSetter.call(element, value);
    }} else {{
      element.value = value;
    }}
    element.dispatchEvent(new Event('input', {{ bubbles: true }}));
    element.dispatchEvent(new KeyboardEvent('keydown', {{ bubbles: true, key: 'Enter', code: 'Enter' }}));
    element.dispatchEvent(new KeyboardEvent('keyup', {{ bubbles: true, key: 'Enter', code: 'Enter' }}));
    element.dispatchEvent(new Event('change', {{ bubbles: true }}));
    element.blur();
    filled.push({{ id, value, observed: element.value }});
  }}
  return filled;
}})()
"""
    return post(f"{HOST_WORKER_URL}/sessions/{session_id}/evaluate", {"script": script})

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 agentic_apply.py <job_url> [session_id]")
        sys.exit(1)

    url = sys.argv[1]
    resume_session_id = sys.argv[2] if len(sys.argv) > 2 else None
    token = get_openclaw_token()
    headless = os.environ.get("AGENTIC_HEADLESS", "true").strip().lower() not in {"0", "false", "no"}
    
    print(f"Starting Agentic Application for: {url}")
    print(f"Headless mode: {headless}")
    
    if resume_session_id:
        session_id = resume_session_id
        print(f"Resuming existing session: {session_id}")
    else:
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
            if not resume_session_id:
                fill_res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/fill", fill_payload)
                print(json.dumps(fill_res, indent=2))
                known_fill_res = prefill_known_greenhouse_questions(session_id, profile)
                if known_fill_res is not None:
                    print("Pre-filled known Greenhouse question IDs:")
                    print(json.dumps(known_fill_res.get("result"), indent=2))
                    time.sleep(2)
                    known_fill_res = prefill_known_greenhouse_questions(session_id, profile)
                    print("Re-applied known Greenhouse question IDs:")
                    print(json.dumps(known_fill_res.get("result"), indent=2))
            else:
                print("Skipping pre-fill because we are resuming an existing session.")
        except Exception as e:
            print(f"Pre-fill step failed: {e}")
            sys.exit(1)
    else:
        print("No profile.json found; continuing without prefill.")

    known_profile_context = ""
    if profile:
        known_profile_context = (
            "\nKnown applicant profile and user-confirmed answers:\n"
            f"{json.dumps(profile, indent=2)}\n"
            "Use these values to answer required application questions when relevant. "
            "If a required answer is still absent from this profile/resume context, request_info instead of guessing.\n"
        )

    messages = [
        {
            "role": "system",
            "content": (
                "You are an autonomous browser agent applying for a job on behalf of the user. "
                "You will be provided with a JSON dump of the current web page containing title, url, inputs, and buttons, along with a screenshot of the page. Each element has a 'box' containing its x, y, width, and height in pixels. "
                "Your job is to look at the DOM and the screenshot, decide what to click or type next, and use your tools to navigate the page by calculating the center of the element (x + width/2, y + height/2). "
                f"{known_profile_context}"
                "CRITICAL RULE: Always verify that your previous action (click/type) actually worked by observing the new page state before taking the next action. "
                "CRITICAL RULE: Inputs marked alreadyHandled=true in the page state are already answered from the user's confirmed profile. Do not click or type into those inputs again; move to unanswered required fields or finish for human review.\n"
                "CRITICAL RULE: If a blank input has a knownAnswer value, use that value to fill or select the field. Do not finish while any required blank field with knownAnswer is still visibly unanswered.\n"
                "CRITICAL RULE FOR DROPDOWNS: If typing into a field (like Country) does not register the selection, DO NOT keep typing. The field is likely a custom dropdown. You must first use 'click_coordinate' on the input field to open the dropdown menu, then on the NEXT turn, use 'click_coordinate' on the visible option that appears.\n"
                "CRITICAL RULE: If a required question asks for personal information not in the resume (e.g. Visa sponsorship, LinkedIn URL, specific history) and you DO NOT know the answer, DO NOT GUESS. Call the 'request_info' tool to ask the user.\n"
                "CRITICAL RULE: DO NOT click the final submit button yourself. When the application is completely filled and ready to submit, call the finish tool with success=true and message='Ready for human review'.\n\n"
                "ABSOLUTE STRICT REQUIREMENT: You MUST use one of the provided tools (click_coordinate, type_coordinate, request_info, or finish) in EVERY response. DO NOT output conversational text. Return a valid JSON tool call."
            )
        }
    ]

    log_dir = Path(os.path.join(os.path.dirname(__file__), "..", "logs", f"agentic_apply_{session_id}"))
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"Logging session to {log_dir}/")

    step = 1
    while step < 30: # Safety limit
        print(f"\n--- Step {step} ---")
        
        # Observe
        print("Observing DOM...")
        inspect_res = get(f"{HOST_WORKER_URL}/sessions/{session_id}/inspect")
        dom = inspect_res.get("inspection", {})
        known_answers = known_greenhouse_answers(profile)
        if known_answers:
            for field in dom.get("inputs", []):
                answer = known_answers.get(field.get("id"))
                if answer:
                    if field.get("value"):
                        field["value"] = answer
                        field["alreadyHandled"] = True
                        field["disabled"] = True
                        field["readOnly"] = True
                    else:
                        field["knownAnswer"] = answer
        
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

        # Strip old screenshots and DOMs from previous user messages to prevent payload bloat
        for m in messages[:-1]:
            if m.get("role") == "user" and isinstance(m.get("content"), list):
                for item in m["content"]:
                    if item.get("type") == "image_url":
                        item["image_url"]["url"] = "data:image/png;base64,"
                    elif item.get("type") == "text" and "Current Page State:" in item.get("text", ""):
                        item["text"] = "[Old page state omitted to save memory]"

        # Think & Act
        print("LLM is thinking...")
        llm_res = query_llm(messages, token)
        
        choice = llm_res["choices"][0]
        message = choice["message"]
        messages.append(message) # Append assistant message
        
        with open(log_dir / f"step_{step}_llm.json", "w") as f:
            json.dump(llm_res, f, indent=2)

        try:
            # Fallback for plain text JSON output
            if "tool_calls" not in message or not message["tool_calls"]:
                text_val = message.get("content", "").strip()
                if text_val.startswith("{") and text_val.endswith("}"):
                    parsed = json.loads(text_val)
                    if "action" in parsed and "tool" not in parsed:
                        parsed["tool"] = parsed["action"]
                    if "tool" in parsed:
                        message["tool_calls"] = [{
                            "id": "call_" + str(int(time.time())),
                            "function": {
                                "name": parsed["tool"],
                                "arguments": json.dumps(parsed)
                            }
                        }]
        except Exception:
            pass

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
                if func_name == "click_coordinate":
                    x, y = args.get("x"), args.get("y")
                    post(f"{HOST_WORKER_URL}/sessions/{session_id}/clickAt", {"x": x, "y": y})
                    time.sleep(2)
                elif func_name == "type_coordinate":
                    x, y, text = args.get("x"), args.get("y"), args.get("text")
                    post(f"{HOST_WORKER_URL}/sessions/{session_id}/typeAt", {"x": x, "y": y, "text": text})
                    time.sleep(1)
                elif func_name == "finish":
                    print(f"\n======================================")
                    print(f"Agent finished! Success: {args.get('success')}. Message: {args.get('message')}")
                    print(f"SESSION_ID: {session_id}")
                    print(f"SCREENSHOT_PATH: {log_dir / f'step_{step-1}_screenshot.png'}")
                    print(f"======================================\n")
                    sys.exit(0)
                elif func_name == "request_info":
                    missing = args.get('missing_fields', [])
                    print(f"\n======================================")
                    print(f"MISSING_REQUIRED_INFO: {', '.join(missing)}")
                    print(f"SESSION_ID: {session_id}")
                    print(f"======================================\n")
                    sys.exit(2)
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
