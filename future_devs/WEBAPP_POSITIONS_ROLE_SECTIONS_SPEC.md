# Webapp positions role sections - let "Score now" read role + requirements too

| Field | Value |
|---|---|
| **Phase** | P13 |
| **Status** | `not-started` |
| **Effort** | S |
| **Epic** | — (standalone) |
| **Depends on** | SCORER_EVAL_HARNESS (the eval run in both `SCORER_TEXT` modes must show the role mode is not a regression before the webapp switches too) |
| **Blocks** | — |
| **Touches** | `webapp/supabase/migrations/012_positions_role_sections.sql` (new), `scripts/sync_positions.py`, `webapp/backend/db/positions.py`, `webapp/backend/routers/scoring.py`, `tests/` + `webapp/backend/tests/` |
| **Night-ready** | no - applying the migration is Supabase SQL, a human-only step; and it is gated on the eval result |

## Overview

Since BUG_DESCRIPTION_COMPANY_BOILERPLATE (2026-10-21), `collect_jobs.py` stores
`role_description` / `responsibilities` / `requirements` on every job and the pipeline's Gemini
prompt reads `role_description` + `requirements` (`matcher/gemini_scorer.py:_job_text_fields`).

The webapp scores from the Supabase `positions` catalog, which only has `description`. So
webapp "Score now" and `POST /score/auto` still fall back to the old `description` prompt: the
pipeline and the webapp score the same job from different text. This task carries the three
section fields through the catalog so the webapp scores exactly like the pipeline.

**When:** after the text-vs-metadata experiment and the two-mode eval. The experiment doesn't
need it (it reads the local golden set), and switching the webapp's Gemini input is a scoring
change - only worth rolling out once the eval shows the role mode holds up. If it regresses,
the pipeline goes back to `SCORER_TEXT=description` and this task is dropped.

## Behaviour

### Migration `012_positions_role_sections.sql`

```sql
-- Role sections split out of the job post at collect time (collect_jobs.py ->
-- ats/utils.py:job_sections). The scorer reads role_description + requirements
-- instead of description when they are present; description stays as the fallback
-- and for the detail view. Populated by scripts/sync_positions.py; the next collect
-- run backfills every live position. Each value is capped at 4000 chars upstream.
alter table positions add column if not exists role_description text;
alter table positions add column if not exists responsibilities text;
alter table positions add column if not exists requirements text;
```

No index (never filtered on), no RLS change (same policy as the rest of `positions`).
Rows synced before the next collect have NULL - the scorer treats NULL like "" and falls back
to `description`, so nothing breaks in between.

### `scripts/sync_positions.py`
- Add `role_description`, `responsibilities`, `requirements` to the upserted row.
- Same graceful degrade as migration 008: if PostgREST answers 400 for a missing column
  (migration 012 not applied yet), warn once naming the migration file and keep syncing
  without the three columns. A missing migration must never block scoring (the step is
  `continue-on-error`, but the catalog refresh itself should still succeed).
- Payload roughly doubles per row (up to +12 KB); check `BATCH_SIZE = 250` still fits
  PostgREST's request limit, lower it if needed.

### `webapp/backend/db/positions.py`
- `fetch_positions(with_description=True)` also selects the three columns; if they are
  missing, fall back to the current column set (like the existing 008 fallback).

### `webapp/backend/routers/scoring.py`
- `_rescore_candidates` select list gains the three columns.
- No scorer change: `score_jobs_batch` already picks `role_description` + `requirements`
  when present. Render's `SCORER_TEXT` env must stay unset (default `role`) - or set it to
  `description` there to keep the webapp on the old prompt.
- `scored_jobs` keeps storing `description` only (detail view); not in scope.

## Files to Touch
- `webapp/supabase/migrations/012_positions_role_sections.sql` (new)
- `scripts/sync_positions.py`
- `webapp/backend/db/positions.py`
- `webapp/backend/routers/scoring.py`
- tests for the sync payload / missing-column fallback and the catalog fetch fallback
- `WEBAPP_SPEC.md` (positions catalog columns), `CLAUDE.md` (sync_positions paragraph)

## How to QA
1. Before applying 012: run `scripts/sync_positions.py` against Supabase - it warns about
   migration 012 and the sync still completes (row count printed, exit 0).
2. Apply 012 in the Supabase SQL editor, re-run the sync - `select count(*) from positions
   where requirements <> ''` is > 0.
3. Trigger "Score now" for a test account on one job - the prompt sent (log it once, or
   reproduce with `build_batch_prompt` on the fetched row) contains `Role:` and
   `Requirements:`, not `Description:`.
4. With Render `SCORER_TEXT=description`, the same job's prompt has `Description:` again.
