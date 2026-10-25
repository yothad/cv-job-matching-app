| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `collect_jobs.py`, `score.py`, `webapp/backend/routers/scoring.py`, Supabase `scored_jobs` migration, webapp frontend job cards |

## Overview

Each position should carry the date it was first observed by the pipeline. Today, `new_jobs.json` is fully overwritten on every daily run, so the first-time a job appeared is lost. Adding a `first_seen` field lets the digest and webapp surface "posted 3 days ago"-style freshness labels, helps Yotam prioritise recent roles, and feeds the existing `WEBAPP_NEW_SINCE_LAST_VISIT` feature when that ships.

## Behaviour

- `collect_jobs.py` reads the existing `new_jobs.json` before overwriting it and builds a `{apply_url: first_seen}` lookup from the prior run.
- For every job collected in the current run: if `apply_url` exists in the lookup, carry forward its `first_seen`; otherwise stamp `first_seen = <today ISO date, UTC>`.
- The `first_seen` value is a date string `YYYY-MM-DD` (no time component needed).
- `score.py` includes `first_seen` in each scored job's output in `digest.md` (e.g., `First seen: 2026-06-14`).
- `webapp/backend/routers/scoring.py` passes `first_seen` when upserting a row into `scored_jobs`. Because the upsert skips already-scored URLs, this is set exactly once per job and never overwritten.
- Supabase `scored_jobs` table gains a `first_seen DATE` column (nullable for pre-existing rows).
- Webapp job cards display `first_seen` as a relative label (e.g., "3 days ago") with a tooltip showing the absolute date.
- If `first_seen` is null (legacy rows seeded before this feature), show nothing rather than "null days ago".

## Files to Touch

1. `collect_jobs.py` — read prior `new_jobs.json`, build lookup, stamp `first_seen` on each job dict
2. `score.py` — emit `first_seen` in the per-job section of `digest.md`
3. `webapp/backend/routers/scoring.py` — add `"first_seen": job.get("first_seen")` to the upsert row dict
4. Supabase SQL migration — `ALTER TABLE scored_jobs ADD COLUMN first_seen DATE;`
5. Webapp frontend (`components/JobCard` or equivalent) — render `first_seen` as "X days ago"

## How to QA

1. Delete or rename `new_jobs.json`; run `uv run python collect_jobs.py`; confirm every job in the new `new_jobs.json` has a `first_seen` field equal to today's date.
2. Run `uv run python collect_jobs.py` again without changing anything; confirm every job's `first_seen` is still today's date (carried forward, not overwritten).
3. Manually edit one job's `first_seen` in `new_jobs.json` to `2026-01-01`; run `collect_jobs.py` again; confirm that job still shows `2026-01-01` while new jobs (if any appear) show today.
4. Run `uv run python score.py`; open `digest.md`; confirm each job entry includes `First seen: YYYY-MM-DD`.
5. Trigger a scoring run via the webapp; open Supabase → `scored_jobs`; confirm new rows have a non-null `first_seen`.
6. Open the webapp digest; confirm job cards show a relative date label (e.g., "3 days ago") and that the tooltip shows the absolute date.
7. Confirm legacy rows with `first_seen = null` display no freshness label.
