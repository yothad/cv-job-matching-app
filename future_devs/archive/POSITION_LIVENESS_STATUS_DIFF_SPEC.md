| Field | Value |
|---|---|
| **Phase** | P8 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | POSITION_LIVENESS |
| **Depends on** | POSITION_LIVENESS_LIVE_SET |
| **Blocks** | POSITION_LIVENESS_DIGEST_RENDER, POSITION_LIVENESS_WEBAPP |
| **Touches** | `score.py` |
| **Spec files to update** | `CLAUDE.md` architecture section (`score.py` cadence note + `scored_jobs.json` field list) |

## Overview

**What:** During `score.py`'s merge step, reconcile every job already in `scored_jobs.json` against the live set from `live_positions.json`, stamping a `status` (`open` / `closed`) and a `closed_at` date.

**Why:** This is where the `inactive`/`closed` state actually gets computed and persisted on the records Yotam reads.

## Behaviour

Load `live_positions.json` once at the start of the merge. Let `live = set(live_apply_urls)` and `successful = set(successful_companies)`.

For each job in the merged `scored_jobs.json` store (after `_merge_new_results` adds this run's new relevant jobs):

- **Newly added / live:** key in `live` → `status = "open"`. Clear any prior `closed_at`.
- **Closed:** key **not** in `live` **AND** the job's company **is** in `successful` → `status = "closed"`, set `closed_at = today` if not already set.
- **Indeterminate (the guard):** key not in `live` but the job's company is **not** in `successful` → leave `status` unchanged (do not close; the company didn't report this run). Default to `open` only if the job has no `status` yet.
- **Reopened:** a job previously `closed` whose key reappears in `live` → `status = "open"`, `closed_at` removed.

Notes:
- Key with the existing `_job_key` helper (`apply_url`, fallback `company::title`) so this lines up with how the store is already keyed.
- Match company via the job's stored `company` field against `successful_companies` (exact match, consistent with existing `_company_filter` casing — lowercase both sides).
- Backfill: jobs already in the store with no `status` get one on first run of this feature.
- If `live_positions.json` is missing (e.g. `score.py` run standalone without a fresh collect), skip status reconciliation entirely and leave existing `status` untouched — never mass-close on missing input.
- `--dry-run` must not write status changes.

## New fields in `scored_jobs.json`

```json
{
  "status": "open | closed",
  "closed_at": "2026-06-17"
}
```

## Files to Touch

- `score.py` — load `live_positions.json`; add a `_reconcile_status(merged, live, successful, today)` step after `_merge_new_results`; persist via existing `_save_scored_jobs`.

## How to QA

1. Run collect → score; confirm live jobs are `status: open` and none are wrongly `closed`.
2. Manually remove a URL from `live_positions.json` (company still in `successful_companies`), re-run score; that job becomes `status: closed` with today's `closed_at`.
3. Remove the same job's company from `successful_companies`; confirm the job does **not** close (guard holds).
4. Re-add the URL to `live`; confirm the job flips back to `open` and `closed_at` is cleared.
5. Delete `live_positions.json`; confirm score.py runs and leaves statuses untouched (no mass-close).
6. Exit gate: `pytest tests/ -v` and `score.py --dry-run` pass.
