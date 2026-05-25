-- Anki-style flashcards for AWS terminology / service definitions.
-- Loaded from CSVs in `questions/` via `scripts/load_flashcards.py`.

-- ---------------------------------------------------------------------------
-- flashcard_decks: groupings the UI offers as separate study targets.
-- code is the natural key for idempotent re-loads from CSV.
-- ---------------------------------------------------------------------------
create table if not exists public.flashcard_decks (
  id uuid primary key default gen_random_uuid(),
  certification_id uuid references public.certifications(id) on delete cascade,
  code text unique not null,
  name text not null,
  description text,
  display_order int not null default 0,
  created_at timestamptz not null default now()
);

create index if not exists idx_flashcard_decks_certification
  on public.flashcard_decks(certification_id);

-- ---------------------------------------------------------------------------
-- flashcards: one row per card. `external_id` is a content hash of `front`
-- so the loader can re-run safely without creating duplicates.
-- ---------------------------------------------------------------------------
create table if not exists public.flashcards (
  id uuid primary key default gen_random_uuid(),
  deck_id uuid not null references public.flashcard_decks(id) on delete cascade,
  external_id text not null,
  front text not null,
  back text not null,
  category text,
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (deck_id, external_id)
);

create index if not exists idx_flashcards_deck_active
  on public.flashcards(deck_id, is_active);

drop trigger if exists flashcards_set_updated_at on public.flashcards;
create trigger flashcards_set_updated_at
  before update on public.flashcards
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- flashcard_reviews: append-only log of "I knew it / I didn't" verdicts.
-- ---------------------------------------------------------------------------
create table if not exists public.flashcard_reviews (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  flashcard_id uuid not null references public.flashcards(id) on delete cascade,
  knew_it boolean not null,
  reviewed_at timestamptz not null default now()
);

create index if not exists idx_flashcard_reviews_user_card
  on public.flashcard_reviews(user_id, flashcard_id, reviewed_at desc);

-- ---------------------------------------------------------------------------
-- flashcard_stats: trigger-maintained rollup (per user, per card).
-- ---------------------------------------------------------------------------
create table if not exists public.flashcard_stats (
  user_id uuid not null references auth.users(id) on delete cascade,
  flashcard_id uuid not null references public.flashcards(id) on delete cascade,
  times_reviewed int not null default 0,
  times_correct int not null default 0,
  last_reviewed_at timestamptz,
  last_correct_at timestamptz,
  primary key (user_id, flashcard_id)
);

create index if not exists idx_flashcard_stats_user
  on public.flashcard_stats(user_id);

create or replace function public.update_flashcard_stats()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.flashcard_stats (
    user_id, flashcard_id, times_reviewed, times_correct, last_reviewed_at, last_correct_at
  )
  values (
    new.user_id,
    new.flashcard_id,
    1,
    case when new.knew_it then 1 else 0 end,
    new.reviewed_at,
    case when new.knew_it then new.reviewed_at else null end
  )
  on conflict (user_id, flashcard_id) do update set
    times_reviewed  = public.flashcard_stats.times_reviewed + 1,
    times_correct   = public.flashcard_stats.times_correct + case when new.knew_it then 1 else 0 end,
    last_reviewed_at = new.reviewed_at,
    last_correct_at  = case when new.knew_it then new.reviewed_at else public.flashcard_stats.last_correct_at end;
  return new;
end;
$$;

drop trigger if exists flashcard_reviews_update_stats on public.flashcard_reviews;
create trigger flashcard_reviews_update_stats
  after insert on public.flashcard_reviews
  for each row execute function public.update_flashcard_stats();

-- ---------------------------------------------------------------------------
-- RLS: decks + cards world-readable for authenticated users; reviews/stats self-only.
-- ---------------------------------------------------------------------------
alter table public.flashcard_decks    enable row level security;
alter table public.flashcards         enable row level security;
alter table public.flashcard_reviews  enable row level security;
alter table public.flashcard_stats    enable row level security;

drop policy if exists flashcard_decks_read_all     on public.flashcard_decks;
drop policy if exists flashcards_read_active       on public.flashcards;
drop policy if exists flashcard_reviews_self_read   on public.flashcard_reviews;
drop policy if exists flashcard_reviews_self_insert on public.flashcard_reviews;
drop policy if exists flashcard_stats_self_read    on public.flashcard_stats;

create policy flashcard_decks_read_all
  on public.flashcard_decks for select to authenticated using (true);

create policy flashcards_read_active
  on public.flashcards for select to authenticated using (is_active = true);

create policy flashcard_reviews_self_read
  on public.flashcard_reviews for select using (auth.uid() = user_id);

create policy flashcard_reviews_self_insert
  on public.flashcard_reviews for insert with check (auth.uid() = user_id);

create policy flashcard_stats_self_read
  on public.flashcard_stats for select using (auth.uid() = user_id);
