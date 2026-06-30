#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import ats_supabase
from verify_ats_jobs import valid_http_url, verify_job_locally, verify_jobs_locally


CHECKED_AT = datetime(2026, 6, 23, tzinfo=timezone.utc)


def sample_job(**overrides):
    job = {
        "schema_version": 1,
        "scan_run_id": "11111111-1111-1111-1111-111111111111",
        "job_key": "lever:123",
        "content_hash": "a" * 64,
        "company": "Example",
        "source": "lever",
        "source_id": "123",
        "title": "Software Engineer Intern",
        "location": "Bengaluru, India",
        "locations": ["Bengaluru, India"],
        "department": "",
        "team": "",
        "employment_type": "",
        "workplace_type": "",
        "description": "Intern role",
        "updated_at": "2026-06-22T08:00:00+00:00",
        "first_published": "2026-06-20T08:00:00+00:00",
        "freshness_days": 14,
        "url": "https://example.test/jobs/123",
        "apply_url": "https://example.test/jobs/123",
    }
    job.update(overrides)
    return job


class LocalJobVerificationTests(unittest.TestCase):
    def test_valid_http_url_requires_http_scheme_and_host(self):
        self.assertTrue(valid_http_url("https://example.test/jobs/123"))
        self.assertFalse(valid_http_url("javascript:alert(1)"))
        self.assertFalse(valid_http_url("https://example test/jobs/123"))
        self.assertFalse(valid_http_url("/jobs/123"))

    def test_valid_job_is_unknown_until_network_verification(self):
        result = verify_job_locally(sample_job(), checked_at=CHECKED_AT)
        self.assertEqual(result["verification_status"], "unknown")
        self.assertEqual(result["reasons"], ["local_quality_checks_passed"])
        self.assertFalse(result["signals"]["network_checked"])

    def test_malformed_job_is_invalid(self):
        result = verify_job_locally(
            sample_job(title="", url="not-a-url", apply_url=""),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result["verification_status"], "invalid")
        self.assertIn("missing_title", result["reasons"])
        self.assertIn("malformed_job_url", result["reasons"])
        self.assertIn("malformed_apply_url", result["reasons"])

    def test_stale_date_is_a_quality_warning_not_closed(self):
        result = verify_job_locally(
            sample_job(updated_at="2025-01-01T00:00:00+00:00", first_published="2025-01-01T00:00:00+00:00"),
            checked_at=CHECKED_AT,
        )
        self.assertEqual(result["verification_status"], "unknown")
        self.assertIn("stale_date_signal", result["reasons"])
        self.assertTrue(result["signals"]["stale_date_signal"])

    def test_duplicate_posting_is_detected_without_marking_invalid(self):
        first = sample_job(source_id="123", job_key="lever:123")
        second = sample_job(source_id="456", job_key="lever:456")
        results = verify_jobs_locally([first, second], checked_at=CHECKED_AT)
        self.assertEqual([item["verification_status"] for item in results], ["unknown", "unknown"])
        self.assertTrue(all("duplicate_company_title_apply_url" in item["reasons"] for item in results))

    def test_persists_local_verification_results(self):
        queries = []

        class FakeCursor:
            def execute(self, sql, params=None):
                queries.append(("execute", sql.strip(), params))
                if "returning id" in sql.lower():
                    self._result = [("22222222-2222-2222-2222-222222222222",)]

            def executemany(self, sql, params_seq):
                queries.append(("executemany", sql.strip(), list(params_seq)))

            def fetchone(self):
                return self._result.pop(0)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConn:
            def cursor(self):
                return FakeCursor()

            def commit(self):
                self.committed = True

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakePsycopg:
            def connect(self, url):
                self.url = url
                return FakeConn()

        verification = verify_job_locally(sample_job(), checked_at=CHECKED_AT)
        with (
            patch.object(ats_supabase, "_load_psycopg", return_value=FakePsycopg()),
            patch.object(ats_supabase, "_database_url", return_value="postgresql://example"),
            patch.object(ats_supabase, "_ensure_schema", return_value=None),
        ):
            result = ats_supabase.persist_verification_results(
                [verification],
                scan_run_id=verification["scan_run_id"],
                verification_kind="local_quality",
            )

        self.assertEqual(result.status, "persisted")
        self.assertEqual(result.verifications_inserted, 1)
        self.assertTrue(any("ats_verification_runs" in query[1] for query in queries))
        self.assertTrue(any("ats_job_verifications" in query[1] for query in queries))


if __name__ == "__main__":
    unittest.main()
