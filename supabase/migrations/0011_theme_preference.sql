-- profiles.theme_preference: persisted per-user theme choice.
--
-- Values:
--   'system'             -- follow the OS / browser prefers-color-scheme
--   'light'              -- explicit light palette
--   'dark_slate'         -- dark, comfortable for long reading (default dark)
--   'dark_high_contrast' -- dark, punchier feedback colors
--
-- The check constraint is named so future migrations can ALTER / DROP it
-- cleanly. Idempotent via `if not exists` on both the column and the
-- constraint -- safe to re-apply.

alter table public.profiles
  add column if not exists theme_preference text not null default 'system';

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'profiles_theme_preference_check'
      and conrelid = 'public.profiles'::regclass
  ) then
    alter table public.profiles
      add constraint profiles_theme_preference_check
      check (theme_preference in ('system', 'light', 'dark_slate', 'dark_high_contrast'));
  end if;
end$$;
