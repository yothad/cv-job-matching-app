| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `in-progress` (schema + sync done; endpoint + panel pending) |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | WEBAPP_POSITIONS_CATALOG_SYNC |
| **Blocks** | — |
| **Touches** | `webapp/supabase/migrations/005_positions_catalog.sql` (or a new `00X_positions_description.sql`), `scripts/sync_positions.py`, `webapp/backend/routers/jobs.py`, `webapp/frontend/app/(app)/positions/page.tsx` |

## Progress (2026-10-12)

Done as part of the BUG_RENDER_JOBS_PATH fix (website scoring now reads jobs from
`positions` and needs descriptions): migration
`webapp/supabase/migrations/008_positions_description.sql` adds the column and
`scripts/sync_positions.py` populates it (retrying without it if the migration
isn't applied yet). The Digest detail view already falls back to it. Still open:
behaviours 3 + 4 below (Positions detail endpoint + panel rendering).

## Overview

On the Positions page detail panel the "Job description" section is a hardcoded
placeholder ("The full description isn't stored in the shared catalog"). This is
**not a missing pipeline run** — the description exists upstream in
`new_jobs.json` (collected by `collect_jobs.py`) and is already shown on the
Digest detail view. It is missing on Positions because the shared `positions`
catalog schema (migration `005`) deliberately stores only
`company/title/location/apply_url/first_seen/synced_at` and drops `description`.

This task adds `description` to the shared catalog so the Positions detail panel
can render the real JD like the Digest does — no full/partial pipeline cycle
needed, it is a schema + sync + endpoint change.

## Answering the filing question directly

- **Do I need to run a full cycle?** No. Descriptions are already collected; the
  Digest already shows them. The Positions page just doesn't carry the field.
- **Only partial cycle?** No. Once the column + sync + endpoint ship, the next
  scheduled `sync_positions.py` run backfills descriptions into the catalog.
- **Is it a code missing?** Yes — the catalog schema/sync/endpoint intentionally
  omit `description`. Adding it is the fix.

## Behaviour

1. Add a nullable `description` (text) column to the `positions` table.
2. `scripts/sync_positions.py` upserts `description` from the `new_jobs.json`
   snapshot alongside the existing fields.
3. `list_positions` (or a dedicated per-position detail endpoint) exposes
   `description`. Prefer keeping the list payload light: if descriptions are
   multi-KB, serve them from a `GET /jobs/positions/{id or apply_url}` detail
   endpoint rather than inflating the ~10k-row list response (mirror the Digest's
   light-list + per-job detail split in `jobs.py`).
4. `PositionDetailPanel` renders the description when present; falls back to the
   existing "open the posting" copy (see BUG_POSITIONS_DETAIL_DUP_LINK — keep a
   single CTA) only when no description is stored.

## Files to Touch

- `webapp/supabase/migrations/00X_positions_description.sql` — add `description` column
- `scripts/sync_positions.py` — include `description` in the upsert
- `webapp/backend/routers/jobs.py` — expose `description` (list or detail endpoint)
- `webapp/frontend/app/(app)/positions/page.tsx` — render real description in the panel

## How to QA

1. Apply the migration; confirm `positions.description` exists.
2. Run `scripts/sync_positions.py` against a `new_jobs.json` with descriptions;
   confirm rows get `description` populated.
3. Positions detail panel shows the real JD for a role that has one.
4. A role with no stored description still shows the single "Go to posting" CTA
   fallback (no duplicate link).
5. The Positions list response is not bloated (descriptions served on demand if
   large).
6. `uv run python3 -m pytest tests/ -v` passes.
7. `uv run python score.py --dry-run` passes.
