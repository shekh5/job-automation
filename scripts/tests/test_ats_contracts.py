#!/usr/bin/env python3

from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
WORKSPACE = SCRIPTS.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
SCHEMAS = WORKSPACE / "data" / "schemas"
sys.path.insert(0, str(SCRIPTS))

import fetch_jobs_ats
from ats_common import PROVIDERS, deduplicate_jobs, is_current, load_source_database, relevant

NOW = datetime(2026, 6, 22, 8, 0, tzinfo=timezone.utc)


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture(provider):
    return load_json(FIXTURES / f"{provider}.json")


class FormalSchemaTests(unittest.TestCase):
    def test_all_json_contracts_parse(self):
        for path in sorted(SCHEMAS.glob("*.schema.json")):
            with self.subTest(path=path.name):
                schema = load_json(path)
                self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
                self.assertEqual(schema["type"], "object")

    def test_golden_jobs_match_canonical_field_contract(self):
        schema = load_json(SCHEMAS / "normalized_job.schema.json")
        required = set(schema["required"])
        properties = set(schema["properties"])
        self.assertEqual(required, properties)
        for provider in PROVIDERS:
            with self.subTest(provider=provider):
                job = load_fixture(provider)["expected_job"]
                self.assertEqual(set(job), required)
                self.assertEqual(job["schema_version"], 1)
                self.assertEqual(job["source"], provider)
                self.assertTrue(job["company"] and job["source_id"] and job["title"])
                self.assertTrue(job["url"] and job["apply_url"])
                self.assertEqual(len(job["locations"]), len(set(item.casefold() for item in job["locations"])))

    def test_source_database_matches_provider_requirements(self):
        sources, errors = load_source_database()
        self.assertEqual(errors, [])
        for source in sources:
            with self.subTest(company=source["company"]):
                self.assertIn(source["provider"], PROVIDERS)
                if source["provider"] in {"greenhouse", "lever"}:
                    self.assertTrue(source.get("slug") or source.get("api_url"))
                elif source["provider"] == "ashby":
                    self.assertTrue(
                        source.get("slug") or source.get("job_board_name")
                        or source.get("api_url") or source.get("career_url")
                    )
                else:
                    self.assertTrue(
                        source.get("api_url") or source.get("career_url")
                        or all(source.get(key) for key in ("host", "tenant", "site"))
                    )


class BaselineBehaviorTests(unittest.TestCase):
    def test_freshness_boundary_and_undated_open_jobs(self):
        self.assertTrue(is_current(NOW - timedelta(days=14), now=NOW))
        self.assertFalse(is_current(NOW - timedelta(days=15), now=NOW))
        self.assertTrue(is_current(None, now=NOW))

    def test_relevance_contract(self):
        self.assertTrue(relevant("Software Engineer Intern", "Bengaluru, India"))
        self.assertFalse(relevant("Senior Software Engineer", "Bengaluru, India"))
        self.assertFalse(relevant("Sales Intern", "Bengaluru, India"))
        self.assertFalse(relevant("Software Engineer Intern", "Remote, United States"))

    def test_deduplication_contract(self):
        first = load_fixture("lever")["expected_job"]
        duplicate = dict(first, description="newer observation")
        other = load_fixture("ashby")["expected_job"]
        result = deduplicate_jobs([first, other, duplicate])
        self.assertEqual(len(result), 2)
        lever = next(job for job in result if job["source"] == "lever")
        self.assertEqual(lever["description"], "newer observation")


class CombinedOutputCompatibilityTests(unittest.TestCase):
    @staticmethod
    def provider_report(provider):
        match = load_fixture(provider)["expected_job"] if provider == "greenhouse" else None
        return {
            "provider": provider,
            "attempted": 1,
            "successful": 1,
            "checked": [{
                "company": f"Example {provider.title()}",
                "source": provider,
                "slug": "example",
                "raw_jobs": 1,
                "recent_jobs": 1,
                "matches": 1 if match else 0,
                "dropped_jobs": 0,
            }],
            "errors": [],
            "source_repairs": [],
            "total_raw_jobs": 1,
            "total_current_jobs": 1,
            "total_dropped_jobs": 0,
            "matches": [match] if match else [],
        }

    def build_report(self):
        sources = [{"company": provider.title(), "provider": provider} for provider in PROVIDERS]

        def fake_scan_provider(provider, scanner, selected_sources):
            self.assertIs(selected_sources, sources)
            return self.provider_report(provider)

        with (
            patch.object(fetch_jobs_ats, "load_source_database", return_value=(sources, [])),
            patch.object(fetch_jobs_ats, "scan_provider", side_effect=fake_scan_provider),
        ):
            return fetch_jobs_ats.scan()

    def test_combined_report_keeps_exact_top_level_contract(self):
        report = self.build_report()
        schema = load_json(SCHEMAS / "ats_scan_report.schema.json")
        self.assertEqual(set(report), set(schema["required"]))
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(set(report["providers"]), set(PROVIDERS))
        self.assertEqual(report["total_raw_jobs"], 4)
        self.assertEqual(report["total_current_jobs"], 4)
        self.assertEqual(report["total_greenhouse_jobs"], 1)
        self.assertEqual(report["total_recent_greenhouse_jobs"], 1)
        self.assertEqual(report["skipped_non_greenhouse"], [])
        self.assertEqual(report["matches"], [load_fixture("greenhouse")["expected_job"]])
        datetime.fromisoformat(report["generated_at"])

    def test_combined_command_writes_compatible_json_and_markdown(self):
        report = self.build_report()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            json_path = root / "job_api_scan_latest.json"
            markdown_path = root / "job_api_scan_latest.md"
            with (
                patch.object(fetch_jobs_ats, "OUT", json_path),
                patch.object(fetch_jobs_ats, "MD_OUT", markdown_path),
                patch.object(fetch_jobs_ats, "scan", return_value=report),
                patch.object(fetch_jobs_ats, "persist_report"),
                redirect_stdout(io.StringIO()),
            ):
                self.assertEqual(fetch_jobs_ats.main(), 0)
            self.assertEqual(load_json(json_path), report)
            markdown = markdown_path.read_text(encoding="utf-8")
            self.assertIn("## Provider Coverage", markdown)
            self.assertIn("## Matches", markdown)
            for provider in PROVIDERS:
                self.assertIn(provider.title(), markdown)


if __name__ == "__main__":
    unittest.main()
