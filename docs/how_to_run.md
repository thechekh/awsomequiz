# How to run AWSomeQuiz

Two ways to run it: **locally** (for development / testing) and **deployed** (Streamlit Community Cloud + hosted Supabase, both free-tier).

- [Local development](#local-development)
- [Deploy to Supabase + Streamlit Community Cloud](#deploy-to-supabase--streamlit-community-cloud)
- [Troubleshooting](#troubleshooting)

---

## Local development

### Prerequisites (install once)

| Tool | Why | Install (Windows) | Install (Mac) |
|---|---|---|---|
| **Docker Desktop** | Runs the Supabase stack + the Streamlit container | <https://docs.docker.com/desktop/install/windows/> | <https://docs.docker.com/desktop/install/mac-install/> |
| **Supabase CLI** | Manages the local Supabase stack | `scoop install supabase`  or  `npm i -g supabase` | `brew install supabase/tap/supabase` |
| **uv** | Python package manager | `winget install astral-sh.uv` | `brew install uv` |
| **GNU make** *(optional)* | If you prefer `make dev` over `.\dev.ps1 dev` | `scoop install make` | preinstalled |

Make sure **Docker Desktop is running** before continuing.

### One-time setup

```powershell
# Windows
cd "C:\Users\ba4f1\Desktop\AWSomeQuiz\aws_prep 1\aws_prep"
uv sync                       # ~1 min first time (downloads Python 3.13 if missing)
.\dev.ps1 db-up               # ~5-10 min first time (downloads ~3 GB of Supabase images)
Copy-Item .env.example .env
.\dev.ps1 db-status           # prints the keys -- paste anon key into .env if it differs
.\dev.ps1 db-reset            # apply migrations + seed (~5 s)
.\dev.ps1 migrate-sqlite      # import 915 questions (~10 s)
.\dev.ps1 load-flashcards     # import 174 flashcards from questions/*.csv (~2 s)
```

```bash
# Mac / Linux
cd /path/to/awsomequiz
uv sync
make db-up
cp .env.example .env
make db-status                # paste anon key into .env if it differs
make db-reset
make migrate-sqlite
make load-flashcards
```

### Daily workflow

```powershell
# Windows
.\dev.ps1 dev                 # supabase start + db reset + migrate + run app in Docker

# Mac / Linux
make dev
```

Or, if you want faster reload (no Docker for the app):

```powershell
.\dev.ps1 app                 # uv-managed Python on host, fast reload
```

Open:

| URL | What |
|---|---|
| <http://localhost:8501> | Streamlit app |
| <http://localhost:54323> | Supabase Studio (SQL editor, table viewer, auth admin) |
| <http://localhost:54324> | Inbucket (catches signup / password-reset emails locally) |

### Stopping things

```powershell
.\dev.ps1 clean               # stop both Streamlit container and Supabase stack
```

### What to test once it's up

1. Open <http://localhost:8501> -> Sign in page.
2. **Register tab** -> email + password (>=8 chars) -> instant sign-in (email confirmations are OFF locally by default).
3. Sign out via the sidebar; sign back in to verify persistence.
4. **Forgot password tab** -> enter email -> check <http://localhost:54324> for the reset email -> click link -> set new password.
5. Click **Start a practice session** on Home -> pick "All" / 10 questions -> answer through the stream.
6. After each submit you should see every option colored correct/wrong with the detailed explanation.
7. Bookmark a question; refresh; bookmark state persists (RLS is working).
8. **Quit session** in the sidebar mid-way; reload -> Home shows a "Resume" CTA pointing at the same session.

If any step misbehaves, jump to [Troubleshooting](#troubleshooting).

---

## Deploy to Supabase + Streamlit Community Cloud

Both services have generous free tiers, no credit card required for either.

### Step 1: Push the code to GitHub

Streamlit Community Cloud deploys directly from a GitHub repo. The repo must be **public** on the free tier (or you can upgrade to a paid plan for private).

```powershell
# Create a clean working copy without the weird "aws_prep 1\aws_prep\" nesting
cd "C:\Users\ba4f1\Desktop"
mkdir awsomequiz
robocopy "AWSomeQuiz\aws_prep 1\aws_prep" awsomequiz /E /XD .venv .idea __pycache__ .ruff_cache supabase\.branches supabase\.temp /XF .env

cd awsomequiz
git init
git add .
git commit -m "Initial commit: AWSomeQuiz Phase 4"

# Create a repo on github.com (e.g. youruser/awsomequiz), then:
git remote add origin https://github.com/youruser/awsomequiz.git
git branch -M main
git push -u origin main
```

Make sure `.gitignore` is in place (it is) so `.env`, `.streamlit/secrets.toml`, and `.venv/` don't get pushed.

### Step 2: Create the hosted Supabase project

1. Sign in at <https://supabase.com> (free, GitHub login OK).
2. Click **New Project**. Pick the closest region. Choose a strong DB password and **write it down** -- you'll need it for the migration step.
3. Wait ~2 minutes for the project to provision.
4. Once green, go to **Project Settings -> API** and copy:
   - **Project URL** (e.g. `https://abcdefg.supabase.co`)
   - **`anon` public key** (the long JWT)
   - **`service_role` key** (also a JWT -- **secret**, don't commit)
5. Go to **Project Settings -> Database -> Connection string** and copy the **URI** (looks like `postgresql://postgres:<DB-PASSWORD>@db.abcdefg.supabase.co:5432/postgres`). This is for the migration script.

### Step 3: Apply schema + seed

Two ways; pick one.

**Option A: Supabase SQL editor** (no CLI needed)

In the Supabase dashboard:
1. Open **SQL Editor**.
2. Paste the contents of `supabase/migrations/0001_schema.sql`, click **Run**.
3. Paste `supabase/migrations/0002_policies.sql`, click **Run**.
4. Paste `supabase/migrations/0003_session_questions.sql`, click **Run**.
5. Paste `supabase/seed.sql`, click **Run**.

**Option B: Supabase CLI** (if you have it from local dev)

```powershell
supabase login                                        # browser auth
supabase link --project-ref abcdefg                   # the part before .supabase.co
supabase db push                                       # applies migrations
# CLI doesn't auto-run seed.sql on push; do it manually:
supabase db execute --file supabase/seed.sql
```

### Step 4: Migrate the 915 questions

Run the same migration script you used locally, but pointed at the hosted DB:

```powershell
$env:SUPABASE_DB_URL = "postgresql://postgres:<your-db-password>@db.abcdefg.supabase.co:5432/postgres"
uv run python scripts/migrate_sqlite_to_supabase.py --sqlite dumps/CLF-C02.db --certification-code CLF-C02
```

Expected output: `Verified: 915 questions, 3755 options in Postgres`.

> **Tip:** Verify in Supabase Studio (Table Editor -> `questions`) that the rows landed.

### Step 5: Configure auth in the Supabase dashboard

1. **Authentication -> URL Configuration**:
   - **Site URL:** `https://<your-app>.streamlit.app` (you'll know this URL after Step 6 -- come back and fix it then)
   - **Redirect URLs:** add `https://<your-app>.streamlit.app` and `https://<your-app>.streamlit.app/reset_password`
2. **Authentication -> Providers -> Email**:
   - Make sure **Enable email signup** is on.
   - Turn **Confirm email** ON for production (verification required before sign-in).
   - Customize the email templates if you like (the defaults work).
3. *(Optional)* **Authentication -> Providers -> GitHub**:
   - See "Enable GitHub OAuth (optional)" below.

### Step 6: Deploy to Streamlit Community Cloud

1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. Click **New app**.
3. **Repository:** select your `awsomequiz` repo.
4. **Branch:** `main`.
5. **Main file path:** `streamlit_app.py`.
6. **Python version:** 3.13 (under Advanced settings). If 3.14 appears, that works too -- `requires-python` allows up to 3.14.
7. Under **Advanced settings -> Secrets**, paste:
   ```toml
   SUPABASE_URL = "https://abcdefg.supabase.co"
   SUPABASE_ANON_KEY = "eyJ... your anon key ..."
   APP_SITE_URL = "https://<your-app>.streamlit.app"
   ```
   (No `SUPABASE_DB_URL` here -- that's only needed for the migration script.)
8. Click **Deploy**. First build takes ~3 minutes.
9. Once live, copy the URL (e.g. `https://awsomequiz-yourname.streamlit.app`).
10. **Go back to Step 5** and update Supabase's Site URL + Redirect URLs to match.

### Step 7: Smoke-test prod

1. Open your Streamlit app URL.
2. **Register** with a real email address.
3. Check your inbox for the verification email (real email this time, not Inbucket).
4. Click the link -> verified. Return to the app, sign in.
5. Click **Start a practice session**, run through 10 questions, finish.
6. In Supabase Studio (Table Editor), confirm rows appeared in `exam_sessions`, `user_answers`, `question_stats`.

You're live.

### Enable GitHub OAuth (optional)

GitHub OAuth is the easiest social provider to wire up -- no consent screen / app verification dance like Google requires.

1. **GitHub OAuth App** (<https://github.com/settings/developers>):
   - Click **New OAuth App**.
   - **Application name:** anything (e.g. `AWSomeQuiz`)
   - **Homepage URL:** your Streamlit URL (e.g. `https://<your-app>.streamlit.app`)
   - **Authorization callback URL:** `https://<your-project>.supabase.co/auth/v1/callback` (the *Supabase* callback, not your app)
   - Click **Register application**.
   - Copy the **Client ID** -> click **Generate a new client secret** -> copy that too.
2. **Supabase dashboard -> Authentication -> Providers -> GitHub**:
   - Enable.
   - Paste Client ID + Client secret.
   - Save.
3. The Sign-in-with-GitHub button on the Login page calls `get_github_oauth_url()`, which always returns a URL -- so the button is always shown. Validation actually happens server-side: if GitHub is enabled in Supabase, clicking goes through; if not, Supabase returns a 400 error to the user. **Configure step 2 before publishing the page.**
4. Test: click **Sign in with GitHub** -> redirects to GitHub authorize page -> "Authorize <your-app>" -> back to your app, signed in.

### Updating the deployment

After the initial deploy, any `git push` to the `main` branch triggers Streamlit Cloud to redeploy (~30-60 s). Supabase schema changes require running migrations again (Step 3) before redeploying.

---

## Maintenance

Once you've shipped, these are the recurring tasks.

### Applying a new migration to prod

When you add a `supabase/migrations/0005_*.sql`:

```powershell
# Option A: paste the new file into Supabase SQL editor and run
# Option B: via CLI
supabase login                              # if not already
supabase link --project-ref <ref>           # one-time per workstation
supabase db push                             # applies all new migrations
```

Then redeploy Streamlit (just `git push` -- nothing to do on the Streamlit Cloud side as long as code already references the new schema).

### Rotating Supabase keys

If your `service_role` or `anon` key leaks (e.g. accidentally committed):

1. **Supabase dashboard -> Project Settings -> API -> Refresh JWT secret**. This rotates BOTH keys simultaneously. Every signed-in user will be logged out on their next API call.
2. Paste the new `anon` key into **Streamlit Cloud -> App settings -> Secrets** (`SUPABASE_ANON_KEY`).
3. Streamlit Cloud picks up secret changes within ~30s without a redeploy.
4. Locally, run `supabase status` for the local CLI keys (they're separate and don't rotate when you rotate prod).

### Free-tier limits to watch

| Service | Limit | What happens if you hit it |
|---|---|---|
| **Supabase free** | 500 MB DB / 5 GB egress per month / project pauses after 7 days idle | DB capped: writes fail with quota error. Egress capped: reads start returning errors. Paused: hit the **Restore project** button in the dashboard |
| **Streamlit Cloud free** | 1 GB RAM / app sleeps after ~10 min idle / public repos only | RAM: app OOM-crashes silently. Idle: ~30 s cold start on next visit. Private repo: need paid tier |

For a hobby CLF-C02 study tool with <100 users, you'll likely never hit these. The schema is small (~1 MB for 915 questions + per-user stats) and per-user activity is bounded.

### Monitoring

Free options:
- **Supabase logs**: dashboard -> Logs -> Postgres / API / Auth. Filter by status code to find errors.
- **Streamlit Cloud logs**: app dashboard -> Manage app -> Logs. Streams stdout/stderr.
- **Inbucket** is local-only; in prod, Supabase sends real emails via its built-in SMTP relay. To use your own SMTP (recommended once you have >10 users so it doesn't go to spam): **Supabase -> Authentication -> Email Settings -> Custom SMTP**.

### Loading questions for an additional certification

All 13 AWS certs already exist as rows in `public.certifications` (seeded by
`supabase/migrations/0007_more_certifications.sql` + `seed.sql`). The picker
on the Login page + sidebar filters to certs that have at least one active
question via `list_certifications_with_questions()`, so a cert is invisible
to users until you load its question bank:

1. Get a SQLite dump matching the existing `tests / test_questions / questions / answer_options` shape (or a JSON file in the project's import format).
2. (Optional) `INSERT INTO domains (certification_id, code, name, weight, display_order)` for the cert's official domain weights.
3. Run `migrate_sqlite_to_supabase.py --sqlite dva.db --certification-code DVA-C02` (or the JSON loader, when one exists).

That's it -- once at least one row lands in `questions` for that cert, it
shows up in the picker. The runner / session / stats code reads through
`get_current_certification()` so no per-cert hardcoding is needed.

### Migrating from CLF-C02 to a refreshed dump

If AWS updates CLF-C02 questions and you have a fresh SQLite:

1. Re-run `migrate_sqlite_to_supabase.py` against prod -- it upserts on `(certification_id, external_id)` so existing questions get refreshed text + explanations.
2. Questions removed from the new dump aren't auto-deleted; manually `UPDATE questions SET is_active = false WHERE external_id IN (...)` in SQL editor.
3. Bookmarks / stats / user_answers all keep pointing at the question UUIDs (which don't change on re-import), so user history survives.

---

## Troubleshooting

### Local

| Symptom | Fix |
|---|---|
| `supabase: command not found` | Reinstall via scoop / brew / npm and reopen the shell |
| `Cannot connect to the Docker daemon` | Start Docker Desktop; wait for the whale icon to settle |
| `Permission denied` running `.\dev.ps1` | `Set-ExecutionPolicy -Scope Process Bypass` |
| First `supabase start` hangs forever | First-time image pull is large; let it run, or `Ctrl+C` and check `docker ps` |
| App: "Could not reach Supabase" | Verify `SUPABASE_URL` / `SUPABASE_ANON_KEY` in `.env` against `supabase status` output |
| Migration fails: "Certification with code 'CLF-C02' not found" | Run `.\dev.ps1 db-reset` first so `seed.sql` runs |
| Practice page shows "No questions match" | Run `.\dev.ps1 migrate-sqlite` |
| Flashcards page shows "No flashcard decks loaded yet" | Run `.\dev.ps1 load-flashcards` |
| Sidebar shows "Signed in as None" | Stored session is stale; sign out via sidebar, sign in again |
| Container can't see Supabase (Linux only) | Compose file has `extra_hosts: host-gateway`; on truly old Docker, swap to `--network=host` |

### Deployment

| Symptom | Fix |
|---|---|
| Streamlit Cloud build fails: "ModuleNotFoundError: ..." | Check Python version is 3.13+ in Advanced settings; verify the missing package is in `pyproject.toml` |
| Streamlit Cloud build fails: "Python (X.Y.Z) is not compatible with the locked Python requirement: `>=3.13`" | Advanced settings -> Python version -> 3.13 (or 3.14) -> Reboot app |
| App loads but "SUPABASE_URL must be set" | Re-check Streamlit Cloud secrets (they're TOML; quote strings) |
| Sign-up email never arrives | Supabase free-tier sends from a generic address that often goes to spam. Check spam. To use your own SMTP, configure in **Supabase -> Authentication -> Email Settings** |
| Verification link 404s back to your app | The link's `redirect_to` doesn't match the **Redirect URLs** allow-list in **Supabase -> Authentication -> URL Configuration**. Add it. |
| GitHub OAuth: "redirect_uri mismatch" or "The redirect_uri MUST match the registered callback URL" | Set the GitHub OAuth App's **Authorization callback URL** to exactly `https://<your-project>.supabase.co/auth/v1/callback` -- no trailing slash, no path |
| GitHub OAuth: 400 "Unsupported provider: provider is not enabled" | Enable GitHub in Supabase dashboard -> Authentication -> Providers -> GitHub. Then save Client ID + secret from the GitHub OAuth App. |
| Supabase project "paused" message | Free-tier projects pause after 7 days of inactivity. Click **Restore project** in the dashboard. Practice + auth resume immediately |
| App is slow / cold-starts | Streamlit Community Cloud spins down idle apps. First hit after ~10 min idle takes ~30 s. Pay tier ($$) for always-on |

### Resetting from scratch

**Local:**
```powershell
.\dev.ps1 clean               # stop everything
supabase stop --no-backup     # nuke local data
```

**Hosted Supabase:**
- Drop tables: `drop schema public cascade; create schema public; create extension if not exists "pgcrypto";` in SQL Editor, then re-run migrations + seed + migration script.

**Streamlit Cloud:**
- Settings tab on the app -> **Delete app**. Reuse the URL by giving the new deployment the same name.
