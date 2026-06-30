#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from verify_ats_urls import check_url_reachability, verify_job_urls


def sample_job(**overrides):
    job = {
        "scan_run_id": "11111111-1111-1111-1111-111111111111",
        "job_key": "lever:123",
        "content_hash": "a" * 64,
        "company": "Example",
        "source": "lever",
        "source_id": "123",
        "title": "Software Engineer Intern",
        "location": "Bengaluru, India",
        "url": "https://example.test/jobs/123",
        "apply_url": "https://example.test/jobs/123/apply",
    }
    job.update(overrides)
    return job


class FakeResponse:
    def __init__(self, status=200, url="https://example.test/final"):
        self.status = status
        self.url = url

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class UrlReachabilityTests(unittest.TestCase):
    def test_malformed_url_is_invalid_without_network(self):
        with patch("verify_ats_urls.urllib.request.urlopen") as urlopen:
            result = check_url_reachability("not-a-url")

        self.assertEqual(result["category"], "invalid")
        self.assertEqual(result["error"], "malformed_url")
        urlopen.assert_not_called()

    def test_200_response_is_reachable(self):
        with patch("verify_ats_urls.urllib.request.urlopen", return_value=FakeResponse(200)):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(result["category"], "reachable")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(result["final_url"], "https://example.test/final")

    def test_redirect_final_url_is_recorded(self):
        with patch(
            "verify_ats_urls.urllib.request.urlopen",
            return_value=FakeResponse(200, "https://jobs.example.test/final"),
        ):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(result["category"], "reachable")
        self.assertEqual(result["final_url"], "https://jobs.example.test/final")

    def test_404_response_is_missing_not_closed(self):
        error = urllib.error.HTTPError("https://example.test/jobs/123", 404, "Not Found", {}, None)
        with patch("verify_ats_urls.urllib.request.urlopen", side_effect=error):
            result = verify_job_urls(sample_job())

        self.assertEqual(result["verification_status"], "unknown")
        self.assertIn("job_url_missing", result["reasons"])
        self.assertIn("apply_url_missing", result["reasons"])
        self.assertTrue(result["signals"]["job_url_missing"])

    def test_410_response_is_missing_not_closed(self):
        error = urllib.error.HTTPError("https://example.test/jobs/123", 410, "Gone", {}, None)
        with patch("verify_ats_urls.urllib.request.urlopen", side_effect=error):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(result["category"], "missing")
        self.assertEqual(result["status_code"], 410)

    def test_403_response_is_blocked(self):
        error = urllib.error.HTTPError("https://example.test/jobs/123", 403, "Forbidden", {}, None)
        with patch("verify_ats_urls.urllib.request.urlopen", side_effect=error):
            result = verify_job_urls(sample_job())

        self.assertEqual(result["verification_status"], "blocked")
        self.assertIn("job_url_blocked", result["reasons"])
        self.assertTrue(result["signals"]["blocked"])

    def test_429_response_is_blocked(self):
        error = urllib.error.HTTPError("https://example.test/jobs/123", 429, "Too Many Requests", {}, None)
        with patch("verify_ats_urls.urllib.request.urlopen", side_effect=error):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(result["category"], "blocked")
        self.assertEqual(result["status_code"], 429)

    def test_500_response_is_transient_unknown_after_retries(self):
        error = urllib.error.HTTPError("https://example.test/jobs/123", 500, "Server Error", {}, None)
        with (
            patch("verify_ats_urls.urllib.request.urlopen", side_effect=error),
            patch("verify_ats_urls.time.sleep") as sleep,
        ):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(result["category"], "transient_failure")
        self.assertEqual(result["status_code"], 500)
        self.assertEqual(result["attempt_count"], 4)
        self.assertEqual(sleep.call_count, 3)

    def test_timeout_is_transient_unknown_after_retries(self):
        with (
            patch("verify_ats_urls.urllib.request.urlopen", side_effect=TimeoutError("timed out")),
            patch("verify_ats_urls.time.sleep") as sleep,
        ):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(result["category"], "transient_failure")
        self.assertEqual(result["attempt_count"], 4)
        self.assertEqual(sleep.call_count, 3)

    def test_head_fallback_to_get_works(self):
        methods = []

        def fake_urlopen(request, timeout):
            methods.append(request.get_method())
            if request.get_method() == "HEAD":
                raise urllib.error.HTTPError(request.full_url, 405, "Method Not Allowed", {}, None)
            return FakeResponse(200)

        with patch("verify_ats_urls.urllib.request.urlopen", side_effect=fake_urlopen):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertEqual(methods, ["HEAD", "GET"])
        self.assertTrue(result["fallback_used"])
        self.assertEqual(result["category"], "reachable")

    def test_error_text_is_bounded(self):
        with (
            patch("verify_ats_urls.urllib.request.urlopen", side_effect=TimeoutError("x" * 1000)),
            patch("verify_ats_urls.time.sleep"),
        ):
            result = check_url_reachability("https://example.test/jobs/123")

        self.assertLessEqual(len(result["error"]), 400)


if __name__ == "__main__":
    unittest.main()
