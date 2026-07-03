-- ─────────────────────────────────────────────────────────────────────────────
-- Run this in the Supabase SQL editor (or via `supabase db push`).
-- Adds the `jobs` table that backs background processing (RQ).
-- The existing `reports` table is unchanged.
-- ─────────────────────────────────────────────────────────────────────────────

create table if not exists jobs (
  id         uuid primary key default gen_random_uuid(),
  user_id    uuid not null references auth.users(id) on delete cascade,
  type       text not null,                      -- 'initial_report' | 'final_report'
  status     text not null default 'queued',     -- queued | started | finished | failed
  progress   int  not null default 0,            -- 0-100
  stage      text,                                -- human-readable current step
  result     jsonb,                               -- payload the client consumes when finished
  error      text,                                -- safe message when failed
  report_id  uuid,                                -- linked report, when known
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists jobs_user_created_idx on jobs (user_id, created_at desc);

alter table jobs enable row level security;

-- One user can only ever see their own jobs. Server-side writes use the
-- service-role key (which bypasses RLS) but always scope by user_id.
drop policy if exists "users see own jobs" on jobs;
create policy "users see own jobs" on jobs
  for all using (auth.uid() = user_id);

-- Optional housekeeping: purge finished/failed jobs older than a day.
-- Schedule with pg_cron if available, or run manually.
--   delete from jobs
--   where status in ('finished','failed') and updated_at < now() - interval '1 day';
