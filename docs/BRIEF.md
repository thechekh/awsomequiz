# Build Brief -- AWS Cloud Practitioner Practice Platform

> Original brief from the project owner. Preserved verbatim. Scope adjustments
> made during clarification are captured in `CLAUDE.md` under "Scope decisions".

You are helping me refactor a local Streamlit quiz app into a deployed multi-user web platform for practicing the **AWS Certified Cloud Practitioner (CLF-C02)** exam. Read the full brief first, then propose a phased plan before writing code.

---

## 1. Background & current state

I'm a senior Python/fullstack developer (FastAPI, Django, Postgres, React, AWS). I currently have a **local Streamlit app** that loads a **SQLite dump** containing CLF-C02 questions and short per-option explanations and serves them as a quiz. It is single-user, runs only on my machine, has no persistence between runs, and the explanations are too thin.

## 2. Target state

A deployed web app at a public URL where any user can register, log in, and practice the CLF-C02 exam with:

- Long-form, per-option explanations (correct *and* incorrect options) tailored to each specific question, not generic blurbs.
- Multiple practice modes (free practice, timed full-length simulation, weak-area focus, missed-questions review).
- Persistent progress, score history, bookmarks, and filters.
- Free-tier-only infrastructure for now.

## 3. Tech stack (fixed)

- **Language:** Python 3.11+
- **Frontend:** Streamlit (multi-page via `st.Page` / `pages/` directory)
- **Database + Auth:** Supabase (managed Postgres + Supabase Auth) -- free tier
- **Python client:** `supabase-py` (v2+)
- **Hosting:** Streamlit Community Cloud (free) unless you have a strong reason to recommend Fly.io / Render / Railway free tier instead -- if so, justify.
- **Secrets:** Streamlit `secrets.toml` for local dev, Streamlit Cloud secrets UI for prod.
- **Migration tool:** plain Python script using `supabase-py` or `psycopg[binary]` against the Supabase connection string.

## 4. Database schema (propose, refine, then implement)

Design Postgres tables that cleanly support every feature in §5. Starting point -- improve as needed and call out anything you'd change:

- `profiles` -- `id` (FK to `auth.users.id`), `username`, `created_at`, `preferences jsonb`. Linked to Supabase Auth via RLS-friendly trigger.
- `certifications` -- initially one row for CLF-C02; built generic so SAA / DVA can be added later without schema change.
- `domains` -- the four CLF-C02 domains (Cloud Concepts, Security & Compliance, Cloud Technology & Services, Billing/Pricing/Support), with `weight` for exam scoring.
- `questions` -- `id`, `certification_id`, `domain_id`, `stem text`, `type` (single/multiple), `difficulty` (easy/medium/hard), `source`, `is_active`, `version`.
- `options` -- `id`, `question_id`, `label` (A/B/C/D), `text`, `is_correct`, `explanation_short` (legacy), `explanation_detailed`, `related_context`.
- `exam_sessions` -- `id`, `user_id`, `mode` (practice / timed / weak_areas / missed / domain_focus), `domain_filter`, `started_at`, `completed_at`, `duration_seconds`, `score_pct`, `passed`.
- `user_answers` -- `session_id`, `question_id`, `selected_option_ids int[]`, `is_correct`, `time_spent_seconds`, `answered_at`.
- `bookmarks` -- `user_id`, `question_id`, `note`, `created_at`. Composite PK.
- `question_stats` -- materialized view or rollup table: per `(user_id, question_id)` -> `times_seen`, `times_correct`, `last_seen_at`, `last_correct_at`. Drives "weak areas" mode.
- `question_reports` -- let users flag bad questions; columns `user_id`, `question_id`, `reason`, `details`, `status`.

**Row-Level Security:** Enable RLS on every user-owned table. Write policies so a user can only read/write their own rows. Questions/options/domains are world-readable; reports are insert-by-anyone-read-by-admin.

Deliver schema as `schema.sql` plus a separate `policies.sql`.

## 5. Features (build all of these)

**Auth & account**
- Supabase Auth email + password with email verification.
- Password reset flow.
- Optional: Google OAuth via Supabase (one toggle -- implement it).
- Streamlit session state holds the JWT; refresh on near-expiry.

**Practice modes**
- *Free practice* -- pick a domain or "all", pick count (10/25/50/all), no timer, immediate feedback after each question with full explanation.
- *Timed exam simulation* -- 65 questions, 90 minutes, mirrors real CLF-C02 format, no feedback until the end, then a full review screen with explanations.
- *Weak-areas mode* -- pulls questions where the user's accuracy is below a threshold (default 70%) or unseen questions, weighted by domain mass.
- *Missed-questions review* -- only questions the user has gotten wrong at least once.
- *Bookmarked review* -- only questions the user has bookmarked.

**During a question**
- Render stem, options as radio (single-answer) or checkboxes (multi-answer) based on `questions.type`.
- After submit: show correctness, then show **every option's** detailed explanation (not just the chosen one), plus a "Related context" paragraph linking back to the AWS service or concept.
- Bookmark toggle, "Report this question" link.

**Progress & analytics dashboard**
- Total questions seen / unique seen / accuracy overall and per domain.
- Score history (line chart) across timed sessions.
- Heatmap or bar chart of accuracy per domain to highlight weak areas.
- Streaks (days practiced in a row).
- Recent session list with resume-if-incomplete.

**Filters & navigation**
- Filter by domain, difficulty, "only unseen", "only wrong-before", "only bookmarked".
- Search question text (Postgres `to_tsvector` full-text index).

**Quality of life**
- Resume incomplete session.
- Keyboard shortcuts (1-6 to select option, Enter to submit, B to bookmark) -- Streamlit limitation: implement what's feasible, document what isn't.
- Dark mode (Streamlit theme).
- Export user's wrong-answer log as CSV.

## 6. Explanation regeneration pipeline

This is a separate one-shot batch job, not part of the user-facing app. Build it as a standalone script.

**Input:** existing SQLite dump where each option has a short, generic explanation.
**Output:** rows written into `options.explanation_detailed` and `options.related_context` on Supabase.

**Approach:**
- Use an LLM (Claude via Anthropic API -- I have an API key). Default model: `claude-sonnet-4-5` or current equivalent -- confirm latest before coding.
- For each question, send the full question stem + all options + existing short explanations + correct-answer flags in a single prompt. Returning one combined response lets the model contrast correct vs. incorrect options coherently.
- Force structured JSON output: per option -> `explanation_detailed` (3-6 sentences, explains *why this option specifically is correct or incorrect in the context of this question*, not a generic definition of the service) and `related_context` (2-3 sentences linking to the underlying AWS service/concept the question tests).
- Validate JSON against a Pydantic schema before writing.
- Concurrency: `asyncio` + a semaphore (max ~5 in-flight) to respect rate limits. Resumable -- track which `question_id`s are done in a local checkpoint file so a crash doesn't redo work.
- Cost estimate before running: print total questions, est. tokens/question, est. USD. Wait for my confirmation.

## 7. Migration from SQLite

Build a `migrate_sqlite_to_supabase.py` script that:
1. Reads the SQLite dump (path passed as arg).
2. Maps old schema -> new schema (you'll need me to share the old `.schema` output -- ask for it).
3. Idempotent: safe to re-run, uses `ON CONFLICT` upserts on natural keys.
4. Wraps inserts in transactions, batches of 500.
5. Verifies counts post-migration.

## 8. Project layout (proposed)

```
.
├── streamlit_app.py            # entry point
├── pages/
│   ├── 1_Practice.py
│   ├── 2_Timed_Exam.py
│   ├── 3_Review.py
│   ├── 4_Bookmarks.py
│   └── 5_Stats.py
├── app/
│   ├── auth.py                 # Supabase auth helpers
│   ├── db.py                   # supabase client (cached)
│   ├── queries.py              # query functions, one per use case
│   ├── session.py              # exam session state machine
│   └── components/             # reusable Streamlit fragments
├── scripts/
│   ├── migrate_sqlite_to_supabase.py
│   └── regenerate_explanations.py
├── supabase/
│   ├── schema.sql
│   ├── policies.sql
│   └── seed_domains.sql
├── tests/
├── pyproject.toml              # uv or poetry -- your call
├── .streamlit/
│   └── secrets.toml.example
└── README.md
```

## 9. Constraints

- **Supabase free tier** at time of writing has limited database size, bandwidth, and may pause inactive projects -- verify current limits before designing and warn me if anything in the design risks hitting them. Keep payloads small; don't store option text in `user_answers` (just IDs).
- **Streamlit Community Cloud free tier** has cold starts and resource limits -- keep the boot path light, cache the Supabase client with `@st.cache_resource`, cache static reference data (domains, certifications) with `@st.cache_data(ttl=...)`.
- **No PII beyond email.** No payment processing in scope.
- **No commit attribution to AI tools** -- don't add Co-Authored-By or "Generated with..." lines to commits or PR descriptions.

## 10. What I want from you, in order

1. **Clarifying questions first.** Ask me anything ambiguous before writing code -- especially about the old SQLite schema, exam mode rules, and which OAuth providers I actually want enabled.
2. **Phased plan.** Outline phases (e.g. schema -> migration -> auth -> practice flow -> timed mode -> analytics -> explanation regen -> deploy) with rough effort per phase and the order you recommend.
3. **Schema + RLS policies** as the first deliverable, ready to paste into the Supabase SQL editor.
4. **Migration script** next, so I can move data and start working against real content.
5. **Streamlit skeleton** with auth working end-to-end (register, verify, login, logout, password reset) before any quiz logic.
6. **One full feature vertical at a time** after that -- pick free-practice mode first, end-to-end, then iterate.
7. **Explanation regeneration script** can run in parallel once schema is in place -- surface the cost estimate before running it on the full set.
8. **Deployment guide** as a README section with exact Streamlit Cloud + Supabase setup steps and the secrets I need to populate.

When you write code: type hints throughout, `ruff`-clean, docstrings on public functions, no over-engineering. Prefer obvious, readable Python over clever Python. When you make a non-obvious design choice, explain it in 1-2 sentences inline.

Begin with your clarifying questions.
