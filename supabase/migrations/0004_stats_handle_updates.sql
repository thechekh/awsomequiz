-- Phase 5 (timed exam) lets users revise their answer to a question before
-- submitting. The Phase 1 trigger only fired on INSERT, so a revised answer
-- never updated question_stats and the rollup drifted out of sync.
--
-- This migration extends the trigger to also fire on UPDATE, applying a
-- correctness delta when (and only when) the is_correct flag flips. INSERT
-- behavior is unchanged.

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

  if tg_op = 'INSERT' then
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
      times_seen      = public.question_stats.times_seen + 1,
      times_correct   = public.question_stats.times_correct + case when new.is_correct then 1 else 0 end,
      last_seen_at    = new.answered_at,
      last_correct_at = case when new.is_correct then new.answered_at else public.question_stats.last_correct_at end;

  elsif tg_op = 'UPDATE' then
    -- Only react when correctness flipped (skips noise from time-spent-only updates).
    if old.is_correct is distinct from new.is_correct then
      update public.question_stats
      set
        times_correct   = times_correct + case when new.is_correct then 1 else -1 end,
        last_correct_at = case when new.is_correct then new.answered_at else last_correct_at end
      where user_id = v_user_id and question_id = new.question_id;
    end if;
  end if;

  return new;
end;
$$;

drop trigger if exists user_answers_update_stats on public.user_answers;
create trigger user_answers_update_stats
  after insert or update on public.user_answers
  for each row execute function public.update_question_stats();
