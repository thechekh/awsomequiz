-- RPC for filing question reports.
--
-- The plain INSERT path on `question_reports` keeps hitting the RLS policy
-- check `auth.uid() = user_id` in production even though the JWT is set on
-- the PostgREST sub-client (`set_session` + `postgrest.auth()`). Wrap the
-- insert in a SECURITY DEFINER function that reads auth.uid() server-side
-- so the JWT-to-client header propagation race goes away.
--
-- The function is grant-EXECUTE to `authenticated` only; anon can't call it.
-- It accepts only the user-supplied fields (question_id, reason, details).
-- user_id is forced to auth.uid() server-side so a logged-in user can never
-- file a report under another identity.

create or replace function public.submit_question_report(
  p_question_id uuid,
  p_reason text,
  p_details text default null
) returns uuid
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_uid uuid;
  v_id uuid;
begin
  v_uid := auth.uid();
  if v_uid is null then
    raise exception 'must be authenticated';
  end if;
  if p_reason not in ('incorrect_answer','typo','ambiguous','outdated','other') then
    raise exception 'invalid reason %', p_reason;
  end if;
  insert into public.question_reports (user_id, question_id, reason, details)
  values (v_uid, p_question_id, p_reason, nullif(p_details, ''))
  returning id into v_id;
  return v_id;
end;
$$;

revoke all on function public.submit_question_report(uuid, text, text) from public;
grant execute on function public.submit_question_report(uuid, text, text) to authenticated;
