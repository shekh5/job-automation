#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ats_common import capture_source_evidence, evaluate_relevance, fetch_json
from ats_crawl_policy import DEFAULT_CRAWL_POLICY, deterministic_retry_delay


class CrawlPolicyTests(unittest.TestCase):
    def test_retry_delay_is_deterministic_and_bounded(self):
        first = deterministic_retry_delay("https://example.test/jobs", 0)
        second = deterministic_retry_delay("https://example.test/jobs", 0)
        self.assertEqual(first, second)
        base = DEFAULT_CRAWL_POLICY.retry_delays_seconds[0]
        self.assertGreaterEqual(first, base * (1 - DEFAULT_CRAWL_POLICY.jitter_ratio))
        self.assertLessEqual(first, base * (1 + DEFAULT_CRAWL_POLICY.jitter_ratio))

    def test_rejection_reasons_are_explainable(self):
        result = evaluate_relevance("Senior Sales Director", "New York, USA")
        self.assertEqual(result["decision"], "rejected")
        self.assertIn("missing_role_signal", result["reasons"])
        self.assertIn("seniority_excluded", result["reasons"])

    def test_fetch_retry_records_one_final_success_observation(self):
        class FakeResponse:
            status = 200

            def read(self):
                return b'{"jobs": []}'

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        source = {"company": "Example", "slug": "example"}
        with (
            capture_source_evidence(source, "greenhouse") as evidence,
            patch("ats_common.urllib.request.urlopen", side_effect=[
                urllib.error.URLError("temporary"),
                FakeResponse(),
            ]),
            patch("ats_common.time.sleep") as sleep,
        ):
            result = fetch_json("https://example.test/jobs")

        self.assertEqual(result, {"jobs": []})
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0]["outcome"], "success")
        self.assertEqual(evidence[0]["attempt_count"], 2)
        sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
