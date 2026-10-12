# CareerWatch Web App — Product Spec

## Overview

CareerWatch is a self-serve job-matching platform. A user provides their CV, fills out a profile (with AI assistance), sets their filters, and the system continuously scrapes VC portfolio companies, collects open positions, and scores them against the user's profile using their own Gemini API key. The user sees a ranked digest of relevant positions and can mark what they've applied to.

The product is free. Users bring their own Gemini API key. The platform absorbs the infrastructure cost of scraping and collection; scoring runs on the user's quota.

---

## Users

Single persona: a job-seeking professional (primarily technical — data scientist, ML engineer, security researcher). Non-technical users are out of scope for v1.

---

## Core User Journey

1. Land on marketing page → understand what the product does in 10 seconds
2. Sign up with email
3. Generate a `profile.md` using an AI prompt (copy prompt → paste into ChatGPT/Claude/Gemini → paste result back), upload an existing profile document, or paste text — optional, can be added later in Settings
4. Upload CV (upload a document or paste text) — optional, can be added later in Settings
5. Enter Gemini API key
6. Configure filters (location, title denylist/allowlist, company exclusions)
7. Trigger first scoring run → see digest
8. Return periodically → new positions appear at the top
9. Mark positions as applied → they disappear from the active list

---

## Pages & Screens

### 1. Landing Page (`/`)

- Hero: one-line value prop + CTA ("Get started free")
- How it works: 3-step visual (Set up profile → System scrapes jobs → You get a ranked digest)
- "Built with your own AI key — your data never trains a model"
- Footer: GitHub link, author credit

### 2. Sign Up / Log In (`/auth`)

- Email + password
- Google OAuth
- No credit card, no plan selection

### 3. Onboarding Flow (first-time user, 4 steps)

**Step 1 — Generate your profile (optional)**
- Explanation: "Your profile tells the AI what you're looking for. The best way to create it is to use an AI assistant."
- Optional: the user can skip and add a profile later in Settings. The Next button reads "Skip ->" when the field is empty and "Next ->" once filled. (Note: scoring still requires a profile, so a skipped profile means no results until one is added.)
- A copyable prompt block:
  ```
  I'm setting up a job-matching tool that scores job postings against my profile.
  I need you to create a profile.md file for me by asking me questions about:
  - My background and years of experience
  - My target roles (title, seniority)
  - My preferred domains/industries
  - What I consider a strong fit vs. a dealbreaker
  - My location and commute constraints
  - What I explicitly don't want
  
  Ask me one section at a time. When done, output a complete profile.md in markdown.
  ```
- Paste result into a text area → save (no longer gated on non-empty content)
- "Already have a profile.md?" — skip to paste

**Step 2 — Upload your CV (optional)**
- Upload PDF or paste plain text
- CV is stored and used verbatim in scoring prompts
- Optional: the user can skip and add a CV later in Settings. The Next button reads "Skip ->" when empty and "Next ->" once filled.

**Step 3 — Gemini API key**
- Input field (masked)
- Prominent note: "It's fully free - Google's Gemini API has a free tier that's plenty for scoring jobs." with a direct "Get your free key here" link to https://aistudio.google.com/apikey
- "How to get a Gemini API key" expandable explanation:
  - Go to [Google AI Studio](https://aistudio.google.com)
  - Sign in with your Google account
  - Click "Get API key" → "Create API key"
  - Copy and paste the key here
  - The free tier is enough to get started (quota resets daily)
- Key is encrypted at rest, never logged, never shared
- Small note: "We never score jobs without your key. If you delete your key, scoring stops."

**Step 4 — Configure filters**
- **Location**: text input — what city/region terms to require in job location (e.g. "israel", "tel aviv"). Leave blank = no location filter.
- **Title denylist**: tags input — terms that auto-exclude a job title (e.g. "data engineer", "analyst"). Pre-populated with sensible defaults, fully editable.
- **Title allowlist**: tags input — at least one term must appear in the title for a job to be scored. Leave blank = score everything that passes denylist.
- **Excluded companies**: tags input — company names to skip entirely.
- **Excluded industries**: tags input — industry keywords to skip entirely (e.g. "gaming", "adtech", "gambling", "crypto"). Jobs whose company or description matches any term are dropped before scoring.
- Preview: "With these filters, X of today's Y collected jobs would be sent to Gemini."

→ "Start my first scoring run" → triggers scoring job in background → redirects to digest

---

### 4. Digest (`/digest`)

Main screen. Seen every return visit.

**Header bar:**
- Last scored: "2 days ago" | Next collection: "Tomorrow"
- "Score now" button (enabled if within weekly limit; shows "2 of 2 runs used this week" when exhausted)
- Settings icon

**Position cards** (sorted by score desc, then date desc):

```
┌─────────────────────────────────────────────────────────────┐
│ 9/10   Cato Networks — Research Team Lead                   │
│ Tel Aviv · Comeet · Scored today                            │
│ "Strong fit for security ML lead role with production       │
│  ownership. Team8-backed, clear leadership path."           │
│ [threat-detection] [team-lead] [tier1-vc]                  │
│                              [Apply →]  [Mark as Applied ✓] │
└─────────────────────────────────────────────────────────────┘
```

- Scores 9-10: green accent
- Scores 7-8: blue accent
- Scores 5-6: grey
- Applied positions: collapsed into "X applied — show" at the bottom
- Positions scored before the current profile version: soft badge "scored with old profile"

**Job detail view:** clicking a card body (or its "Details" button) opens a
slide-over panel with the full un-clamped reasoning, score + tier band, all
flags with their glossary definitions, Apply / Mark-applied actions, and the
full job description. The description is persisted onto `scored_jobs` at score
time (migration `006_scored_jobs_description.sql`); rows scored before the
migration fall back to the shared `positions.description` (migration 008) by `apply_url`,
and a missing description degrades to a "Full description unavailable" note
with the Apply link. Served by `GET /jobs/{id}`; the digest list endpoint
selects explicit columns so descriptions never bloat the list payload.

**Filters sidebar** (collapsible):
- Filter by score (slider: show ≥ N)
- Filter by date scored
- Search by company or title

**Instant load (stale-while-revalidate cache):** Digest (`/jobs` list) and
Positions (`/jobs/positions` list) paint the last-seen list from `localStorage`
on mount, then refetch in the background (`webapp/frontend/lib/swrCache.ts`).
- Key `cw:swr:<jobs|positions>:<supabase user id>`, value
  `{ v, savedAt, userId, data }`. No session user id -> no cache read.
- Discarded (and removed) on version mismatch, `userId` mismatch, age over the
  ceiling (4 days = the longest gap between collection runs, Thu -> Mon), a
  future `savedAt`, or unparseable JSON. Bump `JOBS_CACHE_VERSION` /
  `POSITIONS_CACHE_VERSION` in the page whenever the row shape changes.
- Cache hit: no skeleton, a quiet "Updating..." while the refetch runs; on
  failure the cached list stays with "Couldn't refresh - ... Retry". Cold cache:
  skeleton as before. Written only from live data, so a failed refresh never
  re-stamps stale data as fresh. `/user/me` and `/jobs/stats` stay live-only.
- All `cw:swr:` keys are cleared on sign-out (nav + delete account).
- Node unit test: `node --test webapp/frontend/tests/swrCache.test.mjs`.

---

### 4b. Positions (`/positions`)

The **shared, unscored catalog** of every open role currently pulled from the
pipeline — one copy for ALL users. This is the counterpart to the Digest: the
Digest is your personalized *scored output*; Positions is the raw *market*, so a
brand-new user with no profile or scoring still sees all open roles.

- Source: the global `positions` table (NOT the per-user `scored_jobs` table).
  Backed by `GET /jobs/positions`, which reads the shared table without scoping
  by user and returns `score: null` for every row.
- Per-row: company, title, location. No score, no ranking.
- Clicking a row opens an in-app detail slide-over (shared `DetailPanel` shell,
  same chrome as the Digest job detail) showing the position's company, title,
  and location plus a **Go to posting →** link out to the original ATS page.
  The shared catalog stores no description, so the panel notes that and points
  to the posting; a row with no `apply_url` still opens but omits the link.
  Closed positions stay dimmed and non-interactive.
- Sorted by company, then title. Client-side search + pagination (50/page).
- Populated by `scripts/sync_positions.py` from `new_jobs.json` on each collect
  run (upsert live set + prune stale, incl. `description` from migration 008) — see
  Scheduling below.
- The backend never reads `new_jobs.json` (gitignored, absent on Render). `POST /score/`,
  filter preview, company counts and `/jobs/stats` all read the `positions` table
  (paginated, 1000 rows/request). `/jobs/stats` also returns `last_collected_at`
  (max `positions.synced_at`) and `last_scored_at`, shown in the Digest header as
  "Last collected <local date, time> · next run <Mon|Thu>".

---

### 5. Settings (`/settings`)

Tabs: **Profile** | **CV** | **Filters** | **API Key** | **Account**

**Profile tab:**
- Edit profile.md in a textarea
- "Regenerate with AI" — shows the prompt block again
- "Re-score all positions with updated profile" — triggers full rescore (burns quota, shown as warning)

**CV tab:**
- View/replace current CV text or PDF

**Filters tab:**
- Same UI as onboarding Step 4
- Live preview count updates as user edits

**API Key tab:**
- "It's fully free" note + "Get your free key here" link + a numbered how-to-get-a-key list (Google AI Studio → sign in → Get/Create API key → paste)
- Replace key
- "Test key" — fires a single test call to verify it works
- Delete key (pauses scoring)

**Account tab:**
- Change email/password
- Export all data (JSON)
- Delete account

---

## Scheduling & Backend Behavior

| Job | Frequency | Who runs it |
|-----|-----------|-------------|
| `refresh_companies.py` | Every 2 weeks | GitHub Actions cron |
| `collect_jobs.py` | Mon + Thu | GitHub Actions cron |
| `score.py` | User-triggered | Web server (async job) |
| Backend keep-warm (`GET /health`) | Every 10 min, 03:00-20:59 UTC | GitHub Actions cron (`keep-warm.yml`, repo variable `BACKEND_URL`; no-op while unset, never fails the run) |

**Scoring rate limit:** 2 runs per user per week. Enforced server-side. Shown clearly in the UI.

**Deduplication:** Per-user `all_scores.jsonl` ledger (already implemented). A position scored in a previous run is never re-sent to Gemini.

**Shared data:** `companies.json` and `new_jobs.json` are global — one copy for all users. Scoring input is shared; scoring output is fully isolated per user. The global `positions` table (Supabase) mirrors the latest `new_jobs.json` snapshot and backs the shared Positions page; `scripts/sync_positions.py` upserts it after each `collect_jobs.py` run (add a "Sync shared positions catalog" step to the collect cron, with `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` secrets).

---

## Profile Generation Prompt

Surfaced in two places: onboarding Step 1 and Settings → Profile tab.

The prompt is static, copyable with one click, and includes instructions for the AI to:
- Ask about experience, target roles, domain preferences, location, dealbreakers
- Output a well-structured `profile.md` that the scoring system can parse

The prompt should explicitly mention that the output will be read by an LLM scorer, so the profile should be specific and opinionated, not generic.

---

## Data Model (simplified)

**users**
- id, email, password_hash, created_at
- gemini_api_key (encrypted)
- profile_md (text)
- cv_text (text)
- scoring_runs_this_week (int), last_week_reset (date)

**score_configs**
- user_id, location_terms (array), skip_title_terms (array), keep_title_terms (array), skip_companies (array), skip_industries (array)
- cv_lead_path (nullable), cv_default_path (nullable), lead_title_terms (array)

**scored_jobs**
- user_id, apply_url (unique per user), company, title, location, score, reasoning, flags (array), scored_at, applied (bool)

**Global files (not per-user):**
- `companies.json` — refreshed every 2 weeks
- `new_jobs.json` — refreshed Mon/Thu

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| Frontend | Next.js 14 (App Router) + Tailwind + shadcn/ui | Professional, fast, well-supported |
| Backend | FastAPI (Python) | Reuses existing scoring code directly |
| Database | Supabase (PostgreSQL) free tier | Auth + storage, generous free limits |
| Job queue | Supabase Edge Functions or simple async FastAPI background tasks | Scoring runs are short enough |
| Hosting | Render.com free tier | Persistent disk, Python-native |
| Scheduling | GitHub Actions cron | Free, already where the code lives |
| API key encryption | `cryptography` (Fernet) | Simple symmetric encryption |

---

## v1 Scope (what ships)

- Landing page
- Email auth
- Onboarding flow (4 steps)
- Profile prompt generator
- CV + profile document upload (both flows accept `.md`, `.txt`, `.pdf`, `.docx`, `.doc`; `.md`/`.txt` read client-side, documents extracted via MarkItDown). Allowed types are centralized in `webapp/frontend/lib/uploadFormats.ts` (frontend) and `_DOC_EXTENSIONS`/`_TEXT_EXTENSIONS` in `webapp/backend/routers/user.py` (backend).
- Filter configuration
- Digest view with scoring
- Mark as applied
- Settings (all tabs)
- GitHub Actions scheduled jobs

## Out of scope for v1

- Email notifications ("new positions scored")
- Multiple profiles per user
- Team/shared accounts
- Mobile app
- Re-score with updated profile (too quota-heavy to offer freely)
- Custom VC list per user (everyone gets the same VC universe)
