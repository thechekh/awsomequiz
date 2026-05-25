-- RLS policies for AWSomeQuiz.
-- Run AFTER schema.sql. Safe to re-run: each policy is dropped before recreation.

-- ---------------------------------------------------------------------------
-- Enable RLS on every table
-- ---------------------------------------------------------------------------
alter table public.profiles          enable row level security;
alter table public.certifications    enable row level security;
alter table public.domains           enable row level security;
alter table public.questions         enable row level security;
alter table public.options           enable row level security;
alter table public.exam_sessions     enable row level security;
alter table public.user_answers      enable row level security;
alter table public.bookmarks         enable row level security;
alter table public.question_stats    enable row level security;
alter table public.question_reports  enable row level security;

-- ---------------------------------------------------------------------------
-- profiles: self read/update. INSERT happens via SECURITY DEFINER trigger on auth.users.
-- ---------------------------------------------------------------------------
drop policy if exists profiles_self_read   on public.profiles;
drop policy if exists profiles_self_update on public.profiles;

create policy profiles_self_read
  on public.profiles for select
  using (auth.uid() = id);

create policy profiles_self_update
  on public.profiles for update
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- ---------------------------------------------------------------------------
-- Reference data (certifications, domains, questions, options): world-readable
-- to authenticated users. Writes happen via the service role only (migration script).
-- ---------------------------------------------------------------------------
drop policy if exists certifications_read_all on public.certifications;
drop policy if exists domains_read_all        on public.domains;
drop policy if exists questions_read_active   on public.questions;
drop policy if exists options_read_all        on public.options;

create policy certifications_read_all
  on public.certifications for select to authenticated using (true);

create policy domains_read_all
  on public.domains for select to authenticated using (true);

create policy questions_read_active
  on public.questions for select to authenticated using (is_active = true);

create policy options_read_all
  on public.options for select to authenticated using (true);

-- ---------------------------------------------------------------------------
-- exam_sessions: full CRUD on own rows
-- ---------------------------------------------------------------------------
drop policy if exists exam_sessions_self_read   on public.exam_sessions;
drop policy if exists exam_sessions_self_insert on public.exam_sessions;
drop policy if exists exam_sessions_self_update on public.exam_sessions;
drop policy if exists exam_sessions_self_delete on public.exam_sessions;

create policy exam_sessions_self_read
  on public.exam_sessions for select using (auth.uid() = user_id);

create policy exam_sessions_self_insert
  on public.exam_sessions for insert with check (auth.uid() = user_id);

create policy exam_sessions_self_update
  on public.exam_sessions for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy exam_sessions_self_delete
  on public.exam_sessions for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- user_answers: own rows, scoped via parent session
-- ---------------------------------------------------------------------------
drop policy if exists user_answers_self_read   on public.user_answers;
drop policy if exists user_answers_self_insert on public.user_answers;

create policy user_answers_self_read
  on public.user_answers for select
  using (exists (
    select 1 from public.exam_sessions s
    where s.id = user_answers.session_id and s.user_id = auth.uid()
  ));

create policy user_answers_self_insert
  on public.user_answers for insert
  with check (exists (
    select 1 from public.exam_sessions s
    where s.id = user_answers.session_id and s.user_id = auth.uid()
  ));

-- ---------------------------------------------------------------------------
-- bookmarks: full CRUD on own rows
-- ---------------------------------------------------------------------------
drop policy if exists bookmarks_self_read   on public.bookmarks;
drop policy if exists bookmarks_self_insert on public.bookmarks;
drop policy if exists bookmarks_self_update on public.bookmarks;
drop policy if exists bookmarks_self_delete on public.bookmarks;

create policy bookmarks_self_read
  on public.bookmarks for select using (auth.uid() = user_id);

create policy bookmarks_self_insert
  on public.bookmarks for insert with check (auth.uid() = user_id);

create policy bookmarks_self_update
  on public.bookmarks for update using (auth.uid() = user_id) with check (auth.uid() = user_id);

create policy bookmarks_self_delete
  on public.bookmarks for delete using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- question_stats: read-only for users. Writes happen via SECURITY DEFINER trigger.
-- ---------------------------------------------------------------------------
drop policy if exists question_stats_self_read on public.question_stats;

create policy question_stats_self_read
  on public.question_stats for select using (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- question_reports: any authenticated user can INSERT. No SELECT/UPDATE/DELETE
-- policies for users — moderators read via the service role (bypasses RLS).
-- ---------------------------------------------------------------------------
drop policy if exists question_reports_insert on public.question_reports;

create policy question_reports_insert
  on public.question_reports for insert to authenticated
  with check (auth.uid() = user_id);
