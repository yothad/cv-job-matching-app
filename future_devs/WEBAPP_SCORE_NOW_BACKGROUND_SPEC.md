| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `completed` |
| **Effort** | M |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | WEBAPP_RESCORE_MISSING_DESCRIPTIONS |
| **Touches** | webapp/backend/routers/scoring.py, webapp/backend/tests/test_scoring_background.py, webapp/frontend/app/(app)/digest/page.tsx, webapp/supabase/migrations/010_score_run_progress.sql |
| **Night-ready** | no (needs Supabase SQL) |

## Overview
POST /score scored everything inside one HTTP request: ~80 jobs/min, 580 jobs took many minutes,
no progress, no cap, and a Render restart or proxy timeout lost the whole run. Make Score now a
background job the digest can watch.

## Behaviour
- `POST /score/` validates synchronously (key, profile, weekly limit, already-running → 409), builds
  the pending list, caps it at `SCORE_RUN_CAP` (env, default 200), stores a run record in
  `users.score_run` (jsonb, migration 010) and returns `{started, run}` at once. A FastAPI background
  task does the scoring.
- Each batch is upserted as soon as it is scored (partial work survives a crash) and the run record's
  `scored` / `failed` / `updated_at` are updated.
- `GET /score/status` → `{run, rescore_available}`. A `running` run with no progress write for 10 min
  reads as `failed` ("interrupted") so a dead process never locks the button.
- Weekly limit: a `new` run counts toward the 2/week only when it scored something AND cleared the
  backlog (`remaining == 0`); capped runs can be continued. Nothing scored → not charged (unchanged).
- Scorer-error rows are never persisted (unchanged); a whole failed batch stops the run.
- Digest: polls status every 3s while running, shows "Scoring N of M...", refreshes the list every
  ~15s, resumes watching after a page reload, and shows the final message (incl. "X more waiting").
- Progress writes are best-effort: before migration 010 is applied, scoring still works, only the
  progress/409 guard is missing.

## How to QA
1. Apply migration 010; press Score now - the button returns within a second and the toolbar counts
   up "Scoring N of M...".
2. Reload the page mid-run - progress resumes; new cards appear while it runs.
3. With >200 pending, the run stops at 200 and says "N more waiting"; runs used stays unchanged until a
   run clears the backlog.
4. Press Score now in a second tab mid-run - it follows the existing run instead of starting another.

## Needs Omer
```sql
alter table users add column if not exists score_run jsonb;
```
Run it in Supabase BEFORE merging the branch to main.
