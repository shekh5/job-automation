#!/usr/bin/env python3

from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ats_common import PROVIDERS, infer_provider, load_source_database, normalized_job, parse_datetime
from fetch_jobs_ashby import normalize_job as normalize_ashby
from fetch_jobs_greenhouse import normalize_job as normalize_greenhouse
from fetch_jobs_greenhouse import scan_source as scan_greenhouse_source
from fetch_jobs_lever import normalize_job as normalize_lever
from fetch_jobs_workday import normalize_job as normalize_workday
from fetch_jobs_workday import prepare_source as prepare_workday_source

NOW = datetime(2026, 6, 22, 8, 0, tzinfo=timezone.utc)
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NORMALIZERS = {
    "greenhouse": normalize_greenhouse,
    "lever": normalize_lever,
    "ashby": normalize_ashby,
    "workday": normalize_workday,
}


def load_fixture(provider):
    return json.loads((FIXTURES / f"{provider}.json").read_text(encoding="utf-8"))


class CommonSchemaTests(unittest.TestCase):
    def test_source_database_covers_all_supported_providers(self):
        sources, errors = load_source_database()
        self.assertEqual(errors, [])
        self.assertEqual(set(PROVIDERS), {source["provider"] for source in sources})

    def test_missing_source_id_is_repaired_deterministically(self):
        values = dict(
            provider="lever", source={"company": "Example"}, source_id="",
            title="Software Engineer Intern", locations=["Bengaluru, India"],
            url="https://example.test/jobs/1",
        )
        first = normalized_job(**values)
        second = normalized_job(**values)
        self.assertEqual(first["source_id"], second["source_id"])
        self.assertEqual(first["schema_version"], 1)

    def test_workday_relative_date_is_normalized(self):
        self.assertEqual(
            parse_datetime("Posted 2 Days Ago", now=NOW),
            datetime(2026, 6, 20, 8, 0, tzinfo=timezone.utc),
        )

    def test_url_corrects_mislabeled_provider(self):
        self.assertEqual(
            infer_provider({
                "provider": "greenhouse",
                "api_url": "https://api.ashbyhq.com/posting-api/job-board/example",
            }),
            "ashby",
        )


class ProviderNormalizationTests(unittest.TestCase):
    def assert_golden_fixture(self, provider):
        fixture = load_fixture(provider)
        now = datetime.fromisoformat(fixture["now"])
        actual = NORMALIZERS[provider](
            fixture["raw_payload"], fixture["source"], now=now,
        )
        self.assertEqual(actual, fixture["expected_job"])

    def test_greenhouse_payload(self):
        self.assert_golden_fixture("greenhouse")

    def test_current_jobs_are_retained_before_relevance_filtering(self):
        fixture = load_fixture("greenhouse")
        raw_job = dict(fixture["raw_payload"], title="Senior Sales Director")
        with patch("fetch_jobs_greenhouse.fetch_json", return_value={"jobs": [raw_job]}):
            result = scan_greenhouse_source(fixture["source"])
        self.assertEqual(result.jobs, [])
        self.assertEqual(len(result.current_jobs), 1)
        self.assertEqual(result.current_jobs[0]["title"], "Senior Sales Director")
        self.assertEqual(len(result.job_evidence), 1)
        self.assertEqual(result.job_evidence[0]["raw_job"]["title"], "Senior Sales Director")

    def test_lever_payload(self):
        self.assert_golden_fixture("lever")

    def test_ashby_payload(self):
        self.assert_golden_fixture("ashby")

    def test_workday_payload(self):
        self.assert_golden_fixture("workday")

    def test_workday_source_and_payload(self):
        source, repairs = prepare_workday_source({
            "company": "NVIDIA",
            "provider": "workday",
            "career_url": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite",
        })
        self.assertEqual(source["tenant"], "nvidia")
        self.assertEqual(source["site"], "NVIDIAExternalCareerSite")
        self.assertIn("api_url generated", " ".join(repairs))
        job = normalize_workday(
            load_fixture("workday")["raw_payload"], source, now=NOW,
        )
        self.assertEqual(job["source_id"], "/job/Bengaluru-India/R123")
        self.assertEqual(job["first_published"], "2026-06-20T08:00:00+00:00")
        self.assertEqual(
            job["url"],
            "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite/job/Bengaluru-India/R123",
        )


if __name__ == "__main__":
    unittest.main()
