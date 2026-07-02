import sys
import os
import pytest

# Add parent directory to path so we can import src module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.buglesstack_reporter import report_crash_to_buglesstack

def test_report_crash_to_buglesstack_success(capsys):
    error_msg = "Test Crash Error"
    screenshot = b"dummy_screenshot_bytes"
    html_dom = "<html><body>Dummy Error Page</body></html>"
    
    # Invoke the function
    report_crash_to_buglesstack(error_msg, screenshot, html_dom)
    
    # Capture standard output
    captured = capsys.readouterr()
    
    # Assert expected output was printed
    assert f"🚨 [Buglesstack] Intercepted crash: {error_msg}" in captured.out
    assert "📡 [Buglesstack] Uploading crash data to" in captured.out
    assert "✅ [Buglesstack] Crash report successfully archived." in captured.out
