# BUG: Render scoring endpoint always 503 — new_jobs.json unreachable on persistent disk

## Status
✅ Wrapped (re-opened and re-fixed 2026-10-12 - the first fix never worked)

## Severity
P0

## Description

`render.yaml` sets `JOBS_PATH=/data/new_jobs.json` (persistent disk). The GitHub Actions collect workflow commits `new_jobs.json` to the repo — it never writes to `/data/`. On Render, the persistent disk is separate from the deployed repo, so `/data/new_jobs.json` never exists unless manually seeded. The scoring endpoint will always return HTTP 503 "new_jobs.json not found" in production.

Root cause: two assumptions conflict — the workflow treats `new_jobs.json` as a repo file; the backend treats it as a disk file.

Simplest fix: change `JOBS_PATH` in `render.yaml` to Render's standard repo checkout path:
```
/opt/render/project/src/new_jobs.json
```
Render auto-deploys on every push to main. After each collect run (which commits `new_jobs.json`), Render redeploys and the fresh file is available at the repo checkout path. No disk needed for this file.

Also remove the `disk:` block from `render.yaml` unless needed for another purpose — free-tier persistent disks are limited.

## Steps to Reproduce

1. Deploy to Render using `render.yaml` as-is
2. Wait for GitHub Actions collect to run and commit `new_jobs.json`
3. Trigger a scoring run via `POST /score/`
4. Expected: scoring runs against latest collected jobs
5. Actual: HTTP 503 "new_jobs.json not found"

## Dependencies

- **Depends on:** —
- **Blocks:** Production deployment of the webapp
- **Touches:** `render.yaml`
- **Spec files to update:** `future_devs/archive/WEBAPP_DEPLOY_SPEC.md`

## Fix Notes
- Removed `disk:` block from `render.yaml` (free-tier disk was unused)
- Changed `JOBS_PATH` from `/data/new_jobs.json` → `/opt/render/project/src/new_jobs.json`
- Changed `COMPANIES_PATH` from `/data/companies.json` → `/opt/render/project/src/companies.json`
- Both files are committed to the repo; Render redeploys on every push so they are always current

## Re-fix (2026-10-12)

The first fix was wrong: `new_jobs.json` is **gitignored**, so it is never in the
Render checkout, and `render.yaml` set `NEW_JOBS_PATH` while `scoring.py` read
`JOBS_PATH` - the website's "Score now" could never find jobs. Re-fixed by reading
jobs from the shared Supabase `positions` table (synced by
`scripts/sync_positions.py`) instead of any file:

- `webapp/backend/db/positions.py` - paginated catalog reader (+ latest sync time)
- `routers/scoring.py` - scores from `positions` (same location/title/company/
  industry filters, paginated dedup vs `scored_jobs`), batches at the CLI size,
  never persists scorer-error rows, clear 502 when Gemini fails
- `routers/jobs.py` - company counts, filter preview, stats, detail fallback off
  `positions` too
- migration `008_positions_description.sql` + `sync_positions.py` carry the JD
- `render.yaml` - dead `NEW_JOBS_PATH` removed

Action: apply migration 008 in the Supabase SQL editor; descriptions backfill on
the next collect-and-score run.
