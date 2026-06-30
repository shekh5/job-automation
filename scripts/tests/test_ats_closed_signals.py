import unittest
from datetime import datetime, timezone
import json

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_ats_closed_signals import normalize_page_text, extract_signals, verify_job_signals

class TestATSClosedSignals(unittest.TestCase):
    def test_normalize_page_text(self):
        html = """
        <html>
            <head>
                <style>body { color: red; }</style>
                <script>console.log("hello");</script>
            </head>
            <body>
                <h1>Job Posting</h1>
                <p>This job is NO LONGER available.</p>
            </body>
        </html>
        """
        normalized = normalize_page_text(html)
        self.assertNotIn("console.log", normalized)
        self.assertNotIn("color: red", normalized)
        self.assertNotIn("<h1>", normalized)
        self.assertIn("job posting", normalized)
        self.assertIn("this job is no longer available", normalized)

    def test_generic_closed_phrase(self):
        text = "we are sorry, but this posting has expired and is no longer accepting applications."
        closed, open_phrases = extract_signals(text, "greenhouse")
        self.assertIn("this posting has expired", closed)
        self.assertNotIn("job no longer available", closed)
        self.assertEqual(len(open_phrases), 0)

    def test_generic_open_phrase(self):
        text = "welcome to our careers page. please apply now to join our team!"
        closed, open_phrases = extract_signals(text, "ashby")
        self.assertEqual(len(closed), 0)
        self.assertIn("apply now", open_phrases)

    def test_conflicting_phrases(self):
        text = "this job is no longer available, but you can apply for this job instead."
        closed, open_phrases = extract_signals(text, "lever")
        self.assertTrue(len(closed) > 0)
        self.assertTrue(len(open_phrases) > 0)

    def test_provider_specific_phrases(self):
        # Workday specific
        workday_text = "this job is no longer accepting applications."
        closed, open_phrases = extract_signals(workday_text, "workday")
        self.assertIn("this job is no longer accepting applications", closed)

        # Lever specific open phrase
        lever_text = "apply for this job today."
        closed, open_phrases = extract_signals(lever_text, "lever")
        self.assertIn("apply for this job", open_phrases)

    def test_verify_job_signals_with_evidence(self):
        job = {
            "job_key": "test:123",
            "source": "greenhouse",
            "url": "https://example.com/job/123",
            "raw_evidence": {
                "body": "This job is no longer available."
            }
        }
        result = verify_job_signals(job)
        self.assertIsNotNone(result)
        self.assertEqual(result["verification_status"], "unknown")
        self.assertIn("closed_text_signal_found", result["reasons"])
        self.assertTrue(result["signals"]["closed_text_found"])
        self.assertFalse(result["signals"]["open_text_found"])
        self.assertEqual(result["signals"]["source"], "stored_evidence")

    def test_verify_job_signals_no_evidence(self):
        job = {
            "job_key": "test:456",
            "source": "lever",
            "url": "https://example.com/job/456",
            "raw_evidence": None
        }
        # Without fetch missing, it should return None since there is no evidence
        result = verify_job_signals(job, fetch_missing=False)
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()
