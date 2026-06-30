import pathlib
import sys
import unittest
from datetime import datetime, timezone

SCRIPT_DIR = pathlib.Path(__file__).resolve().parents[1]
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from verify_ats_open_closed import classify_open_closed


CHECKED_AT = datetime(2026, 6, 23, tzinfo=timezone.utc)


def base_job(**overrides):
    job = {
        "job_key": "greenhouse:123",
        "scan_run_id": "00000000-0000-0000-0000-000000000001",
        "content_hash": "a" * 64,
        "source": "greenhouse",
        "company": "Example",
        "title": "Engineer",
        "url": "https://example.test/jobs/123",
        "apply_url": "https://example.test/jobs/123/apply",
        "present_in_scan": True,
        "local_status": "unknown",
        "local_reasons": ["local_quality_checks_passed"],
        "local_signals": {"has_required_fields": True},
        "url_status": "unknown",
        "url_reasons": [],
        "url_signals": {},
        "url_missing_count": 0,
        "url_blocked_count": 0,
        "url_transient_count": 0,
    }
    job.update(overrides)
    return job


class OpenClosedClassificationTests(unittest.TestCase):
    def test_current_reachable_job_is_open(self):
        result = classify_open_closed(
            base_job(
                url_reasons=["job_url_reachable"],
                url_signals={"job_url_reachable": True, "job_url_status_code": 200},
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "open")
        self.assertIn("present_in_selected_scan", result["reasons"])
        self.assertIn("url_reachable", result["reasons"])
        self.assertEqual(result["confidence"], 0.9)
        self.assertFalse(result["signals"]["network_checked"])

    def test_invalid_local_quality_stays_invalid(self):
        result = classify_open_closed(
            base_job(
                local_status="invalid",
                local_reasons=["malformed_job_url"],
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "invalid")
        self.assertIn("invalid_job_data", result["reasons"])
        self.assertIn("malformed_job_url", result["reasons"])

    def test_blocked_url_stays_blocked(self):
        result = classify_open_closed(
            base_job(
                url_status="blocked",
                url_reasons=["job_url_blocked"],
                url_signals={"job_url_blocked": True},
                url_blocked_count=2,
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "blocked")
        self.assertIn("url_access_blocked", result["reasons"])
        self.assertIn("url_blocked_count_2", result["reasons"])

    def test_present_missing_url_is_not_closed(self):
        result = classify_open_closed(
            base_job(
                url_reasons=["job_url_missing"],
                url_signals={"job_url_missing": True, "job_url_status_code": 404},
                url_missing_count=1,
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "unknown")
        self.assertIn("single_or_conflicting_missing_url_not_enough_to_close", result["reasons"])

    def test_absent_repeated_missing_job_is_closed(self):
        result = classify_open_closed(
            base_job(
                present_in_scan=False,
                url_reasons=["job_url_missing"],
                url_signals={"job_url_missing": True, "job_url_status_code": 404},
                url_missing_count=3,
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "closed")
        self.assertIn("absent_from_selected_scan", result["reasons"])
        self.assertIn("repeated_missing_url_count_3", result["reasons"])
        self.assertTrue(result["signals"]["closed_requires_absence_and_repeated_missing"])

    def test_absent_single_missing_job_remains_unknown(self):
        result = classify_open_closed(
            base_job(
                present_in_scan=False,
                url_reasons=["job_url_missing"],
                url_signals={"job_url_missing": True},
                url_missing_count=1,
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "unknown")
        self.assertIn("missing_url_below_close_threshold", result["reasons"])

    def test_transient_failure_remains_unknown(self):
        result = classify_open_closed(
            base_job(
                url_reasons=["job_url_transient_failure"],
                url_signals={"job_url_transient_failure": True},
                url_transient_count=1,
            ),
            checked_at=CHECKED_AT,
        )

        self.assertEqual(result["verification_status"], "unknown")
        self.assertIn("transient_url_failure", result["reasons"])


if __name__ == "__main__":
    unittest.main()
