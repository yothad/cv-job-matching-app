| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `not-started` |
| **Effort** | L |
| **Epic** | - |
| **Depends on** | WEBAPP_FIRST_LOGIN_JOURNEY (soft: the journey's profile/CV steps become "create your first profile") |
| **Blocks** | MULTI_AGENT_RESUME_TAILOR (needs a CV per target role) |
| **Touches** | webapp/supabase/migrations/, webapp/backend/routers/user.py, webapp/backend/routers/scoring.py, webapp/backend/routers/jobs.py, webapp/backend/routers/gaps.py, webapp/frontend/app/(app)/settings/page.tsx, webapp/frontend/app/(app)/digest/page.tsx, webapp/frontend/app/onboarding/page.tsx |
| **Night-ready** | no — schema migration + backfill must be applied in the Supabase SQL editor by Omer |

## Overview

Today a user has exactly one profile and one CV: `users.profile_md`, `users.cv_text`, `users.profile_version`. People often target different roles (e.g. Team Lead vs IC, or two industries) and want a different CV and "what I want" text for each, with separate scores and digests. The local pipeline already supports this (`profiles/<name>/` with its own cv, profile and `score_config.json`, wrapped as "Multi-profile support"); the webapp does not.

Goal: a user can create several named profiles, each with its own profile text, CV, and filters, switch between them, and score and view results per profile. The Gemini API key stays per user.

## Behaviour

**Data model (new migration, run by Omer in the Supabase SQL editor):**
- New table `user_profiles`: `id uuid pk`, `user_id uuid -> users(id) on delete cascade`, `name text not null`, `profile_md text`, `cv_text text`, `profile_version int default 1`, `profile_updated_at`, `cv_updated_at`, `is_default bool`, `created_at`. Unique `(user_id, name)`.
- `score_configs`: add `profile_id uuid -> user_profiles(id)`; one config per profile (today one per user).
- `scored_jobs`: add `profile_id`; the upsert key `on_conflict="user_id,apply_url"` (scoring.py) must become `(profile_id, apply_url)` or the same job scored under two profiles overwrites itself. Same for the dedup lookup of already-scored URLs.
- **Backfill:** for every existing user create one profile named "Default" from `users.profile_md/cv_text/...`, point their `score_configs` and `scored_jobs` rows at it. Keep the old `users` columns until the new path is verified, then drop in a follow-up migration.

**Backend:**
- CRUD: `GET/POST /user/profiles`, `GET/PATCH/DELETE /user/profiles/{id}`; the existing `/user/profile`, `/user/cv`, `/user/filters` become per-profile (accept `profile_id`, default to the user's default profile so the old frontend keeps working during rollout).
- Scoring, filter preview, stats, gaps and job detail take a `profile_id`. The weekly limit (2 runs/week) stays per USER, not per profile - otherwise profiles multiply the Gemini bill. Decide and document: does one "Score now" run cover one profile (recommended) or all.
- Ownership check on every `profile_id` (must belong to the authed user) via `require_user`.
- Cap profiles per user (suggest 5) to bound cost and storage.

**Frontend:**
- A profile switcher in the app shell (Digest, Settings, Gaps), remembered per browser. Digest shows the active profile's scores; "Score now" scores the active profile.
- Settings: Profile / CV / Filters tabs edit the ACTIVE profile; API Key and Account stay user-level. Create, rename, duplicate ("start from this profile"), delete (with confirmation and a warning that its scores are deleted).
- Onboarding creates the first profile (named "Default", renamable). Single-profile users should see almost no new UI - the switcher only appears once a second profile exists.
- Positions/Companies stay shared and profile-independent.

**Edge cases:** deleting the default profile promotes another; deleting the last profile is blocked; renaming to an existing name is rejected; a profile without a CV scores profile-only (as today); old scored_jobs without `profile_id` after migration must not appear under the wrong profile.

## Files to Touch

- `webapp/supabase/migrations/010_user_profiles.sql` (+ backfill; Omer applies it manually)
- `webapp/backend/routers/user.py`, `scoring.py`, `jobs.py`, `gaps.py`; `webapp/backend/auth.py` (profile ownership helper)
- `webapp/frontend/app/(app)/settings/page.tsx`, `(app)/digest/page.tsx`, `(app)/gaps/`, `app/onboarding/page.tsx`, app-shell nav for the switcher
- `scripts/seed_supabase.py` (seeds from `profiles/omer/` - update to create a named profile)
- Specs to update: `WEBAPP_SPEC.md`, `CLAUDE.md` only if the scoring contract changes. Note: no scorer prompt, rubric, model or batch-size change is needed, so the eval gate does not apply; if implementation touches `matcher/gemini_scorer.py`, run the eval first per CLAUDE.md.

## How to QA

1. Existing user after migration: sees one profile "Default" with their old profile, CV, filters and all previous scores intact.
2. Create a second profile with a different profile text and CV; "Score now" on it produces scores that do not overwrite the first profile's scores for the same jobs.
3. Switch profiles in Digest: the job list and scores change; Settings edits the active profile only.
4. Delete a profile: its scores disappear, the other profile is untouched; deleting the last profile is refused.
5. The weekly limit counts per user across profiles (a 3rd run in the week is rejected regardless of profile).
6. A user cannot read or write another user's `profile_id` (expect 404/403); `pytest` and `npm run build` pass.
