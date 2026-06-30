#!/usr/bin/env python3

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

import ats_supabase


class SupabasePersistenceTests(unittest.TestCase):
    def sample_report(self):
        return {
            "schema_version": 2,
            "generated_at": "2026-06-22T08:00:00+00:00",
            "freshness_days": 14,
            "strategy": "Direct public ATS APIs with provider-specific adapters: Greenhouse, Lever, Ashby, and Workday.",
            "total_raw_jobs": 1,
            "total_current_jobs": 1,
            "total_dropped_jobs": 0,
            "provider_counts": {},
            "checked": [],
            "errors": [],
            "source_repairs": [],
            "matches": [{
                "schema_version": 1,
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
                "updated_at": "",
                "first_published": "",
                "freshness_days": 14,
                "url": "https://example.test/jobs/123",
                "apply_url": "https://example.test/jobs/123",
            }],
        }

    def test_placeholder_url_is_not_used(self):
        self.assertIsNone(
            ats_supabase._database_url({
                "SUPABASE_DATABASE_URL": "postgresql://postgres:[YOUR-PASSWORD]@x:5432/postgres"
            })
        )

    def test_direct_url_can_route_through_session_pooler(self):
        result = ats_supabase._database_url({
            "SUPABASE_DATABASE_URL": "postgresql://postgres:secret@db.exampleproject.supabase.co:5432/postgres",
            "SUPABASE_POOLER_HOST": "aws-1-ap-northeast-1.pooler.supabase.com",
        })
        self.assertEqual(
            result,
            "postgresql://postgres.exampleproject:secret@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres?sslmode=require",
        )

    def test_pooler_host_rejects_non_hostname_values(self):
        with self.assertRaises(ValueError):
            ats_supabase._database_url({
                "SUPABASE_DATABASE_URL": "postgresql://postgres:secret@db.exampleproject.supabase.co:5432/postgres",
                "SUPABASE_POOLER_HOST": "https://invalid.example",
            })

    def test_skips_without_driver_or_database_url(self):
        result = ats_supabase.persist_report(self.sample_report(), env={})
        self.assertEqual(result.status, "skipped")

    def test_builds_job_key_deterministically(self):
        job = self.sample_report()["matches"][0]
        self.assertEqual(ats_supabase._job_key(job), "lever:123")

    def test_content_hash_is_order_independent(self):
        self.assertEqual(
            ats_supabase._content_hash({"a": 1, "b": 2}),
            ats_supabase._content_hash({"b": 2, "a": 1}),
        )

    def test_phase3a_migration_defines_verification_schema(self):
        sql = (ats_supabase.MIGRATIONS_DIR / "004_ats_phase3a_verification_schema.sql").read_text(
            encoding="utf-8"
        )
        required_fragments = [
            "create table if not exists ats_verification_runs",
            "create table if not exists ats_job_verifications",
            "verification_status in ('open', 'closed', 'unknown', 'invalid', 'blocked')",
            "create or replace view ats_job_verification_latest",
            "create or replace view ats_job_verification_dashboard",
            "alter view ats_job_verification_latest set (security_invoker = true)",
            "alter table ats_verification_runs enable row level security",
            "revoke all on table ats_job_verifications from anon, authenticated",
        ]
        for fragment in required_fragments:
            self.assertIn(fragment, sql)

    def test_ensure_schema_applies_phase3a_migration_in_order(self):
        applied_versions = []
        executed_migrations = []

        class FakeCursor:
            def execute(self, sql, params=None):
                stripped = sql.strip()
                if "select 1 from ats_schema_migrations" in stripped:
                    self._result = None
                elif "insert into ats_schema_migrations" in stripped:
                    applied_versions.append(params[0])
                elif "create table if not exists ats_schema_migrations" in stripped:
                    self._result = None
                else:
                    executed_migrations.append(stripped)
                    self._result = None

            def fetchone(self):
                return self._result

        ats_supabase._ensure_schema(FakeCursor())

        self.assertIn("004_ats_phase3a_verification_schema.sql", applied_versions)
        self.assertEqual(applied_versions, sorted(applied_versions))
        self.assertTrue(
            any("ats_verification_runs" in sql for sql in executed_migrations),
            "Phase 3A migration SQL was not executed",
        )

    def test_persists_run_and_jobs_with_driver(self):
        report = self.sample_report()
        job = report["matches"][0]
        queries = []

        class FakeCursor:
            def execute(self, sql, params=None):
                queries.append(("execute", sql.strip(), params))
                if "returning id" in sql.lower():
                    self._result = [("11111111-1111-1111-1111-111111111111",)]

            def executemany(self, sql, params_seq):
                queries.append(("executemany", sql.strip(), list(params_seq)))

            def fetchone(self):
                return self._result.pop(0)

            def fetchall(self):
                return []

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        class FakeConn:
            def __init__(self):
                self.committed = False

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

        fake_psycopg = FakePsycopg()

        with (
            patch.object(ats_supabase, "_load_psycopg", return_value=fake_psycopg),
            patch.object(ats_supabase, "_database_url", return_value="postgresql://example"),
            patch.object(ats_supabase, "_ensure_schema", return_value=None),
        ):
            result = ats_supabase.persist_report(report, [job], scan_kind="combined")

        self.assertEqual(result.status, "persisted")
        self.assertEqual(result.jobs_upserted, 1)
        self.assertEqual(result.run_jobs_upserted, 1)
        self.assertTrue(any(kind == "execute" for kind, *_ in queries))
        self.assertTrue(any(kind == "executemany" for kind, *_ in queries))


if __name__ == "__main__":
    unittest.main()
