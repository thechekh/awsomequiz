# Playwright Audit — Pre-Share Final Check (2026-05-28)

End-to-end audit of [awsomequiz.streamlit.app](https://awsomequiz.streamlit.app)
driven through the Playwright MCP. Goal: catalog everything broken or rough
before sharing the app with other people. Severity uses 🔴 (broken/blocking
share), 🟡 (rough, fix before launch), 🟢 (verified working).

**Scope note** — audit ran against the live Streamlit Cloud deploy rather
than the local Docker stack. The deployed app is what users will see and
hits a quirk-rich path (Streamlit Cloud cookie proxy, free-tier latency)
the local stack can't reproduce. Two existing accounts were used:
`danylo.chekh@chisw.com` (email/password) and `thechekh` (GitHub OAuth →
`chekhwork@gmail.com`). The forgot-password flow was **not** exercised
end-to-end (would require access to a real inbox; Inbucket isn't reachable
on Streamlit Cloud).

---

## 1. Code / Functional

### 🔴 Blocking

| Sev | Area | Finding | Repro | File |
|:-:|---|---|---|---|
| 🔴 | Auth: Register | Duplicate-email registration shows **"Account created… (Locally: http://localhost:54324 --Inbucket.)"** in prod. Inbucket is a dev-only service; the localhost URL leaks to real users, and Supabase's enumeration-prevention message ("Account created" for an email that already exists) reads as a flat success — confusing UX. | Sign out, /, Register tab, enter `danylo.chekh@chisw.com` + any password ≥8 chars + matching confirm, Create account. | [pages/login.py:120-123](pages/login.py#L120-L123) |
| 🔴 | Mobile UX | At 375px viewport the **sidebar auto-expands and overlays ~244 of 375 px** of the screen on every authenticated page load. The expand-button click in `streamlit_app.py:282-309` was added because the unauth → auth transition leaves the sidebar collapsed; on mobile the same script forces it open even though that's the wrong default. Net effect: a phone user lands on Home with the sidebar covering 65% of the content. | Sign in. Resize to 375×812. Reload `/`. Sidebar is open over the main column. | [streamlit_app.py:282-309](streamlit_app.py#L282-L309) |

### 🟡 Needs improvement

| Sev | Area | Finding | Repro | File |
|:-:|---|---|---|---|
| 🟡 | Timed exam | When the deadline passes while the tab is closed and the user re-opens later, the auto-submit fires correctly **but the summary reports a bogus duration** ("Time spent: **524m 19s**" for a 90-min exam). `complete_session` uses `now - started_at` without capping at `cert.duration_minutes`. | Start a timed exam, close the tab, wait > 90 min, come back to `/timed_exam`. Look at the summary's "Time spent". | [app/session.py](app/session.py) `complete_session` |
| 🟡 | Bookmarks | Per-row timestamp renders raw ISO: `Bookmarked 2026-05-28T11:18:14.295085+00:00`. Should be formatted (e.g. `Bookmarked 2026-05-28 11:18`) like the session-history table does via `format_started_at`. | `/bookmarks`. Look at the "Bookmarked …" caption on each row. | [pages/bookmarks.py:110](pages/bookmarks.py#L110) |
| 🟡 | Flashcards | The **AWS Basics deck has only 1 card** because `questions/basic.csv` ships with a single data row. The other decks are fine (WAF 6, CAF 6, Migration 6, Services 155). Either backfill basic.csv or rename the deck so users don't expect more. | `/flashcards`, look at the Basics row card count. | data: [questions/basic.csv](questions/basic.csv) |
| 🟡 | Stats | "Recent sessions" table rows aren't clickable — can't drill into a past session's per-question review even though `get_review_bundle(session_id)` already exists. Low-effort missing feature. | `/stats`, click a row in the table. Nothing happens. | [pages/stats.py:157-178](pages/stats.py#L157-L178) |
| 🟡 | Stats — sidebar mini-stats | Sidebar mini-stats show **47.8% accuracy** while Stats page reports the same. Cross-check ✅. **But** the mini-stats show a one-render delay after a question is answered (cache TTL=30s on `get_user_stats_summary`). Documented; minor. | Answer a question; refresh; sidebar still shows pre-answer values for ~30s. | [streamlit_app.py:73-110](streamlit_app.py#L73-L110) |
| 🟡 | Account page | The `Username` text input has placeholder help "Shown on the leaderboard once that lands. Must be unique." but **the username is never actually displayed** anywhere in the app (sidebar uses email). Either ship the leaderboard or hide the field. | `/account`. Look at the Username form. | [pages/account.py:38-58](pages/account.py#L38-L58) |
| 🟡 | Welcome line | Home shows "Welcome, danylo.chekh@chisw.com" — exposes email to anyone screen-sharing. Should fall back to `profiles.username` when set. | `/`. Look at the Welcome heading. | [pages/home.py:32](pages/home.py#L32) |

### 🟢 Verified working

| Sev | Area | Result |
|:-:|---|---|
| 🟢 | Sign in (email/password) | Wrong password → "Invalid login credentials". Empty fields → "Email and password are required." Short password on Register → "Password must be at least 8 characters." Mismatched confirm → "Passwords do not match." |
| 🟢 | Sign in (GitHub OAuth) | `thechekh` GitHub → `chekhwork@gmail.com` Supabase user. PKCE callback handled correctly; URL params cleared. |
| 🟢 | Signed-out deeplinks | `/practice`, `/stats`, `/timed_exam`, `/review`, `/bookmarks`, `/flashcards`, `/account` — all redirect cleanly to Login. No "Page not found". |
| 🟢 | Home metrics | Q count = **915**, Pass threshold = **70%**, Duration = **90 min**, Exam length = **65 Q**. Matches `certifications` row. |
| 🟢 | Home resume CTAs | Three concurrent unfinished sessions (Practice, Timed, Review) all rendered with `Resume` buttons. |
| 🟢 | Practice runner | Picker → runner; Q1/25 rendered; wrong-answer feedback shows "Incorrect.", correct-row marker, full explanation. Bookmark toggle label flips. Quit returns to picker. |
| 🟢 | Bookmarks page | "**2 bookmarked**" caption, two rows with question stems + Remove buttons + Practice-all primary button. |
| 🟢 | Review tabs | Weak areas: "892 questions eligible" (cached `_weak_area_question_ids_cached`). Missed questions tab loads. |
| 🟢 | Flashcards | All 5 decks present (Basics, WAF, CAF, Migration 6Rs, Services). Flip-to-reveal works on the Basics card; both "Need more practice" + "I knew it" buttons render. Card counter "1/1". |
| 🟢 | Stats page | 4 metric cards populate (unique=23, accuracy=47.8%, streak=1, sessions=5). PRACTICE ACCURACY TREND section visible with correct sub-25 message ("Answer at least 25 questions… So far: 23"). Per-domain bar chart and Recent sessions table both render. |
| 🟢 | Account | Profile (email + username + Save), Change password (new + confirm + Update), Sign out — all render. |
| 🟢 | Timed exam | Countdown ticks 89:42 → 89:23 over ~19s. Submit dialog fires with 0/65 unanswered warning. Cancel returns to runner. |
| 🟢 | Question report dialog | After the 0010 migration + RPC fix, submitting via the report dialog lands a row in `public.question_reports` (verified via psycopg). |
| 🟢 | Glossary | 382 of 382 entries render on both signed-in and guest views. Guest cold-load + refresh both pass (Bug-2 regression test from the previous review still ✅). |
| 🟢 | Deeplink restore (authed) | `/stats` deeplink with the cookie cold-loaded preserves URL and renders Stats. |

---

## 2. User Experience

### 🔴 Blocking

| Sev | Area | Finding |
|:-:|---|---|
| 🔴 | Mobile (375 px) | See Code §1 — sidebar overlay covers 65% of the viewport on auth pages. Phones are unusable until the user manually closes the sidebar. |

### 🟡 Needs improvement

| Sev | Area | Finding |
|:-:|---|---|
| 🟡 | Timed exam sidebar grid | 65 question buttons in a `n_per_row=5` grid render in the sidebar. On 1366 px the sidebar is ~336 px wide → buttons are ~50 px each, just barely readable. On 768 px / 375 px the buttons wrap awkwardly and "Submit exam" CTA can scroll off the bottom of the sidebar. Consider 4 per row on narrow widths or a virtualised grid. |
| 🟡 | Dark mode toggle position | At 1920 px the toggle sits in the rightmost column (good). At 375 px it's still pushed to the right of the same `st.columns([9, 2])` row, but the column ratio means the toggle ends up underneath the page H1 once content wraps. Either swap to a sidebar-only toggle on narrow widths or move to the bottom of the sidebar. |
| 🟡 | Quit confirmation | All five places that show a "Quit session" or "Abandon" button fire immediately with no confirmation. Accidental click → progress lost (although the session row stays in DB). Wrap in `@st.dialog`. |
| 🟡 | Pass celebration | Reaching 70%+ on a timed exam shows a green `st.success("PASSED — 76.92% …")` banner, no balloons / no animation. One line of code (`st.balloons()`) for big delight delta. |
| 🟡 | Recent-sessions empty state | A brand-new user lands on `/stats` with `unique_seen=0` and gets the helpful banner "Answer some questions first — charts will populate as you practice." 🟢 — but if they tap the wider trend section the "Practice accuracy trend" sub-25 hint says "So far: 0" twice in a row visually. Could be one merged empty state. |
| 🟡 | Cert picker race | After switching certs in the sidebar picker, the mini-stats panel one render keeps showing the OLD cert's accuracy before refreshing. Documented in code, not yet fixed. |
| 🟡 | Email visibility | "Welcome, danylo.chekh@chisw.com" on Home and `Signed in as danylo.chekh@chisw.com` in the sidebar both expose the user's email — uncomfortable on screen share. Already noted in §1; fix is to use `profiles.username` when set. |
| 🟡 | Streamlit dev-mode warnings in browser console | The deployed app emits "Unrecognized feature: 'ambient-light-sensor'", "Vega warnings about Accuracy %_start: [Infinity, -Infinity]", etc. Not blocking, but noisy for anyone with devtools open. |

### 🟢 Verified working

| Sev | Area | Result |
|:-:|---|---|
| 🟢 | Layout 1920×1080 | Hero stat block, section cards, sidebar — all proportions clean. |
| 🟢 | Layout 1366×768 | Slightly more compressed; still readable; no overflow. |
| 🟢 | Layout 768×1024 (tablet) | Sidebar collapses behind hamburger; main column gets full width; no horizontal scrollbar. |
| 🟢 | Layout 375 (mobile, content area) | Main column is the full viewport; no horizontal scrollbar on Home. Only blocker is the sidebar auto-expand (Bug D above). |
| 🟢 | Color palette | Blue primary / emerald correct / red incorrect / amber warning all rendering consistently. Dark mode toggle persists via cookie. |
| 🟢 | Glossary nav (guest + auth) | URL preserved, instant render, no Loading-flash regression. |
| 🟢 | st.dataframe behaviour | Recent-sessions table fits at 1920/1366, scrolls horizontally inside its container at 768/375 — no page-level overflow. |
| 🟢 | Console errors / exceptions | Zero Python tracebacks surfaced during the entire session. The 404s on `_stcore/health` / `_stcore/host-config` are Streamlit-Cloud routing artifacts and not app bugs. |

---

## 3. Fix-next shortlist (prioritised for share-ready cut)

The smallest set of changes that turns this from "looks rough on phones, has a few dev-mode leaks" into "fine to send to a friend":

1. **🔴 Stop the Inbucket localhost leak** ([pages/login.py:120-123](pages/login.py#L120-L123)) — remove the `(Locally: http://localhost:54324 --Inbucket.)` parenthetical from the Register success message and the Forgot-password success message. Two lines.
2. **🔴 Don't force-open the sidebar on mobile** ([streamlit_app.py:282-309](streamlit_app.py#L282-L309)) — guard the auto-expand script with `if (window.innerWidth >= 768)` so the click only fires on desktop/tablet. Phones keep the collapsed default and content gets full width.
3. **🟡 Cap timed-exam duration at the cert's `duration_minutes`** ([app/session.py](app/session.py) `complete_session`) — `min(now - started_at, duration_minutes * 60)` for the displayed time. Stops the "524m" report.
4. **🟡 Format bookmark timestamps** ([pages/bookmarks.py:110](pages/bookmarks.py#L110)) — pass `bm['created_at']` through `format_started_at`. One line.
5. **🟡 Welcome line + sidebar label use `profiles.username` when set** ([pages/home.py:32](pages/home.py#L32), [streamlit_app.py:311-312](streamlit_app.py#L311-L312)) — fall back to email-local-part. Two small reads.
6. **🟡 Wrap "Quit session" + "Abandon" in `@st.dialog`** — five callsites: practice/review/bookmarks/timed_exam/flashcards. ~30 LOC total.
7. **🟢 (delight) `st.balloons()` on first pass** ([pages/timed_exam.py:127](pages/timed_exam.py#L127)) — gate behind a `summary["passed"] and is_first_pass_today` check.

Items 1-2 are the actual "before share" blockers. 3-5 are quick wins. 6-7 are polish. Estimate: 1-2 hours of focused work for all seven.

## 4. Out of scope / monitor-only

Things that came up but don't gate sharing:

- Spaced-repetition scheduling for missed/weak (already deferred — see REVIEW_2026-05-28 §3.3).
- Per-question notes (already deferred).
- Domain tagging accuracy for CLF-C02 (~85-90% via keyword heuristic; remaining ~10% sit in Untagged and the chart handles them).
- Multi-answer question UX probe (skipped during this run; would have needed multiple practice rounds to land on a multi-answer question; the runner code path is identical between single/multi, so a code review is sufficient — no UI changes since the previous review).
