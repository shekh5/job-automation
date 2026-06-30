import sys
import os
import urllib.request
import json

HOST_WORKER_URL = os.environ.get("HOST_WORKER_URL", "http://host.docker.internal:4555")

def post(url):
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Error {e.code} on {url}: {e.read().decode()}")
        sys.exit(1)
    except Exception as e:
        print(f"Failed to submit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ats_submit.py <session_id>")
        sys.exit(1)
    
    session_id = sys.argv[1]
    print(f"Submitting session {session_id}...")
    res = post(f"{HOST_WORKER_URL}/sessions/{session_id}/submit")
    print(f"Submit command sent: {res}")
    
    print("Closing session...")
    post(f"{HOST_WORKER_URL}/sessions/{session_id}/close")
    print("Session closed successfully.")
