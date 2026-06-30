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
