# BUG: "Mark applied" button missing / not persisting on digest page

## Status
✅ Wrapped

## Severity
P2

## Description
The "Mark applied" / "Undo applied" toggle button on the digest page was working earlier and is now missing or broken. The feature exists in code (`JobCard` in `webapp/frontend/app/(app)/digest/page.tsx` and the `POST /jobs/{job_id}/applied` endpoint in `webapp/backend/routers/jobs.py`) but the user can no longer interact with it.

Likely root causes (in order of probability):

1. **Production deploy regression** - a recent Render deploy may have reverted the frontend or backend to a version without the feature, or caused a runtime error on the toggle endpoint.
2. **`toggle_applied` KeyError** - `jobs.py:143` does `not row["applied"]`; if the `applied` column is absent from the DB response (e.g. column missing on the live Supabase instance), this throws a 500 which the frontend swallows silently.
3. **Missing `applied` column on live Supabase** - the migration `001_initial_schema.sql` defines `applied boolean default false`, but if the live DB was provisioned before this migration ran, existing rows may not have the column.

## Steps to Reproduce
1. Open the webapp digest page (production or local)
2. Look for the "Mark applied" button below each job card
3. Expected: button visible, clicking toggles applied state and persists across page reload
4. Actual: button is absent, or clicking produces no visible effect / silent failure

## Dependencies
- **Depends on:** -
- **Blocks:** -
- **Touches:** `webapp/frontend/app/(app)/digest/page.tsx`, `webapp/backend/routers/jobs.py`, `webapp/supabase/migrations/001_initial_schema.sql`
- **Spec files to update:** -

## Fix Notes
Root cause confirmed in code: `toggleApplied()` in `webapp/frontend/app/(app)/digest/page.tsx` fired the `POST /jobs/{job_id}/applied` request and unconditionally applied an optimistic local state update, never checking `res.ok`. Any backend failure - a 404, a 500 from a schema mismatch, an auth hiccup, anything - was silently swallowed: the button visually toggled but nothing persisted, so a reload reverted it. This matches the reported symptom exactly and was present since the feature was first written (git history shows a single, unmodified version of the function), so it is a latent bug rather than a deploy regression.

Fix: `toggleApplied` now checks `res.ok` before updating local state; on failure it sets the existing `scoreMsg` UI slot (already used for Score-now feedback) to `'Could not update applied status - try again'` and returns without touching `jobs` state, so the button no longer lies about success.

Hypotheses 1 (deploy regression) and 3 (missing `applied` column on live Supabase) from the original bug report could not be verified from this session - they require checking the live Render deploy and the production Supabase schema directly, which needs Yotam's access. If the button still fails after this fix ships, check the browser console/network tab for the new visible error message and the actual HTTP status from `/jobs/{job_id}/applied` - that will point at which of those two it is.
