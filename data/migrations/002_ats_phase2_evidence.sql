create table if not exists ats_fetch_payloads (
  evidence_hash text primary key check (length(evidence_hash) = 64),
  method text not null,
  url text not null,
  request_payload jsonb,
  response_payload jsonb not null,
  status_code integer not null,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '90 days')
);

alter table ats_scan_runs
  add column if not exists crawl_policy jsonb not null default '{}'::jsonb;

create table if not exists ats_fetch_observations (
  id bigint generated always as identity primary key,
  run_id uuid not null references ats_scan_runs(id) on delete cascade,
  evidence_hash text references ats_fetch_payloads(evidence_hash) on delete set null,
  company text not null,
  provider text not null,
  source_slug text not null default '',
  url text not null default '',
  method text not null default '',
  fetched_at timestamptz not null,
  outcome text not null check (outcome in ('success', 'error')),
  status_code integer not null default 0,
  attempt_count integer not null default 0,
  elapsed_ms integer not null default 0,
  error text not null default '',
  observed_at timestamptz not null default now()
);

create index if not exists ats_fetch_observations_run_id_idx
  on ats_fetch_observations(run_id);

create index if not exists ats_fetch_observations_provider_company_idx
  on ats_fetch_observations(provider, company, observed_at desc);

create table if not exists ats_job_versions (
  job_key text not null references ats_jobs(job_key) on delete cascade,
  content_hash text not null check (length(content_hash) = 64),
  normalized_job jsonb not null,
  raw_job jsonb not null,
  first_seen_run_id uuid references ats_scan_runs(id) on delete set null,
  last_seen_run_id uuid references ats_scan_runs(id) on delete set null,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  expires_at timestamptz not null default (now() + interval '90 days'),
  primary key (job_key, content_hash)
);

create index if not exists ats_job_versions_last_seen_at_idx
  on ats_job_versions(last_seen_at desc);

alter table ats_jobs
  add column if not exists current_content_hash text;

alter table ats_run_jobs
  add column if not exists content_hash text;

alter table ats_run_jobs
  add column if not exists observation_status text;

alter table ats_run_jobs
  alter column job_snapshot drop not null;

insert into ats_job_versions (
  job_key, content_hash, normalized_job, raw_job,
  first_seen_run_id, last_seen_run_id, first_seen_at, last_seen_at, expires_at
)
select
  rj.job_key,
  encode(digest(rj.job_snapshot::text, 'sha256'), 'hex'),
  rj.job_snapshot,
  rj.job_snapshot,
  rj.run_id,
  rj.run_id,
  rj.seen_at,
  rj.seen_at,
  rj.seen_at + interval '90 days'
from ats_run_jobs rj
where rj.job_snapshot is not null
on conflict (job_key, content_hash) do update set
  last_seen_at = greatest(ats_job_versions.last_seen_at, excluded.last_seen_at),
  last_seen_run_id = excluded.last_seen_run_id,
  expires_at = greatest(ats_job_versions.expires_at, excluded.expires_at);

update ats_run_jobs
set
  content_hash = encode(digest(job_snapshot::text, 'sha256'), 'hex'),
  observation_status = coalesce(observation_status, 'imported')
where job_snapshot is not null and content_hash is null;

update ats_jobs j
set current_content_hash = latest.content_hash
from (
  select distinct on (job_key) job_key, content_hash
  from ats_job_versions
  order by job_key, last_seen_at desc
) latest
where j.job_key = latest.job_key and j.current_content_hash is null;

create table if not exists ats_job_evaluations (
  run_id uuid not null references ats_scan_runs(id) on delete cascade,
  job_key text not null references ats_jobs(job_key) on delete cascade,
  decision text not null check (decision in ('accepted', 'rejected')),
  reasons jsonb not null default '[]'::jsonb,
  signals jsonb not null default '{}'::jsonb,
  evaluated_at timestamptz not null default now(),
  primary key (run_id, job_key)
);

create index if not exists ats_job_evaluations_decision_idx
  on ats_job_evaluations(decision, evaluated_at desc);

create or replace view ats_job_evidence_dashboard as
select
  rj.run_id,
  sr.persisted_at as run_at,
  sr.scan_kind,
  rj.job_key,
  j.provider,
  j.source_id,
  j.company,
  j.title,
  j.location,
  j.url,
  rj.observation_status,
  rj.content_hash,
  ev.decision,
  ev.reasons,
  ev.signals
from ats_run_jobs rj
join ats_scan_runs sr on sr.id = rj.run_id
join ats_jobs j on j.job_key = rj.job_key
left join ats_job_evaluations ev on ev.run_id = rj.run_id and ev.job_key = rj.job_key;

create or replace view ats_fetch_evidence_dashboard as
select
  fo.run_id,
  sr.persisted_at as run_at,
  sr.scan_kind,
  fo.company,
  fo.provider,
  fo.source_slug,
  fo.url,
  fo.method,
  fo.outcome,
  fo.status_code,
  fo.attempt_count,
  fo.elapsed_ms,
  fo.error,
  fo.evidence_hash,
  fp.first_seen_at as payload_first_seen_at,
  fp.last_seen_at as payload_last_seen_at
from ats_fetch_observations fo
join ats_scan_runs sr on sr.id = fo.run_id
left join ats_fetch_payloads fp on fp.evidence_hash = fo.evidence_hash;

create or replace function ats_cleanup_evidence(retention interval default interval '90 days')
returns table (
  evaluations_deleted bigint,
  observations_deleted bigint,
  job_versions_deleted bigint,
  fetch_payloads_deleted bigint
)
language plpgsql
as $$
declare
  cutoff timestamptz := now() - retention;
begin
  delete from ats_job_evaluations where evaluated_at < cutoff;
  get diagnostics evaluations_deleted = row_count;

  delete from ats_fetch_observations where observed_at < cutoff;
  get diagnostics observations_deleted = row_count;

  delete from ats_job_versions where last_seen_at < cutoff;
  get diagnostics job_versions_deleted = row_count;

  delete from ats_fetch_payloads p
  where p.last_seen_at < cutoff
    and not exists (
      select 1 from ats_fetch_observations o where o.evidence_hash = p.evidence_hash
    );
  get diagnostics fetch_payloads_deleted = row_count;

  return next;
end;
$$;

alter table ats_scan_runs enable row level security;
alter table ats_jobs enable row level security;
alter table ats_run_jobs enable row level security;
alter table ats_fetch_payloads enable row level security;
alter table ats_fetch_observations enable row level security;
alter table ats_job_versions enable row level security;
alter table ats_job_evaluations enable row level security;
