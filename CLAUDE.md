# CLAUDE.md

Guide for Claude Code (or any other AI agent / fresh human) picking up work on AWSomeQuiz.

## Project in one paragraph

AWSomeQuiz is a multi-user web platform for practicing the AWS Certified Cloud
Practitioner (CLF-C02) exam. Streamlit frontend (multi-page via `pages/`),
Supabase backend (Postgres + Auth). Original source data: a 915-question SQLite
dump in `dumps/CLF-C02.db`. Local dev runs the Supabase stack via the Supabase
CLI in Docker; the Streamlit app runs as a separate container (or on host via
uv). Deploy target: Streamlit Community Cloud + hosted Supabase, both free-tier.

The original product brief is in [docs/BRIEF.md](docs/BRIEF.md). Skim it before
making scope decisions.

---

## Phase roadmap

| # | Phase | Status | Deliverables |
|---|-------|:-:|---|
| 1 | Postgres schema + RLS | DONE | `supabase/migrations/0001_schema.sql`, `0002_policies.sql`, `supabase/seed.sql` |
| 2 | SQLite -> Supabase migration + Docker dev setup | DONE | `scripts/migrate_sqlite_to_supabase.py`, `docker/Dockerfile`, `docker-compose.yml`, `Makefile`, `dev.ps1` |
| 3 | Auth E2E | DONE | `app/auth.py`, `app/db.py` (PKCE), `streamlit_app.py` gate via `st.navigation`, `pages/login.py` (3 tabs + GitHub button), `pages/home.py`, `pages/account.py`, `pages/reset_password.py`. Email/password register/login/logout/reset all working; GitHub OAuth via Supabase provider (was Google originally, swapped post-deploy because GitHub doesn't need Google Cloud Console). |
| 4 | Free-practice vertical | DONE | `pages/practice.py`, `app/session.py`, `app/queries.py`, `supabase/migrations/0003_session_questions.sql` (adds `exam_sessions.question_ids uuid[]`). Picker -> question runner with per-question review -> session summary. Bookmark toggle, report dialog, resume of incomplete sessions all working. |
| 5 | Timed exam | DONE | `pages/timed_exam.py`, `start_timed_session()` + `get_active_timed_session()` in `app/session.py`, `get_review_bundle()` in `app/queries.py`, `supabase/migrations/0004_stats_handle_updates.sql` (trigger now fires on UPDATE too, so revising answers keeps `question_stats` correct). `record_answer` now UPSERTs. 65Q/90min runner: sidebar grid, `st.fragment(run_every="1s")` timer with auto-submit, server-derived deadline, end-of-exam review (Wrong / Correct / All tabs). |
| 6 | Other review modes | DONE | `pages/review.py` (Weak / Missed tabs), `pages/bookmarks.py` (list + Practice all). Runner factored into `app/components/runner.py` and reused across practice / review / bookmarks. New `pick_weak_area_question_ids` / `pick_missed_question_ids` / `pick_bookmarked_question_ids` + `list_bookmarks` / `delete_bookmark` in `app/queries.py`. New `start_weak_areas_session` / `start_missed_session` / `start_bookmarked_session` in `app/session.py`. |
| 7 | Stats dashboard | DONE | `pages/stats.py`. 4 metric cards (unique seen / overall accuracy / current streak / sessions completed), timed-exam score history line chart, per-domain bar chart with "Untagged" fallback, recent-sessions table (last 20). New helpers in `app/queries.py`: `get_user_stats_summary`, `get_session_history`, `get_per_domain_accuracy`, `get_practice_streak` -- the three rollups use `@st.cache_data(ttl=30)`, history is uncached so a just-completed session shows up immediately. |
| 8 | Production deploy | DONE (code) / PENDING (user verifies) | `requirements.txt` added at repo root for Streamlit Cloud. `docs/how_to_run.md` got a Maintenance section (apply migrations to prod, rotate keys, free-tier limits, add another cert). Auth-callback failures (bad/expired OAuth code, bad OTP link) now surface to Login via `auth_callback_error` in session state. `tests/test_imports.py` catches import-time regressions. **User still needs to run the deploy steps end-to-end and confirm** -- I can't access GitHub / Supabase / Streamlit Cloud from this session. |
| Bonus | Anki-style flashcards | DONE | Scope addition after Phase 8. `supabase/migrations/0005_flashcards.sql` adds `flashcard_decks` / `flashcards` / `flashcard_reviews` / `flashcard_stats` (trigger-maintained rollup on review insert) + RLS. `scripts/load_flashcards.py` imports the 3 CSVs in `questions/` into 5 decks: AWS Basics, AWS Well-Architected Framework (WAF), AWS Cloud Adoption Framework (CAF), AWS Migration Strategies (6 Rs), AWS Services. `pages/flashcards.py` is the study UI: deck picker -> mode picker (all / unseen / need practice) -> flip-to-reveal runner -> session summary. Front + back render HTML (the CSVs contain `<b>`, `<i>`, `<span style=...>` formatting). |

### Deferred / explicitly out of scope for v1

User opted out of these during clarification — re-confirm before adding.

- **Explanation regeneration via LLM** (brief §6). Existing SQLite `description` is mapped 1:1 to `options.explanation_detailed` at migration time. If regen is added later, preserve the legacy text in a new `legacy_description` column first.
- **Domain tagging.** Source SQLite has no domain field. `questions.domain_id` is nullable; the 4 CLF-C02 domains exist in `seed.sql` but no question is linked. Weak-areas mode (Phase 6) falls back to per-question accuracy alone.
- **`difficulty` column** on questions. User opted out.
- **Full-text search** (`to_tsvector`). Add later if needed.
- **CSV export, keyboard shortcuts.** Phase 9 polish.

---

## Architecture

```
streamlit_app.py             # auth gate: handles ?code= and ?token_hash= callbacks, routes via st.navigation
pages/
  login.py                   # Sign in / Register / Forgot password tabs + GitHub OAuth button -- DONE
  home.py                    # Authenticated landing: resume banners for all modes + 4 quick-start CTAs -- DONE
  practice.py                # Free practice (picker + runner delegate) -- DONE
  timed_exam.py              # Timed exam runner (timer fragment, grid, no per-Q feedback, end review) -- DONE
  review.py                  # Weak-areas + Missed tabs (picker + runner delegate) -- DONE
  bookmarks.py               # Bookmark list/remove + Practice-all (runner delegate) -- DONE
  stats.py                   # 4 metric cards + score history + per-domain bar + recent sessions table -- DONE
  flashcards.py              # Anki-style: deck picker -> mode picker -> flip-to-reveal -> summary -- DONE
  account.py                 # Profile (username) + change password + sign out -- DONE
  reset_password.py          # Target of password-reset email link -- DONE
tests/
  test_imports.py            # Module-import smoke test (catches circular/typo issues)
requirements.txt             # Streamlit Cloud dep manifest (mirror of pyproject.toml)
app/
  auth.py                    # Supabase auth helpers -- DONE
  db.py                      # @st.cache_resource Supabase client (PKCE flow) -- DONE
  queries.py                 # cert/domains/questions/bookmark/report/review-bundle + mode-specific pick_* -- DONE
  session.py                 # start/record/complete/abandon for all session modes -- DONE
  components/
    runner.py                # Shared per-question runner (sidebar progress, input/review, completion) -- DONE
scripts/
  migrate_sqlite_to_supabase.py    # idempotent SQLite -> Postgres -- DONE
  load_flashcards.py               # idempotent CSV -> Postgres flashcards loader -- DONE
questions/                   # CSV sources for the flashcard decks
  basic.csv                  # Front,Back (Anki-style)
  aws_framework.csv          # aspect,description,framework (WAF / CAF / Migration Strategies)
  aws_service.csv            # service,description (~155 AWS services)
supabase/
  config.toml                # Supabase CLI config (GitHub OAuth disabled by default)
  migrations/0001_schema.sql            # 10 tables + indexes + 3 triggers -- DONE
  migrations/0002_policies.sql          # RLS on every table -- DONE
  migrations/0003_session_questions.sql # exam_sessions.question_ids column -- DONE
  migrations/0004_stats_handle_updates.sql  # trigger fires on UPDATE too -- DONE
  migrations/0005_flashcards.sql        # flashcard tables + RLS + stats trigger -- DONE
  seed.sql                   # CLF-C02 cert + 4 domains (auto-run by `supabase db reset`)
docker/Dockerfile            # Streamlit container (python:3.13-slim + uv)
docker-compose.yml           # Streamlit service; talks to Supabase via host.docker.internal
Makefile / dev.ps1           # one-command orchestration
dumps/CLF-C02.db             # source data (915 Q / 3,755 options)
docs/BRIEF.md                # original product brief
docs/how_to_run.md           # local + deploy walkthroughs
.streamlit/                  # streamlit config + secrets.toml.example
```

### Data flow at a glance

1. `supabase start` brings up Postgres + GoTrue (auth) + PostgREST + Studio + Inbucket inside Docker.
2. `supabase db reset` applies migrations + `seed.sql` -> CLF-C02 row + 4 domains exist.
3. `migrate_sqlite_to_supabase.py` reads `dumps/CLF-C02.db`, upserts into `public.questions` + `public.options`. Idempotent via `ON CONFLICT (certification_id, external_id)` and `ON CONFLICT (question_id, label)`.
4. Streamlit app reads via the anon-key `supabase-py` client (`app/db.py`); RLS filters rows by `auth.uid()`.
5. Auth flows go through GoTrue (`supabase.auth.sign_up` etc.); local verification emails land in Inbucket at http://localhost:54324.

### Schema notes worth remembering

- All PKs are `uuid` (`gen_random_uuid()` via `pgcrypto`).
- `questions.external_id` preserves the SQLite `question_number` as text so re-migration is idempotent without coupling Postgres IDs to source IDs.
- `question_stats` is a **trigger-maintained rollup table**, not a materialized view. Supabase free tier has no `pg_cron` for scheduled REFRESHes; trigger is `SECURITY DEFINER` so users can't write directly.
- `profiles` row auto-created via `on_auth_user_created` trigger on `auth.users` insert -- username defaults to email-local-part, user can update later.
- `question_reports.user_id` is nullable with `on delete set null` so moderation history survives user deletion.
- All user-owned tables (`exam_sessions`, `user_answers`, `bookmarks`, `question_stats`) are protected by self-only RLS policies. `certifications`/`domains`/`questions`/`options` are world-readable to authenticated users. `question_reports` is insert-only for users; admin reads via the service role (bypasses RLS).

---

## Scope decisions made so far (do not silently revert)

1. **No LLM explanation regen.** Use the existing SQLite descriptions as the only source of explanations. If the user re-opens this scope, the `regenerate_explanations.py` skeleton from brief §6 is the starting point; add a `legacy_description` column first to preserve originals.
2. **No `difficulty` column.** Surface accuracy via `question_stats` rollup instead.
3. **`questions.domain_id` is nullable** because source data has no domain. Don't make it NOT NULL without first tagging the 915 existing questions.
4. **No `explanation_short` column.** The brief lists it as "legacy" but our SQLite has only one description field per option, mapped to `explanation_detailed`.
5. **Python 3.13+** -- `requires-python = ">=3.13,<3.15"`. Streamlit Cloud needs the deploy Advanced setting at 3.13 or 3.14 to match the uv.lock file's >=3.13 pin. (Previously was 3.11; bumped after Streamlit Cloud build failed on the version mismatch.)
6. **Supabase CLI for local dev** (not a hand-rolled docker-compose with Postgres + GoTrue). Gives 1:1 prod parity for auth flows. Streamlit runs as a separate container.

## Hard constraints from the brief (do not violate)

- **No AI commit attribution.** Omit `Co-Authored-By: Claude` and "Generated with Claude Code" footers from commits and PR descriptions. (Brief §9.)
- **Free tier only.** Keep payloads small. Don't store option text in `user_answers` -- only IDs. Cache the Supabase client with `@st.cache_resource`; cache static reference data (domains, certifications) with `@st.cache_data(ttl=...)`.
- **No PII beyond email.** No payment processing.
- **`questions.is_active` is the soft-delete mechanism.** Don't hard-delete rows referenced by `user_answers`.

---

## Commands cheat sheet

| Win (PowerShell) | Unix (make) | What it does |
|---|---|---|
| `.\dev.ps1 dev` | `make dev` | One command: start Supabase, reset DB, migrate SQLite, run app container |
| `.\dev.ps1 db-up` | `make db-up` | `supabase start` |
| `.\dev.ps1 db-down` | `make db-down` | `supabase stop` |
| `.\dev.ps1 db-status` | `make db-status` | Print local URLs + anon/service keys |
| `.\dev.ps1 db-reset` | `make db-reset` | Drop DB; re-apply migrations + seed |
| `.\dev.ps1 migrate-sqlite` | `make migrate-sqlite` | Import `dumps/CLF-C02.db` into local Supabase |
| `.\dev.ps1 app` | `make app` | Run Streamlit on host (uv) -- faster reload |
| `.\dev.ps1 app-docker` | `make app-docker` | Build + run Streamlit container |
| `.\dev.ps1 lint` | `make lint` | `ruff check` |
| `.\dev.ps1 format` | `make format` | `ruff format` |

Direct commands (when the wrapper doesn't fit):
```powershell
uv sync                                      # install / refresh Python deps
uv run streamlit run streamlit_app.py        # run app
uv run python scripts/migrate_sqlite_to_supabase.py --sqlite dumps/CLF-C02.db --certification-code CLF-C02 --dry-run
supabase status                              # local URLs + JWT secret + keys
supabase db reset                            # re-apply migrations + seed
docker compose logs -f streamlit             # tail app logs
```

---

## What to do in the next session

The product brief is fully implemented. There is no "next phase" in the roadmap. Options if more work is needed:

1. **Domain tagging** -- weak-areas + per-domain stats will be much more useful once the 915 CLF-C02 questions actually have `domain_id` populated. Either: (a) build an admin page to tag them manually, (b) re-open scope on the LLM regen pipeline (see [[project-scope-decisions]]) and have it tag domain during the same prompt, or (c) write a one-shot classification script using Haiku 4.5.
2. **Additional certifications** -- see "Adding a second certification" in `docs/how_to_run.md`. The schema is already generic.
3. **Polish items deferred from the brief**:
   - CSV export of wrong-answer log (brief QoL section)
   - Keyboard shortcuts (Streamlit-limited; 1-6 to select option via `streamlit-shortcuts` package would work)
   - Full-text search (`to_tsvector` index on `questions.stem`)
4. **Quality**:
   - Real tests against the runner state machine (currently only smoke imports). Mock `app/db.get_supabase` and exercise the state transitions.
   - `mypy` / `pyright` strict mode -- the codebase is type-hinted but not type-checked in CI.
   - `ruff format --check` in pre-commit.
5. **Re-open scope decisions** -- check `[[project-scope-decisions]]` in memory. If the user wants LLM regen / difficulty / domain tagging, that's the scoped re-discussion.

### Phase 8 notes (just shipped, for context)

- **`requirements.txt`** at repo root is what Streamlit Cloud reads. Mirrors `pyproject.toml` -- keep both in sync when bumping deps.
- **Auth callback errors surface to the Login page** via `st.session_state["auth_callback_error"]`. `streamlit_app.py._handle_auth_callback` sets it on failed `exchange_code` or failed `verify_otp`; `pages/login.py` pops + renders it at the top.
- **Maintenance section** in `docs/how_to_run.md` covers applying migrations to prod, rotating keys, free-tier limits, monitoring, adding a 2nd certification, and refreshing the CLF-C02 dump.
- **`tests/test_imports.py`** catches circular imports / typos at import time. Run with `uv run pytest tests/`.
- I (the agent) couldn't actually run the deploy from this session -- no GitHub / Supabase Cloud / Streamlit Cloud access. User needs to do the actual deploy and report back any gaps in the walkthrough.

### Phase 7 notes (still relevant)

- All four stats helpers are in `app/queries.py`. Three of them (`get_user_stats_summary`, `get_per_domain_accuracy`, `get_practice_streak`) use `@st.cache_data(ttl=30)` -- short enough that the "I just completed a session" feedback feels live. `get_session_history` is **uncached** because users expect freshness on the recent-sessions table.
- `get_practice_streak` is computed in Python (fetch all session start dates for user, walk backward from today). Postgres-native via window functions would be cleaner but the brief said it's fine client-side; this also keeps the schema simpler.
- Streak counts as 0 if user hasn't practiced today **or** yesterday (one-day grace period). If you want strict "must include today", drop the `yesterday` check.
- `get_per_domain_accuracy` returns ALL configured domains (4 for CLF-C02) with 0-attempt rows, plus an "Untagged" row when the user has attempts on questions with `domain_id IS NULL`. The stats page chart filters to attempts>0 + non-untagged; if there's only Untagged, it shows an explanatory info banner instead of a chart.
- Built-in `st.line_chart` / `st.bar_chart` are used (no Altair / Plotly dep). They take pandas DataFrames with the index as the x-axis.

### Phase 6 notes (still relevant)

- Runner is now in `app/components/runner.py` and takes a `namespace` string. Each entry page (practice, review, bookmarks) uses its own namespace so state doesn't collide. The runner derives session/index/summary keys from the namespace and clears them on quit/finish.
- `render_summary` in the same module returns `"restart"` or `None`; pages handle the restart-click by clearing their summary key and rerunning.
- `pick_weak_area_question_ids` includes *unseen* questions alongside low-accuracy ones (brief: "where accuracy is below threshold OR unseen"). `min_attempts=3` filters out one-shot noise.
- `pick_missed_question_ids` queries `user_answers` directly (not `question_stats`) so it reflects last-submitted answers per session. Returns distinct question_ids; scope is the user's full history across all sessions.
- `list_bookmarks` uses a PostgREST nested-select on `bookmarks(questions(...))` but PostgREST doesn't filter parent rows by nested-table conditions, so we do a second `questions` lookup with `.in_()` to filter to the certification.
- Three new `get_active_*_session` helpers in `app/session.py`. `get_active_review_session` returns weak/missed but NOT bookmarked (bookmarks lives on its own page and has its own state namespace; user can have one weak-or-missed AND one bookmarked in flight simultaneously).

### Phase 5 notes (still relevant)

- `record_answer` now uses **UPSERT** (not INSERT). The Phase 1 trigger only fired on INSERT, so revising an answer in timed mode would leave `question_stats` out of date. Migration 0004 extends the trigger to fire on INSERT or UPDATE, with a correctness-delta path for the UPDATE case.
- Timer is `st.fragment(run_every="1s")`. The deadline is computed from `session.started_at + cert.duration_minutes`, **not** from a client clock -- prevents tab-clock-skew "cheating". Auto-submit guarded by `TIMED_AUTO_SUBMITTED_KEY` so the fragment can't double-fire during the rerun window.
- `complete_session` treats **unanswered questions as wrong** (matches real-exam scoring). Use `sess["question_count"]` as the denominator, not `len(answers)`.
- Sidebar question grid uses `st.button(type="primary" if current else "secondary")` for the current-question marker. There's no third button style; "v " prefix on the label distinguishes answered.
- `get_review_bundle` is the only N=1 query helper I've added -- everything else uses single-row reads. The bundle fetches questions + options + answers in 3 round-trips total (not N).

### Phase 4 notes (still relevant)

- `exam_sessions.question_ids uuid[]` (migration 0003) stores the pre-picked random sequence. Resume works because the sequence is stable across reruns / browser refreshes.
- `app/queries.py` caches static reference data with `@st.cache_data(ttl=...)`. Per-question data has a 5-min TTL so the same Streamlit session doesn't refetch every rerun.
- `app/session.py.complete_session` reads pass_threshold from the certification row; do not hardcode 70%.
- The `user_answers_update_stats` trigger is the only writer of `question_stats` -- if you ever need to recompute, drop the rollup and let the trigger refill on next answer (or write a one-shot backfill script).
- Practice page state lives in `st.session_state["practice_session"]` + `["practice_index"]` + `["practice_summary"]`. Timed page uses parallel `timed_*` keys so the two can coexist.
- Report dialog uses `@st.dialog` (Streamlit 1.40+). Don't downgrade Streamlit below that.

### Phase 3 notes (still relevant)

- PKCE flow is enabled in `app/db.py` (`ClientOptions(flow_type="pkce")`) so OAuth + reset links return a `code` we can `exchange_code_for_session` for. Email confirmation links use `verify_otp` with `token_hash + type` -- both handled in `streamlit_app.py` `_handle_auth_callback()`.
- Session lives in `st.session_state["supabase_session"]` as a dict (not the raw `Session` model -- Streamlit serializes it across reruns). `app/auth.apply_session_to_client()` must be called on every rerun before queries that need RLS.
- GitHub OAuth: button in `pages/login.py` calls `get_github_oauth_url()` which always returns a URL (supabase-py doesn't validate provider availability server-side -- it just builds the request URL). So the button always renders when a URL is generated. Validation happens when the user clicks: if GitHub isn't enabled in Supabase, they get a 400 "Unsupported provider" error. To enable: GitHub OAuth App at <https://github.com/settings/developers> -> Supabase dashboard -> Auth -> Providers -> GitHub -> paste Client ID + Secret. (No Google Cloud Console / consent screen needed; this was swapped from Google for that reason.)
- Email confirmations are `false` locally (instant signup). For prod, flip `[auth.email] enable_confirmations = true`. Either way, Inbucket at http://localhost:54324 catches signup/reset emails locally.
- `profiles` row is auto-created by the `on_auth_user_created` trigger -- don't insert on signup, just read/update via `pages/account.py`.

---

## Conventions for new code

- Type hints on every function signature.
- One-line docstring on each public function (the function body explains "how"; the docstring explains "what + why").
- Inline `# 1-2 sentence` comments only where the choice is non-obvious. No commentary that restates the code.
- `ruff check .` and `ruff format .` should pass cleanly before declaring a phase done.
- No new top-level files without a reason. Prefer extending existing modules.
- No `# TODO` comments in committed code -- either do it or add a row to the roadmap table.
