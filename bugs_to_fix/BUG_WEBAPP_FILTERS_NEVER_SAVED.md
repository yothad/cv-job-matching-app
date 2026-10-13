# BUG: Settings filters are never saved (Save failed, empty on reload)

## Status
🟢 Completed

## Severity
P1

## Description
`PATCH /user/filters` (and the unused `POST /user/setup`) wrote `score_configs` with
`upsert(on_conflict="user_id")`, but `score_configs.user_id` has no unique constraint
(001_initial_schema.sql), so Postgres rejects every call with 42P10 "there is no unique or
exclusion constraint matching the ON CONFLICT specification". The UI flashed "Save failed"
for 3s and nothing was stored; prod `score_configs` was empty. Side effect: with no
location filter, auto-score scored the whole worldwide catalog (~2,600 non-Israel rows).

## Steps to Reproduce
1. Settings -> Filters, set Location "israel", Save.
2. Go to Digest, come back to Settings -> Filters.
3. Expected: "israel" is shown | Actual: the field is empty, no score_configs row exists.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** webapp/backend/routers/user.py, webapp/backend/tests/test_user_setup.py
- **Spec files to update:** —

## Fix Notes
`_save_filters()` updates the user's row and inserts it if none exists (same pattern as
`_save_user_fields`), stamping `updated_at`. No migration needed. Regression tests cover
the first save (insert) and later saves (update only).
