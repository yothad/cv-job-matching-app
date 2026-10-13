# BUG: Website keeps months-old jobs open when their company is no longer collected

## Status
✅ Wrapped

## Severity
P2

## Description
`scripts/sync_positions.py:reconcile_scored_jobs` closes a website job only when its
company pulled successfully this run and the URL is gone. Companies that are no longer
collected at all (ATS `unknown`, e.g. Dream, Monday, Astelia, CardinalOps, Guardz) never
appear in `successful_companies`, so their jobs from May stayed open forever. In prod on
2026-10-13: 31 open rows not in the live catalog, all first seen May/June, all score >= 5,
which is about half of the visible digest.

## Steps to Reproduce
1. A company has open scored_jobs rows, then stops being collected.
2. Run the CI sync.
3. Expected: its long-gone jobs close | Actual: they stay open indefinitely.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** collect_jobs.py, scripts/sync_positions.py, tests/test_sync_positions.py, CLAUDE.md
- **Spec files to update:** CLAUDE.md architecture section

## Fix Notes
Safety net in `reconcile_scored_jobs`: an open job whose URL isn't live and whose
`first_seen` is older than `STALE_AFTER_DAYS` (30) closes even if its company wasn't
pulled. Applied only when the run saw live URLs (an empty collect never mass-closes), and never
to a company whose pull raised this run: collect_jobs.py now writes `failed_companies`
into live_positions.json (missing in older files = none failed), so a transient error
keeps the "a failed pull never closes anything" rule. Review: career-night.
A wrong close self-heals: the URL showing up live again reopens it. Takes effect on the
next CI run.

Follow-up (same day): the first CI run closed only 1 row - all 31 legacy rows have
`first_seen = null` (they predate the column), so the age rule fell back to scored_at.
Several also carry a company label that no longer matches a collected board (e.g.
"Cardinalops" rows on the old pagayais Greenhouse board, "Astelia" rows on Team8's Comeet
board), which is why the company rule never reached them either.

Verified 2026-10-13 (CI run 38387091683): 46 closed, 0 open scored_jobs left outside the live catalog.
