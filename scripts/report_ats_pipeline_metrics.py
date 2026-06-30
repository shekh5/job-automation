#!/usr/bin/env python3
"""Phase 7 Metrics and Reporting

Queries the database to calculate coverage, verification rates,
crawler quality, and operational health. Also evaluates the 
classifier against the ground-truth sample.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from ats_supabase import _load_psycopg, _database_url

logger = logging.getLogger(__name__)

def load_truth_sample() -> list[dict]:
    p = Path(__file__).parent.parent / "data" / "evaluation" / "ats_job_truth_sample.json"
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return []

def generate_report(conn) -> dict[str, Any]:
    report = {
        "status_distribution": {},
        "truth_sample_evaluation": {},
        "top_failing_providers": [],
        "metrics": {}
    }
    
    with conn.cursor() as cur:
        # 1. Status Distribution
        cur.execute("""
            SELECT verification_status, COUNT(*) 
            FROM ats_job_verification_latest 
            GROUP BY verification_status;
        """)
        total_verified = 0
        for row in cur.fetchall():
            status, count = row
            report["status_distribution"][status] = count
            total_verified += count
            
        report["metrics"]["total_verified_jobs"] = total_verified
        
        # 2. Evaluate Truth Sample
        truth_sample = load_truth_sample()
        if truth_sample:
            matches = 0
            mismatches = []
            
            for item in truth_sample:
                job_key = item["job_key"]
                expected = item["expected_status"]
                
                cur.execute("""
                    SELECT verification_status 
                    FROM ats_job_verification_latest 
                    WHERE job_key = %s
                """, (job_key,))
                res = cur.fetchone()
                
                actual = res[0] if res else "unverified"
                
                if actual == expected:
                    matches += 1
                else:
                    mismatches.append({
                        "job_key": job_key,
                        "expected": expected,
                        "actual": actual
                    })
                    
            report["truth_sample_evaluation"] = {
                "total_samples": len(truth_sample),
                "matches": matches,
                "accuracy_rate": round(matches / len(truth_sample), 2),
                "mismatches": mismatches
            }

        # 3. Top Blocking Providers (Providers causing 'blocked' or 'invalid')
        cur.execute("""
            SELECT j.provider, v.verification_status, COUNT(*) as c
            FROM ats_jobs j
            JOIN ats_job_verification_latest v ON j.job_key = v.job_key
            WHERE v.verification_status IN ('blocked', 'invalid')
            GROUP BY j.provider, v.verification_status
            ORDER BY c DESC
            LIMIT 5;
        """)
        for row in cur.fetchall():
            provider, status, count = row
            report["top_failing_providers"].append({
                "provider": provider,
                "status": status,
                "count": count
            })
            
    return report

def generate_markdown(report: dict[str, Any]) -> str:
    md = [
        "# ATS Pipeline Metrics Report\n",
        "## Overall Pipeline Health\n",
        f"- **Total Verified Jobs:** {report.get('metrics', {}).get('total_verified_jobs', 0)}",
    ]
    
    md.append("\n### Status Distribution")
    for status, count in report.get("status_distribution", {}).items():
        md.append(f"- **{status.upper()}:** {count}")
        
    truth = report.get("truth_sample_evaluation")
    if truth:
        md.append("\n## Ground-Truth Accuracy")
        md.append(f"- **Accuracy Rate:** {truth.get('accuracy_rate', 0) * 100}%")
        md.append(f"- **Matches:** {truth.get('matches')} out of {truth.get('total_samples')}")
        
        if truth.get("mismatches"):
            md.append("\n### Mismatches requiring manual review:")
            for m in truth.get("mismatches"):
                md.append(f"- `{m['job_key']}` expected **{m['expected']}** but was **{m['actual']}**")

    fails = report.get("top_failing_providers")
    if fails:
        md.append("\n## Top Failing Providers")
        for f in fails:
            md.append(f"- **{f['provider']}** had {f['count']} jobs marked as `{f['status']}`")
            
    return "\n".join(md)

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--out", help="File to save the report to")
    args = parser.parse_args()

    if not _database_url():
        logger.error("ATS_DATABASE_URL not set")
        return 1

    try:
        psycopg = _load_psycopg()
        conn = psycopg.connect(_database_url())
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return 1

    with conn:
        report = generate_report(conn)

    if args.format == "json":
        output_str = json.dumps(report, indent=2)
    else:
        output_str = generate_markdown(report)

    if args.out:
        Path(args.out).write_text(output_str, encoding="utf-8")
        logger.info(f"Report saved to {args.out}")
    else:
        print(output_str)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
