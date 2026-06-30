create extension if not exists pgcrypto;

create table if not exists ats_scan_runs (
  id uuid primary key default gen_random_uuid(),
  scan_kind text not null,
  schema_version integer not null,
  generated_at timestamptz not null,
  persisted_at timestamptz not null default now(),
  freshness_days integer not null,
  strategy text not null,
  total_raw_jobs integer not null,
  total_current_jobs integer not null,
  total_dropped_jobs integer not null default 0,
  match_count integer not null default 0,
  provider_counts jsonb not null default '{}'::jsonb,
  checked_sources jsonb not null default '[]'::jsonb,
  errors jsonb not null default '[]'::jsonb,
  source_repairs jsonb not null default '[]'::jsonb,
  report jsonb not null
);

create table if not exists ats_jobs (
  job_key text primary key,
  provider text not null,
  source_id text not null,
  company text not null,
  title text not null,
  location text not null,
  locations text[] not null default '{}'::text[],
  department text not null default '',
  team text not null default '',
  employment_type text not null default '',
  workplace_type text not null default '',
  description text not null default '',
  url text not null,
  apply_url text not null,
  freshness_days integer not null,
  updated_at timestamptz,
  first_published timestamptz,
  raw_job jsonb not null,
  first_seen_run_id uuid references ats_scan_runs(id) on delete set null,
  last_seen_run_id uuid references ats_scan_runs(id) on delete set null,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  updated_at_db timestamptz not null default now()
);

create unique index if not exists ats_jobs_provider_source_id_key
  on ats_jobs(provider, source_id);

create index if not exists ats_jobs_company_title_idx
  on ats_jobs(company, title);

create index if not exists ats_jobs_last_seen_at_idx
  on ats_jobs(last_seen_at desc);

create table if not exists ats_run_jobs (
  run_id uuid not null references ats_scan_runs(id) on delete cascade,
  job_key text not null references ats_jobs(job_key) on delete cascade,
  provider text not null,
  company text not null,
  title text not null,
  url text not null,
  job_snapshot jsonb not null,
  seen_at timestamptz not null default now(),
  primary key (run_id, job_key)
);

create index if not exists ats_run_jobs_job_key_idx
  on ats_run_jobs(job_key);
