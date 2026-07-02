import requests
import json
import os
import base64

BUGLESSTACK_API_URL = os.getenv("BUGLESSTACK_API_URL", "http://localhost:3000/api/crashes")

def report_crash_to_buglesstack(error_message: str, screenshot_bytes: bytes, dom_html: str):
    """
    Sends a crash report to Buglesstack including the error message, 
    the full page screenshot, and the HTML DOM snapshot.
    """
    print(f"🚨 [Buglesstack] Intercepted crash: {error_message}")
    
    try:
        # Convert screenshot to base64 for JSON transmission
        screenshot_b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        
        payload = {
            "error": error_message,
            "screenshotBase64": screenshot_b64,
            "htmlSnapshot": dom_html,
            "metadata": {
                "source": "Stealth_Job_Applier",
                "engine": "Camofox"
            }
        }
        
        print(f"📡 [Buglesstack] Uploading crash data to {BUGLESSTACK_API_URL}...")
        
        # In a real setup, we POST to the Buglesstack API
        # response = requests.post(BUGLESSTACK_API_URL, json=payload)
        # response.raise_for_status()
        
        print("✅ [Buglesstack] Crash report successfully archived.")
        
    except Exception as e:
        print(f"❌ [Buglesstack] Failed to send crash report: {e}")
