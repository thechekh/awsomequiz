-- AWSomeQuiz schema for Supabase Postgres.
-- Paste into Supabase SQL editor. Safe to re-run: tables use IF NOT EXISTS,
-- triggers/policies are dropped before recreation in policies.sql.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Helper: bump updated_at on UPDATE
-- ---------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------------
-- profiles: one row per auth.users row; auto-created by trigger below
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  username text unique,
  preferences jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- SECURITY DEFINER so the trigger can insert into profiles regardless of RLS.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.profiles (id, username)
  values (new.id, split_part(new.email, '@', 1))
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- certifications: one row per exam (CLF-C02, SAA, DVA, ...)
-- ---------------------------------------------------------------------------
create table if not exists public.certifications (
  id uuid primary key default gen_random_uuid(),
  code text unique not null,
  name text not null,
  question_count int not null default 65,
  duration_minutes int not null default 90,
  pass_threshold_pct int not null default 70,
  created_at timestamptz not null default now()
);

-- ---------------------------------------------------------------------------
-- domains: exam domains with official AWS weights
-- ---------------------------------------------------------------------------
create table if not exists public.domains (
  id uuid primary key default gen_random_uuid(),
  certification_id uuid not null references public.certifications(id) on delete cascade,
  code text not null,
  name text not null,
  weight numeric(5,2) not null,
  display_order int not null default 0,
  unique (certification_id, code)
);

create index if not exists idx_domains_certification on public.domains(certification_id);

-- ---------------------------------------------------------------------------
-- questions
-- external_id preserves the source SQLite question_number so re-migration upserts.
-- domain_id is nullable: not all dumps carry domain tags (current CLF-C02 dump doesn't).
-- ---------------------------------------------------------------------------
create table if not exists public.questions (
  id uuid primary key default gen_random_uuid(),
  certification_id uuid not null references public.certifications(id) on delete restrict,
  domain_id uuid references public.domains(id) on delete set null,
  external_id text not null,
  stem text not null,
  type text not null check (type in ('single','multiple')),
  source text,
  is_active boolean not null default true,
  version int not null default 1,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (certification_id, external_id)
);

create index if not exists idx_questions_cert_active on public.questions(certification_id, is_active);
create index if not exists idx_questions_domain on public.questions(domain_id) where domain_id is not null;

drop trigger if exists questions_set_updated_at on public.questions;
create trigger questions_set_updated_at
  before update on public.questions
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- options
-- explanation_detailed is the only explanation field in v1 (filled from the
-- existing SQLite `description`). The brief's `explanation_short` is omitted
-- since we have no separate short/detailed split in the source data.
-- ---------------------------------------------------------------------------
create table if not exists public.options (
  id uuid primary key default gen_random_uuid(),
  question_id uuid not null references public.questions(id) on delete cascade,
  label text not null check (label ~ '^[A-F]$'),
  text text not null,
  is_correct boolean not null default false,
  explanation_detailed text,
  related_context text,
  unique (question_id, label)
);

create index if not exists idx_options_question on public.options(question_id);

-- ---------------------------------------------------------------------------
-- exam_sessions
-- ---------------------------------------------------------------------------
create table if not exists public.exam_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  certification_id uuid not null references public.certifications(id) on delete restrict,
  mode text not null check (mode in ('practice','timed','weak_areas','missed','domain_focus','bookmarked')),
  domain_filter uuid[],
  question_count int not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  duration_seconds int,
  score_pct numeric(5,2),
  passed boolean
);

create index if not exists idx_sessions_user_started on public.exam_sessions(user_id, started_at desc);
-- Partial index for "resume incomplete session" lookups
create index if not exists idx_sessions_user_incomplete on public.exam_sessions(user_id) where completed_at is null;

-- ---------------------------------------------------------------------------
-- user_answers
-- Composite PK (session_id, question_id): a question is answered at most once per session.
-- Only IDs stored (not option text) per §9 free-tier constraint.
-- ---------------------------------------------------------------------------
create table if not exists public.user_answers (
  session_id uuid not null references public.exam_sessions(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete restrict,
  selected_option_ids uuid[] not null default '{}',
  is_correct boolean not null,
  time_spent_seconds int,
  answered_at timestamptz not null default now(),
  primary key (session_id, question_id)
);

create index if not exists idx_user_answers_question on public.user_answers(question_id);

-- ---------------------------------------------------------------------------
-- bookmarks
-- ---------------------------------------------------------------------------
create table if not exists public.bookmarks (
  user_id uuid not null references auth.users(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete cascade,
  note text,
  created_at timestamptz not null default now(),
  primary key (user_id, question_id)
);

-- ---------------------------------------------------------------------------
-- question_stats: trigger-maintained rollup (chosen over MATERIALIZED VIEW
-- because Supabase free tier has no pg_cron for scheduled REFRESHes, and
-- per-user rollup keeps writes incremental rather than recomputing globally).
-- ---------------------------------------------------------------------------
create table if not exists public.question_stats (
  user_id uuid not null references auth.users(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete cascade,
  times_seen int not null default 0,
  times_correct int not null default 0,
  last_seen_at timestamptz,
  last_correct_at timestamptz,
  primary key (user_id, question_id)
);

create index if not exists idx_question_stats_user on public.question_stats(user_id);

-- SECURITY DEFINER so users can't write to question_stats directly but the
-- trigger can update on their behalf when they answer a question.
create or replace function public.update_question_stats()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  v_user_id uuid;
begin
  select user_id into v_user_id from public.exam_sessions where id = new.session_id;
  insert into public.question_stats (
    user_id, question_id, times_seen, times_correct, last_seen_at, last_correct_at
  )
  values (
    v_user_id,
    new.question_id,
    1,
    case when new.is_correct then 1 else 0 end,
    new.answered_at,
    case when new.is_correct then new.answered_at else null end
  )
  on conflict (user_id, question_id) do update set
    times_seen = public.question_stats.times_seen + 1,
    times_correct = public.question_stats.times_correct + case when new.is_correct then 1 else 0 end,
    last_seen_at = new.answered_at,
    last_correct_at = case when new.is_correct then new.answered_at else public.question_stats.last_correct_at end;
  return new;
end;
$$;

drop trigger if exists user_answers_update_stats on public.user_answers;
create trigger user_answers_update_stats
  after insert on public.user_answers
  for each row execute function public.update_question_stats();

-- ---------------------------------------------------------------------------
-- question_reports: insert-by-anyone-authenticated, admin-read via service role
-- user_id is nullable so reports survive user deletion (for moderation history)
-- ---------------------------------------------------------------------------
create table if not exists public.question_reports (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references auth.users(id) on delete set null,
  question_id uuid not null references public.questions(id) on delete cascade,
  reason text not null check (reason in ('incorrect_answer','typo','ambiguous','outdated','other')),
  details text,
  status text not null default 'open' check (status in ('open','triaged','resolved','dismissed')),
  created_at timestamptz not null default now()
);

create index if not exists idx_question_reports_open on public.question_reports(question_id) where status = 'open';
