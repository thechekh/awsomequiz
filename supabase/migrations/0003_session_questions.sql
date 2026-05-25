-- Add the pre-picked question sequence to exam_sessions so resume works and
-- the question order is deterministic across reruns / browser refreshes.

alter table public.exam_sessions
  add column if not exists question_ids uuid[] not null default '{}';

comment on column public.exam_sessions.question_ids is
  'Ordered list of question UUIDs picked at session start. Drives the question runner and resume.';
