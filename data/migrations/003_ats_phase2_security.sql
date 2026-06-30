alter view ats_job_evidence_dashboard set (security_invoker = true);
alter view ats_fetch_evidence_dashboard set (security_invoker = true);

revoke all on table ats_schema_migrations from anon, authenticated;
revoke all on table ats_scan_runs from anon, authenticated;
revoke all on table ats_jobs from anon, authenticated;
revoke all on table ats_run_jobs from anon, authenticated;
revoke all on table ats_fetch_payloads from anon, authenticated;
revoke all on table ats_fetch_observations from anon, authenticated;
revoke all on table ats_job_versions from anon, authenticated;
revoke all on table ats_job_evaluations from anon, authenticated;
revoke all on table ats_job_evidence_dashboard from anon, authenticated;
revoke all on table ats_fetch_evidence_dashboard from anon, authenticated;
revoke all on function ats_cleanup_evidence(interval) from anon, authenticated;
