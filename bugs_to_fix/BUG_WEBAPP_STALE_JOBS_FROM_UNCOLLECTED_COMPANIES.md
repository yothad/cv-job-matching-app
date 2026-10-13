# BUG: Website keeps months-old jobs open when their company is no longer collected

## Status
🟢 Completed

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
- **Touches:** scripts/sync_positions.py, tests/test_sync_positions.py, CLAUDE.md
- **Spec files to update:** CLAUDE.md architecture section

## Fix Notes
Safety net in `reconcile_scored_jobs`: an open job whose URL isn't live and whose
`first_seen` is older than `STALE_AFTER_DAYS` (30) closes even if its company wasn't
pulled. Applied only when the run saw live URLs (an empty collect never mass-closes).
A wrong close self-heals: the URL showing up live again reopens it. Takes effect on the
next CI run.
