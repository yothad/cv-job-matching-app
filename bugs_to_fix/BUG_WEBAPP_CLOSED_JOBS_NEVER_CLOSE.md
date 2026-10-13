# BUG: Website digest never marks closed positions as closed

## Status
✅ Wrapped

## Severity
P1

## Description
The pipeline closes jobs in `profiles/*/scored_jobs.json` (`score.py:_reconcile_status`, driven by
`live_positions.json`), and `scripts/sync_positions.py` prunes the shared `positions` catalog. But
nothing ever writes `status='closed'` / `closed_at` to the webapp's per-user Supabase `scored_jobs`
table (migration 004 added the columns; the backend only reads them). Every job scored via
"Score now" therefore stays "open" on the website forever, and the frontend's "Recently closed"
section is always empty.

## Steps to Reproduce
1. Score jobs on the website ("Score now").
2. Wait for a CI run in which one of those postings disappears from its company's ATS.
3. Expected: the job moves to "Recently closed" on /digest | Actual: it stays in the open list.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** scripts/sync_positions.py, tests/test_sync_positions.py
- **Spec files to update:** CLAUDE.md architecture section (sync step description)

## Fix Notes
Fixed 2026-10-13. `scripts/sync_positions.py` gained `reconcile_scored_jobs()`, run right after the
catalog prune in the CI sync step. It reads `live_positions.json` and applies score.py's rule to every
user's `scored_jobs`: close (status=closed, closed_at=today) only when the company pulled successfully
and the apply_url is gone; reopen (closed_at=null) a closed row whose URL is live again; skip entirely if
live_positions.json is missing/empty. Pages through rows 1000 at a time, PATCHes ids in batches of 100.
No DDL (columns from migration 004). Tests: 3 new in tests/test_sync_positions.py.
QA: read-only run against production (writes stubbed) - 39 would close, 0 reopen, against the stale
local August live_positions.json; CI uses the fresh one.
