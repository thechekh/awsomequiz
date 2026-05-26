-- Allow anonymous (unauthenticated) users to read reference data
-- (certifications, domains, questions, options). This lets guest-mode
-- practice work without requiring a sign-in -- the user data tables
-- (exam_sessions, user_answers, bookmarks, etc.) remain self-only.
--
-- Trade-off: the question bank is now technically scrapeable with just the
-- public anon key. That's acceptable for a study tool: the question content
-- is curated public exam-prep material, not proprietary.

drop policy if exists certifications_read_all on public.certifications;
drop policy if exists domains_read_all        on public.domains;
drop policy if exists questions_read_active   on public.questions;
drop policy if exists options_read_all        on public.options;

create policy certifications_read_all
  on public.certifications for select
  using (true);

create policy domains_read_all
  on public.domains for select
  using (true);

create policy questions_read_active
  on public.questions for select
  using (is_active = true);

create policy options_read_all
  on public.options for select
  using (true);

-- Flashcard reference tables also open up so a guest-mode flashcards page
-- could be added later. Not required for the immediate guest practice
-- feature but cheaper to do now than as a separate migration.
drop policy if exists flashcard_decks_read_all on public.flashcard_decks;
drop policy if exists flashcards_read_active   on public.flashcards;

create policy flashcard_decks_read_all
  on public.flashcard_decks for select
  using (true);

create policy flashcards_read_active
  on public.flashcards for select
  using (is_active = true);
