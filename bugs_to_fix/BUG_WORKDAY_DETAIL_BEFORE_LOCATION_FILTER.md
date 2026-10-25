# BUG: Workday puller fetches every global job's description before the location filter

## Status
🔵 Open

## Severity
P2

## Description
`ats/workday.py:fetch_positions` pages the full job list, then makes one sequential
detail GET (10s timeout) per posting to get the description. `collect_jobs.py` applies
`location_filter` only afterwards (`collect_jobs.py:103-115`), so for big global tenants
almost all detail calls fetch descriptions that are immediately discarded.

GE HealthCare (`tenant: gehc`, `wd5`, `GEHC_ExternalSite`, `location_filter: israel`) had
1,009 postings on 2026-10-20: ~51 list pages + 1,009 detail GETs, roughly 20-35 minutes of
silent runtime for a handful of Israel jobs. Nothing prints during the pull, so the run
looks hung - Yotam stopped a local collect once, then thought it was stuck a second time.
It also slows every CI collect run.

Root cause: the puller has no access to `location_filter`, so it can't skip irrelevant
postings before the expensive per-job call.

Fix direction:
- Pass `location_filter` into the Workday puller (via the `ATS_PULLERS` lambda in
  `ats/__init__.py`, e.g. an optional `location_filter` param on `fetch_positions`).
- Skip the detail call for postings whose list-view `locationsText` doesn't contain the
  filter (case-insensitive) - **except** empty or collapsed `"N Locations"` text
  (`_COLLAPSED_LOC_RE`), which still need the detail call to rebuild the real location set.
- This is behaviour-preserving: for non-collapsed postings the final `location` already
  *is* the list-view text, so `collect_jobs.py`'s filter would drop the same jobs. Keep the
  filter in `collect_jobs.py` as is (it still covers every other ATS and the expanded
  collapsed-location case).
- Print progress every N detail fetches (e.g. every 100) so long pulls don't look hung.

## Steps to Reproduce
1. `companies.json` contains GE HealthCare with `ats: workday`, `location_filter: israel`.
2. `uv run python collect_jobs.py` and watch output after "Egis Technology".
3. Expected: GE HealthCare finishes in well under a minute (only Israel / collapsed-location
   postings get a detail call). | Actual: ~20-35 minutes with no output, ~1,000 detail GETs.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** `ats/workday.py`, `ats/__init__.py`, `tests/test_ats_location_hardening.py` (or a new Workday test)
- **Spec files to update:** `CLAUDE.md` (Adding a new ATS / location_filter gotcha - note that pullers may pre-filter but `collect_jobs.py` stays the source of truth)
- **Night-ready:** 🌙 yes - pure puller change, testable with mocked httpx like the existing Workday tests; no secrets, no scoring change

## Fix Notes
<!-- populated after fix -->
