# AWSomeQuiz

Multi-user CLF-C02 (AWS Certified Cloud Practitioner) practice platform.
Streamlit frontend, Supabase backend (Postgres + Auth), Docker for local dev.

> **Status:** Feature-complete (Phases 1-7). Phase 8 is production deploy verification -- the walkthrough lives in [docs/how_to_run.md](docs/how_to_run.md). See [CLAUDE.md](CLAUDE.md) for the roadmap and [docs/BRIEF.md](docs/BRIEF.md) for the original product brief.

## Features
- Email/password + Google OAuth (toggleable) via Supabase Auth
- **Free practice** mode: pick domain + count, per-question feedback with detailed explanations
- **Timed exam** simulation: 65 questions / 90 minutes / 70% pass, with countdown + end-of-exam review
- **Weak areas** / **Missed questions** review modes
- **Bookmarks** for hard questions
- **Anki-style flashcards**: 5 decks (Basics / WAF / CAF / Migration 6Rs / AWS Services) loaded from CSV
- **Stats dashboard**: accuracy, streaks, per-domain breakdown, score history
- Resumable sessions across browser restarts

---

## Test it locally (step-by-step)

### 0. One-time prereqs

Install if you don't already have them:

| Tool | Why | Install (Windows) |
|---|---|---|
| **Docker Desktop** | Runs the Supabase stack + the Streamlit container | https://docs.docker.com/desktop/install/windows/ |
| **Supabase CLI** | Manages the local Supabase stack | `scoop install supabase`  *or*  `npm i -g supabase` |
| **uv** | Python package manager (replaces pip + venv) | `winget install astral-sh.uv`  *or*  `irm https://astral.sh/uv/install.ps1 \| iex` |
| **GNU make** *(optional)* | If you prefer `make dev` over `.\dev.ps1 dev` | `scoop install make` |

Make sure Docker Desktop is **running** before continuing.

### 1. Install Python deps

```powershell
cd "C:\Users\ba4f1\Desktop\AWSomeQuiz\aws_prep 1\aws_prep"
uv sync
```

First run downloads Python 3.13 if missing (~1 min) and installs streamlit + supabase + psycopg + pydantic.

### 2. Boot the local Supabase stack

```powershell
.\dev.ps1 db-up
# equivalent: supabase start
```

**First run downloads ~9 Docker images (~3 GB, 5-10 min on a fast link).** Subsequent runs take ~30 s.

When it finishes you'll see something like:

```
Started supabase local development setup.
         API URL: http://localhost:54321
     GraphQL URL: http://localhost:54321/graphql/v1
          DB URL: postgresql://postgres:postgres@localhost:54322/postgres
      Studio URL: http://localhost:54323
    Inbucket URL: http://localhost:54324
      JWT secret: super-secret-jwt-...
        anon key: eyJhbGciOiJI...
service_role key: eyJhbGciOiJI...
```

### 3. Populate `.env`

```powershell
Copy-Item .env.example .env
.\dev.ps1 db-status   # prints the keys again if you missed them
```

Open `.env` and replace `SUPABASE_ANON_KEY=...` with the **anon key** printed by `supabase status`. The default `.env.example` value works for most Supabase CLI versions but isn't guaranteed identical to yours.

### 4. Apply schema + seed

```powershell
.\dev.ps1 db-reset
# equivalent: supabase db reset
```

This drops the local DB, replays `supabase/migrations/0001_schema.sql` + `0002_policies.sql`, then runs `supabase/seed.sql` (which inserts the CLF-C02 certification + 4 domains). Takes ~5 s.

### 5. Migrate the SQLite questions into Postgres

```powershell
.\dev.ps1 migrate-sqlite
```

Expected output:

```
Reading SQLite dump: dumps\CLF-C02.db
  Parsed: 915 questions (91 multi-answer), 3755 options

Connecting to Postgres: postgresql://postgres:***@localhost:54322/postgres
  Certification 'CLF-C02' -> <uuid>

Upserting 915 questions in batches of 500...
Upserting 3755 options in batches of 500...
  Wrote 3755 option rows

Verifying counts...
  Verified: 915 questions, 3755 options in Postgres

Done.
```

### 6. Run the Streamlit app

Pick **one**:

```powershell
# Option A: in Docker (mirrors prod, slower first build)
.\dev.ps1 app-docker

# Option B: on the host (faster reload, easier debugging)
.\dev.ps1 app
```

Open <http://localhost:8501>. You should see:

- **Certification:** CLF-C02
- **Questions migrated:** 915
- **Pass threshold:** 70%
- A table of 4 domains with weights summing to 100.

### 7. Verify via Studio (optional but recommended)

Open <http://localhost:54323>. Click **SQL Editor** in the sidebar and run:

```sql
-- Counts
SELECT COUNT(*) AS questions FROM public.questions;          -- expect 915
SELECT COUNT(*) AS options   FROM public.options;            -- expect 3755

-- Multi-answer detection
SELECT type, COUNT(*) FROM public.questions GROUP BY type;
-- expect: single 824, multiple 91

-- Domains
SELECT name, weight, display_order FROM public.domains ORDER BY display_order;
-- expect 4 rows, weights 24 / 30 / 34 / 12

-- Spot-check explanations are populated
SELECT label, is_correct, LEFT(explanation_detailed, 80) AS expl
FROM public.options
WHERE question_id = (
  SELECT id FROM public.questions
  WHERE external_id = '1' AND certification_id = (SELECT id FROM public.certifications WHERE code = 'CLF-C02')
)
ORDER BY label;
```

### 8. Idempotency check (optional)

Re-run the migration — it should be a no-op besides updating `updated_at`:

```powershell
.\dev.ps1 migrate-sqlite
# counts unchanged: 915 questions, 3755 options
```

### 9. Tear down

```powershell
.\dev.ps1 clean
# stops Streamlit container + supabase stack
```

---

## Test Phase 3 (auth) locally

After steps 1-6 above, you should see the **Sign in** page at http://localhost:8501 instead of the smoke-test landing.

### Register + sign in (instant flow)

By default `enable_confirmations = false` in `supabase/config.toml`, so signups are instant -- no email click needed.

1. Open http://localhost:8501.
2. Click the **Register** tab. Enter `test@example.com` + a >=8 char password. Click **Create account**.
3. You'll be auto-signed in and bounced to **Home** (shows your email + the migrated catalog).
4. Verify the profile auto-trigger fired -- open Studio (http://localhost:54323) -> SQL Editor:
   ```sql
   SELECT id, email FROM auth.users;            -- your new account
   SELECT id, username, created_at FROM public.profiles;  -- one row, username = email-local-part
   ```

### Sign out + sign in again

1. In the sidebar, click **Sign out**. You're back on Sign in.
2. Sign in with the same email + password. Lands on Home again.

### Forgot password (Inbucket flow)

1. Sign out. Click the **Forgot password** tab. Enter your email. Click **Send reset link**.
2. Open Inbucket: http://localhost:54324. Click the mailbox for your email.
3. Open the **Reset Password** email. The body contains a link like `http://localhost:54321/auth/v1/verify?token=...&type=recovery&redirect_to=http://localhost:8501/reset_password`.
4. Click the link. You land on the **Set a new password** page in the app.
5. Enter a new password (>=8 chars). Click **Update password**. You're now signed in with the new credentials.

### Test email verification (optional -- mirrors prod)

To test the full verification flow:

1. Edit `supabase/config.toml`: `[auth.email] enable_confirmations = true`.
2. `.\dev.ps1 db-down && .\dev.ps1 db-up` (restart Supabase to pick up the config).
3. Register a NEW account. You'll see "Account created ... check your email."
4. Open Inbucket -> click the **Confirm your signup** email -> click the link.
5. You're verified. Go back to the app, sign in.

Then flip `enable_confirmations` back to `false` for daily dev.

### Test Google OAuth (optional)

The Sign-in-with-Google button is disabled by default because no Google Cloud OAuth client is configured. To enable:

1. Create a Google Cloud project at https://console.cloud.google.com/
2. Enable the "Google+ API" (or just the OAuth consent screen)
3. Create OAuth 2.0 credentials -> Web application
   - Authorized redirect URI: `http://localhost:54321/auth/v1/callback` (local)
   - Add `https://<your-project>.supabase.co/auth/v1/callback` later for prod
4. Copy the client ID and secret into your `.env`:
   ```
   SUPABASE_AUTH_EXTERNAL_GOOGLE_CLIENT_ID=...
   SUPABASE_AUTH_EXTERNAL_GOOGLE_SECRET=...
   ```
5. Edit `supabase/config.toml`: `[auth.external.google] enabled = true`.
6. `.\dev.ps1 db-down && .\dev.ps1 db-up` to restart.
7. The Sign-in-with-Google button is now active. Clicking it redirects to Google -> back to the app -> signed in.

---

## Daily workflow

Once everything above works, the one command is:

```powershell
.\dev.ps1 dev    # or: make dev
```

Runs all of `db-up` -> `db-reset` -> `migrate-sqlite` -> `app-docker` in sequence. Note: `db-reset` **wipes user data each time**, so swap to `.\dev.ps1 db-up && .\dev.ps1 app-docker` once you have auth flows you don't want to nuke (Phase 3+).

| URL | What |
|---|---|
| http://localhost:8501 | Streamlit app |
| http://localhost:54321 | Supabase API (REST + Auth) |
| http://localhost:54322 | Postgres (direct connection) |
| http://localhost:54323 | Supabase Studio (admin UI) |
| http://localhost:54324 | Inbucket (catches signup/reset emails locally) |

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `supabase: command not found` | Reinstall via scoop/npm and reopen the shell so PATH updates |
| `Cannot connect to the Docker daemon` | Start Docker Desktop, wait for the whale icon to stop animating |
| `Permission denied` running `.\dev.ps1` | `Set-ExecutionPolicy -Scope Process Bypass` for the current shell |
| Streamlit shows "Could not reach Supabase" | Check `supabase status`; verify `SUPABASE_URL` and `SUPABASE_ANON_KEY` in `.env` |
| Migration fails: "Certification with code 'CLF-C02' not found" | Run `.\dev.ps1 db-reset` first so `seed.sql` runs |
| `host.docker.internal` doesn't resolve inside Streamlit container (Linux) | The compose file already includes `extra_hosts: host-gateway`; on truly old Docker, replace with `--network=host` |
| First `supabase start` hangs forever | First-time image pull is large — let it run, or `Ctrl+C` and check `docker ps` |

---

## Project layout

```
.
├── streamlit_app.py             # Auth gate + multi-page router via st.navigation
├── pages/
│   ├── login.py                 # Sign in / Register / Forgot password / Google OAuth
│   ├── home.py                  # Dashboard with resume CTAs + quick-start
│   ├── practice.py              # Free practice mode
│   ├── timed_exam.py            # 65Q / 90min CLF-C02 simulation
│   ├── review.py                # Weak areas + Missed questions tabs
│   ├── bookmarks.py             # Saved-questions list + practice
│   ├── flashcards.py            # Anki-style: deck picker -> flip-to-reveal runner
│   ├── stats.py                 # Accuracy, streak, score history dashboard
│   ├── account.py               # Profile + change password + sign out
│   └── reset_password.py        # Target for password-reset email link
├── app/
│   ├── auth.py                  # Supabase auth helpers (PKCE flow)
│   ├── db.py                    # Cached Supabase client
│   ├── queries.py               # Reference data + per-mode question selection + stats
│   ├── session.py               # Start / record / complete / abandon session lifecycle
│   └── components/runner.py     # Reusable per-question runner
├── scripts/
│   ├── migrate_sqlite_to_supabase.py
│   └── load_flashcards.py       # questions/*.csv -> flashcard_decks/flashcards
├── questions/                   # CSV sources for flashcard decks
│   ├── basic.csv
│   ├── aws_framework.csv        # WAF / CAF / Migration Strategies
│   └── aws_service.csv          # ~155 AWS service definitions
├── supabase/
│   ├── config.toml              # Supabase CLI config
│   ├── migrations/
│   │   ├── 0001_schema.sql      # 10 tables + RLS-ready
│   │   ├── 0002_policies.sql    # RLS on every table
│   │   ├── 0003_session_questions.sql
│   │   ├── 0004_stats_handle_updates.sql
│   │   └── 0005_flashcards.sql  # flashcard tables + RLS + stats trigger
│   └── seed.sql                 # CLF-C02 + 4 domains (auto-run on db reset)
├── docker/Dockerfile            # Streamlit container
├── docker-compose.yml           # Streamlit service (Supabase runs via CLI)
├── Makefile / dev.ps1           # One-command orchestration
├── dumps/CLF-C02.db             # Source SQLite (915 questions)
├── docs/
│   ├── BRIEF.md                 # Original product brief
│   └── how_to_run.md            # Local + deploy walkthrough + maintenance guide
├── tests/test_imports.py        # Smoke test: every module imports cleanly
├── requirements.txt             # Streamlit Cloud dep manifest (mirrors pyproject)
├── pyproject.toml               # uv project + ruff config
└── CLAUDE.md                    # Agent guide + phase roadmap
```

## Deploy to production

See [docs/how_to_run.md § Deploy](docs/how_to_run.md#deploy-to-supabase--streamlit-community-cloud) for the end-to-end walkthrough (hosted Supabase + Streamlit Community Cloud, both free-tier).
