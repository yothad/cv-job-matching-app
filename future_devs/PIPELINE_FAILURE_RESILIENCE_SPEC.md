| Field | Value |
|---|---|
| **Phase** | P11 |
| **Status** | `not-started` |
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
