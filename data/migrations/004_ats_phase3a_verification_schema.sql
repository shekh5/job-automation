create table if not exists ats_verification_runs (
  id uuid primary key default gen_random_uuid(),
  scan_run_id uuid references ats_scan_runs(id) on delete set null,
  verification_kind text not null default 'job',
  schema_version integer not null default 1,
  status text not null default 'started'
    check (status in ('started', 'completed', 'failed')),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  total_jobs integer not null default 0 check (total_jobs >= 0),
  status_counts jsonb not null default '{}'::jsonb,
  config jsonb not null default '{}'::jsonb,
  errors jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ats_verification_runs_scan_run_id_idx
  on ats_verification_runs(scan_run_id);

create index if not exists ats_verification_runs_started_at_idx
  on ats_verification_runs(started_at desc);

create table if not exists ats_job_verifications (
  verification_run_id uuid not null references ats_verification_runs(id) on delete cascade,
  job_key text not null references ats_jobs(job_key) on delete cascade,
  scan_run_id uuid references ats_scan_runs(id) on delete set null,
  content_hash text check (content_hash is null or length(content_hash) = 64),
  verification_status text not null
    check (verification_status in ('open', 'closed', 'unknown', 'invalid', 'blocked')),
  confidence numeric(5,4) not null default 0
    check (confidence >= 0 and confidence <= 1),
  reasons jsonb not null default '[]'::jsonb,
  signals jsonb not null default '{}'::jsonb,
  evidence jsonb not null default '{}'::jsonb,
  url text not null default '',
  apply_url text not null default '',
  url_status_code integer not null default 0 check (url_status_code >= 0),
  apply_url_status_code integer not null default 0 check (apply_url_status_code >= 0),
  final_url text not null default '',
  final_apply_url text not null default '',
  error text not null default '',
  checked_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  primary key (verification_run_id, job_key)
);

create index if not exists ats_job_verifications_job_key_checked_at_idx
  on ats_job_verifications(job_key, checked_at desc);

create index if not exists ats_job_verifications_status_checked_at_idx
  on ats_job_verifications(verification_status, checked_at desc);

create index if not exists ats_job_verifications_content_hash_idx
  on ats_job_verifications(content_hash)
  where content_hash is not null;

create or replace view ats_job_verification_latest as
select distinct on (jv.job_key)
  jv.verification_run_id,
  vr.scan_run_id as verification_scan_run_id,
  jv.scan_run_id as job_scan_run_id,
  vr.started_at as verification_run_started_at,
  vr.completed_at as verification_run_completed_at,
  jv.checked_at,
  jv.job_key,
  j.provider,
  j.source_id,
  j.company,
  j.title,
  j.location,
  j.url,
  j.apply_url,
  jv.content_hash,
  jv.verification_status,
  jv.confidence,
  jv.reasons,
  jv.signals,
  jv.url_status_code,
  jv.apply_url_status_code,
  jv.final_url,
  jv.final_apply_url,
  jv.error
from ats_job_verifications jv
join ats_verification_runs vr on vr.id = jv.verification_run_id
join ats_jobs j on j.job_key = jv.job_key
order by jv.job_key, jv.checked_at desc, vr.started_at desc;

create or replace view ats_job_verification_dashboard as
select
  jv.verification_run_id,
  vr.scan_run_id as verification_scan_run_id,
  jv.scan_run_id as job_scan_run_id,
  vr.verification_kind,
  vr.status as run_status,
  vr.started_at as run_started_at,
  vr.completed_at as run_completed_at,
  jv.checked_at,
  jv.job_key,
  j.provider,
  j.source_id,
  j.company,
  j.title,
  j.location,
  j.url,
  j.apply_url,
  jv.content_hash,
  jv.verification_status,
  jv.confidence,
  jv.reasons,
  jv.signals,
  jv.url_status_code,
  jv.apply_url_status_code,
  jv.final_url,
  jv.final_apply_url,
  jv.error
from ats_job_verifications jv
join ats_verification_runs vr on vr.id = jv.verification_run_id
join ats_jobs j on j.job_key = jv.job_key;

alter view ats_job_verification_latest set (security_invoker = true);
alter view ats_job_verification_dashboard set (security_invoker = true);

alter table ats_verification_runs enable row level security;
alter table ats_job_verifications enable row level security;

revoke all on table ats_verification_runs from anon, authenticated;
revoke all on table ats_job_verifications from anon, authenticated;
revoke all on table ats_job_verification_latest from anon, authenticated;
revoke all on table ats_job_verification_dashboard from anon, authenticated;
