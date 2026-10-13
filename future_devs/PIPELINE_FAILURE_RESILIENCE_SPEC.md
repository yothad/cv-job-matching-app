| Field | Value |
|---|---|
| **Phase** | P11 |
| **Status** | `completed` |
| **Effort** | M |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `collect_jobs.py`, `refresh_companies.py`, `score.py`, `companies.json` (state), `tests/` |
| **Night-ready** | 🌙 yes |
| **Model** | Fable (`claude-fable-5`) |

## Overview

Investigate and harden the pipeline's handling of intermittent / partial
failures. Symptoms live in `companies.json` state: `consecutive_failures`
climbing on companies that are actually fine, stale `careers_url` entries, and
partial pulls that look like success. This is a *diagnosis* task, not a known
one-line bug — the goal is to find the real cause of flaky per-company behaviour
rather than declare it fixed after one clean run.

**Why Fable:** correctly distinguishing an intermittent flake from a real,
reproducible failure — and not stopping at the first green run — is exactly the
debugging behaviour Fable is noted for. Hand it the three orchestrators together
and let it trace state transitions end-to-end.

## Behaviour

Trace and, where warranted, fix:

1. **`consecutive_failures` semantics** — confirm it increments only on genuine
   pull failures and resets to 0 on the next success. A transient network blip
   should not permanently mark a live company stale.
2. **Stale-entry re-verification threshold** — `refresh_companies.py` re-verifies
   VC entries at 30d+ since `last_verified_at` or `consecutive_failures >= 3`.
   Confirm the threshold logic fires correctly and doesn't strand a recoverable
   company.
3. **Partial-pull detection** — a puller that returns 0 jobs due to an error vs.
   a company that genuinely has 0 open roles must be distinguishable, so the
   latter doesn't get penalised as a failure.
4. **Score-stage robustness** — Gemini JSON-wrapping / malformed responses are
   parsed leniently (documented gotcha); confirm one bad job doesn't drop the
   rest of the batch.
5. **State-write atomicity** — a crash mid-run must not corrupt `companies.json`
   or `new_jobs.json` (merge-never-overwrite invariant).

## Files to Touch

- `collect_jobs.py` — failure counting, partial-pull detection, per-company isolation
- `refresh_companies.py` — stale/failure re-verification thresholds
- `score.py` — lenient Gemini-response parsing, per-job error isolation
- `tests/` — regression tests reproducing each real failure mode found

## How to QA

1. `uv run python3 -m pytest tests/ -v` passes with new resilience tests.
2. `uv run python score.py --dry-run` runs clean.
3. Simulate a transient failure for a live company → `consecutive_failures`
   increments once, then resets to 0 on the next successful `collect_jobs.py` run.
4. Feed a malformed Gemini response fixture → the bad job is skipped, the rest of
   the batch still scores.
5. A written diagnosis: each failure mode found, whether it was a real bug or a
   false alarm, and evidence (tool output) for the conclusion.

## Diagnosis (night run 2026-10-12)

Evidence was gathered read-only from `companies.json`, its git history (last 80
committed versions) and `profiles/omer/all_scores.jsonl`. Failure modes were
reproduced in `tests/test_pipeline_resilience.py` with monkeypatched pullers /
discovery / Gemini client in temp dirs. No real collect / refresh / score run.

| # | Area | Verdict | Fixed? |
|---|---|---|---|
| 1 | `consecutive_failures` semantics | Logic in `collect_jobs.py` is correct; the counter is dead in practice | No (Needs Omer) |
| 2 | Re-verification threshold | Threshold fires correctly; a failed re-verify **wipes a working config** | Yes |
| 3 | Error vs genuine zero | **Real** - indistinguishable; same root cause as 1 | No (Needs Omer) |
| 4 | Score-stage robustness | **Real** - one bad item failed the whole batch; scorer errors became permanent | Yes |
| 5 | State-write atomicity | **Real** but latent - plain truncating writes | Yes |

### 1 + 3. consecutive_failures / partial pulls - real bug, root cause in `ats/*.py`

`collect_jobs.py` increments on an exception and resets to 0 on the next success,
and a genuine 0-job pull counts as a success. Test
`test_failure_increments_once_then_resets_on_success` and
`test_genuine_zero_jobs_is_not_a_failure` pass against the unchanged code, so the
orchestrator itself is right.

The problem is that almost every puller catches its own HTTP / JSON errors and
returns `[]` (or the pages fetched so far): ashby, bamboohr, breezy, comeet,
getro, greenhouse, jobvite, lever, taleo, teamme, teamtailor return `[]`;
amazon_jobs, consider, eightfold, google_careers, microsoft_careers, oracle_hcm,
smartrecruiters, successfactors, talentbrew, workable, workday `break` / return
partial results. `tests/test_ats_schema.py` pins this as the contract ("HTTP error
should return [] not raise"). So collect sees a transient 503 as "0 open positions":

- `consecutive_failures` is reset to 0, never incremented. Evidence: all 2,975
  entries (793 pullable) have `consecutive_failures == 0` today, and none of the
  last 60 committed versions of `companies.json` contains a non-zero value. With
  ~800 HTTP pulls a day that is not plausible; the `>= 3` re-verify trigger has
  never fired.
- The company is listed in `live_positions.json.successful_companies`, so
  `score.py::_reconcile_status` marks all of its open scored jobs `closed` for the
  day (they reopen on the next good pull). Partial paginated pulls do the same to
  the jobs on the pages that failed.

Pinned by `test_transient_http_error_in_real_puller_counts_as_failure`
(`xfail(strict=True)`; it flips to XPASS once fixed). Not fixed tonight: the fix
changes the documented puller contract across ~20 `ats/` modules (outside this
task's Touches list) and flips existing tests. See Needs Omer in the night report.

### 2. Re-verification - real bug, fixed

`needs_reverify` is correct (30d age or `>= 3` failures, `skip_discovery` honoured,
timestamps all tz-aware). But on re-verify, `refresh_companies.py` copied whatever
`discover()` returned. `find_careers_url` / `detect_ats` swallow their errors and
return `None` / `"unknown"`, so any discovery flake (Playwright timeout, bot wall,
careers page redesign) overwrote a working `ats` / `ats_params` with
`unknown` / `{}`. collect then skips the entry ("no ATS cached"); with
`last_verified_at` restamped it is not retried for 30 days, and after
`scripts/mark_skips.py` it is locked out for good (`skip_reason=unknown_ats`).

Evidence (git history of `companies.json`): 593 known-ATS -> unknown transitions,
374 of them in the 2026-06-07 refresh and 92 / 49 / 30 / 25 in later ones. 503
companies that once had a working config have no usable ATS config today, 331 of them now
`skip_reason=unknown_ats`, including tier-1 names like Island, Torq,
Zafran, Astelia, Guardz, Sweet, IONIX. Some of these may be genuine (board moved,
earlier detection was a false positive), so restoring them is a data decision.

Fix: `refresh_companies.apply_reverify()` - a re-discovery with no usable ATS
params keeps the cached config, stamps `last_verified_at`, leaves
`consecutive_failures` alone (so a still-failing entry retries next week).
A successful re-discovery still replaces the config and resets failures. Used
by both the VC loop and the manual-entries loop. Tests:
`test_failed_reverify_keeps_working_ats_config` (4 cases),
`test_successful_reverify_still_updates_config`,
`test_reverify_of_unknown_entry_still_records_discovery`.

### 4. Score-stage robustness - real bug, fixed

- Fence stripping / lenient JSON already works (`test_gemini_parser.py`).
- `score_jobs_batch` converted items inside the same `try` as the API call, so a
  single bad item (`"score": "N/A"`, `null`) raised and the whole batch of 10 got
  the `scorer-error` fallback. A short array gave silent `score: 0` with no flag.
  Fixed with per-item isolation (only `matcher/gemini_scorer.py` parsing; prompt,
  rubric, model and batch size untouched).
- Bigger issue: scorer-error results were appended to `all_scores.jsonl`, which
  `_load_seen_keys` treats as "already scored", so transient failures were
  permanent. Evidence: 147 of 701 rows (21%) in `profiles/omer/all_scores.jsonl`
  are `scorer-error` - 137 are Gemini `503 UNAVAILABLE`, 10 one malformed batch
  (`Expecting ',' delimiter`). Those jobs were never scored and never will be.
  Fixed: scorer-error results are no longer logged as seen (retried next run),
  and `--rescore` no longer overwrites an existing score with a scorer-error 0.
  Tests: `test_one_malformed_item_does_not_drop_the_batch`,
  `test_short_response_flags_missing_items_as_scorer_error`,
  `test_scorer_errors_are_not_persisted_as_seen`,
  `test_rescore_error_does_not_clobber_existing_score`.

### 5. Atomicity - real (latent), fixed

`companies.json`, `new_jobs.json` (37 MB) and `live_positions.json` were written
with `open("w")` + `json.dump`, so a crash / Ctrl-C mid-dump left a truncated
file. In CI the commit step only runs on success, so a torn file would not be
committed, and there is no evidence it has happened; locally it would break the
next run (`companies.json`) or reset every `first_seen` to today (`new_jobs.json`
read failure is swallowed). Fixed with write-to-`.tmp` + `os.replace` in
`collect_jobs._write_json_atomic`, reused by `refresh_companies.save_companies`.
Tests: `test_collect_crash_mid_write_leaves_companies_json_intact`,
`test_collect_crash_mid_jobs_write_leaves_new_jobs_json_intact`,
`test_refresh_save_crash_leaves_companies_json_intact`.
`profiles/*/scored_jobs.json` (`score._save_scored_jobs`) has the same pattern and
was left alone (outside this spec's state files).

## Night run 2026-10-12
Shipped unattended (gate: pytest 85 passed + 1 strict xfail, score.py --dry-run green; review pass; scorer prompt/model/batch size byte-identical).
Morning QA:
1. Next weekly refresh: check "re-discovery found no ATS, keeping cached" lines - the kept entries still pull jobs.
2. Watch the daily Gemini quota - failed jobs now retry every run with no cap.
3. Run `score.py --dry-run` on `main` after the merge.
Follow-ups (Needs Omer): pullers raise on fetch failure (fixes modes 1 + 3, flip 4 tests in test_ats_schema.py + remove the xfail); restore the 503 stranded companies; delete 147 error rows from all_scores.jsonl; atomic write for scored_jobs.json; try/except around discover() in the refresh VC loop.
