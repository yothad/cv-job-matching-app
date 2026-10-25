| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `not-started` |
| **Effort** | S |
| **Epic** | WEBAPP_JOBSEEKER_WORKFLOW |
| **Depends on** | WEBAPP_POSITIONS_CATALOG_SYNC |
| **Blocks** | — |
| **Touches** | `webapp/supabase/migrations/00X_position_applied.sql` (new), `webapp/backend/routers/jobs.py`, `webapp/frontend/app/(app)/positions/page.tsx` |

## Overview

The Positions page detail panel has no way to mark a role as applied/saved. A job
seeker browsing the shared market wants to track which catalog roles they have
acted on, without switching to the Digest.

### Context — what already exists (read before building)

- The **Digest** already supports mark-applied: the binary `applied` toggle lives
  on every scored job (`JobCard` + `JobDetailPanel` "Mark applied" button,
  `POST /jobs/{id}/applied`). If the user's intent was "track applied on my
  scored jobs," that is already shipped.
- `WEBAPP_APPLICATION_TRACKER` (not-started) upgrades that Digest binary into a
  full status tracker (`saved`/`applied`/`interviewing`/`rejected`/`offer`).
- This spec is specifically the **Positions (shared catalog)** surface, which is
  distinct.

### Design tension (decide before building)

The Positions catalog is a **shared, unscored, per-`apply_url`** table — not
per-user. There is no user-scoped row to flip an `applied` bool on, so marking a
catalog position applied requires a **new per-user overlay table**
(`user_id` + `apply_url` + `status`/`applied` + timestamp) joined into
`list_positions`. That is genuinely new persistent state — CLAUDE.md cautions
against adding state beyond what's needed, so confirm the value with Yotam before
building. Cheaper alternative: link catalog rows to the Digest's existing
applied-tracking rather than duplicating the mechanism on the catalog.

## Behaviour (if approved)

1. New table `position_status` (per user, keyed by `user_id` + `apply_url`):
   `applied` bool (or a status enum, aligned with WEBAPP_APPLICATION_TRACKER),
   `updated_at`.
2. `list_positions` left-joins the current user's overlay so each returned
   position carries its per-user `applied`/status (default not-set).
3. New endpoint to set/clear applied for a given `apply_url`.
4. `PositionDetailPanel` gains a "Mark applied" / "Undo applied" control; applied
   rows render de-emphasized in the list (mirror the Digest's applied styling).

## Files to Touch

- `webapp/supabase/migrations/00X_position_applied.sql` — per-user overlay table
- `webapp/backend/routers/jobs.py` — join overlay into `list_positions`; set/clear endpoint
- `webapp/frontend/app/(app)/positions/page.tsx` — mark-applied control + applied styling

## How to QA

1. Mark a catalog position applied; it persists across reload.
2. Applied positions render de-emphasized / grouped.
3. The overlay is per-user (a second account does not see the first's applied state).
4. `uv run python3 -m pytest tests/ -v` passes.
5. `uv run python score.py --dry-run` passes.
