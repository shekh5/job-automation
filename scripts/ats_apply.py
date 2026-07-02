import sys
import json
import urllib.request
import urllib.error
import time
import os

HOST_WORKER_URL = os.environ.get("HOST_WORKER_URL", "http://host.docker.internal:4555")

def post(url, data=None):
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, headers=headers, method="POST")
    if data:
        req.data = json.dumps(data).encode("utf-8")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error {e.code}: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def get(url):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"Error {e.code}: {body}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def maybe_advance_application(session_id):
    # Workday often opens a job shell first and only reveals the form after an
    # initial Apply/Continue click. Try to advance through that shell before
    # filling fields so we don't stop on the job description page.
    for label in ["Accept Cookies", "Apply", "Introduce Yourself", "Sign In", "Sign in with email", "Continue", "Next"]:
        print(f'Trying to advance application flow via "{label}"...')
        script = f"""
(() => {{
  const targetLabel = {json.dumps(label)}.toLowerCase();
  const texts = (el) => ((el.innerText || el.value || el.getAttribute('aria-label') || el.textContent || '')).trim();
  const visible = (el) => {{
    const rect = el.getBoundingClientRect();
    const style = window.getComputedStyle(el);
    return rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden';
  }};
  const buttons = Array.from(document.querySelectorAll('button, a, input[type="submit"], input[type="button"]'));
  const candidates = buttons.filter((el) => visible(el) && texts(el).toLowerCase().includes(targetLabel));
  if (candidates.length === 0) {{
    return {{
      clicked: false,
      currentUrl: window.location.href,
      visibleButtons: buttons.slice(0, 20).map(texts),
    }};
  }}

  const target = candidates[0];
  const clickedText = texts(target);
  target.click();
  return {{
    clicked: true,
    clickedText,
    currentUrl: window.location.href,
  }};
}})()
"""
        click_res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/evaluate", {"script": script})
        print("Advance result payload:", json.dumps(click_res, indent=2))
        result = click_res.get("result", {})
        if not result.get("clicked"):
            continue
        time.sleep(4)
        if label == "Sign in with email":
            return True
        inspect_res = get(f"{HOST_WORKER_URL}/sessions/{session_id}/inspect")
        inspection = inspect_res.get("inspection", {})
        if inspection.get("inputs"):
            return True
    return False

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 ats_apply.py <job_url> [security_code]")
        sys.exit(1)

    url = sys.argv[1]
    security_code = sys.argv[2] if len(sys.argv) > 2 else None
    
    # 1. Read Profile
    profile_path = os.path.join(os.path.dirname(__file__), "..", "profile.json")
    if not os.path.exists(profile_path):
        print(f"Error: Profile not found at {profile_path}. Please ask the user for their profile details and save it to workspace/profile.json")
        sys.exit(1)
        
    with open(profile_path, "r") as f:
        profile = json.load(f)

    # 2. Check for resume
    resume_path = os.path.join(os.path.dirname(__file__), "..", "resume.pdf")
    if not os.path.exists(resume_path):
        resume_path = None

    print(f"Starting application for: {url}")
    
    # 3. Create Session
    session_res = post(f"{HOST_WORKER_URL}/sessions", {
        "application_id": f"openclaw-{int(time.time())}",
        "url": url,
        "profile_id": profile.get("email", "unknown")
    })
    session_id = session_res["session"]["application_id"]
    print(f"Session created: {session_id}")

    # Give the browser a few seconds to load the ATS page
    time.sleep(5)

    maybe_advance_application(session_id)

    inspect_res = get(f"{HOST_WORKER_URL}/sessions/{session_id}/inspect")
    print("Post-advance inspection:", json.dumps(inspect_res.get("inspection", {}), indent=2))
    html_res = post(
        f"{HOST_WORKER_URL}/sessions/{session_id}/evaluate",
        {
            "script": "(() => ({ html: document.documentElement.outerHTML.slice(0, 5000), iframeCount: document.querySelectorAll('iframe').length, frameCount: window.frames.length, iframeSrcs: Array.from(document.querySelectorAll('iframe')).map(f => f.getAttribute('src') || '') }))()",
        },
    )
    print("Post-advance HTML probe:", json.dumps(html_res.get("result", {}), indent=2))

    # 4. Fill Application
    print("Filling application...")
    fill_res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/fill", {
        "profile": profile,
        "resume_path": resume_path
    })
    
    print("Fill result payload:", json.dumps(fill_res, indent=2))
    status = fill_res.get("session", {}).get("status")
    print(f"Fill session status: {status}")
    
    if status == "ready":
        print("Form is filled and ready! Pausing for 5 seconds so you can see it...")
        time.sleep(5)
        print("Submitting...")
        submit_res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/submit")
        print(f"Submit status: {submit_res.get('status')}")
        if security_code:
            print("Entering security code and resubmitting...")
            time.sleep(5)
            verify_res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/verify", {
                "code": security_code
            })
            print("Verify result payload:", json.dumps(verify_res, indent=2))
    else:
        print("Form requires manual attention (missing fields). Please check the browser window!")
        # We don't close the session so the user can see it
        sys.exit(0)

    # 5. Close Session if submitted successfully
    print("Pausing for 60 seconds so you can examine the filled form before the browser closes...")
    time.sleep(60)
    print("Closing session...")
    post(f"{HOST_WORKER_URL}/sessions/{session_id}/close")
    print("Job application completed successfully!")

if __name__ == "__main__":
    main()
