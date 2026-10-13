# BUG: Gemini 5xx drops scoring batches instead of retrying; busy model wastes a call per batch

## Status
🟢 Completed

## Severity
P2

## Description
On 2026-10-13 webapp Score now reported "Scored 580 new jobs - Some jobs were not scored:
500 INTERNAL". The Render logs show two problems in `matcher/gemini_scorer.py`:

1. **5xx is never retried.** `score_jobs_batch` / `score_job` back off and retry only on 429.
   When every model in the cascade answers 500/503, the error falls into the non-429 branch and
   the whole batch becomes `scorer-error` on the first attempt. Those jobs are dropped for the
   run. `gap_analyzer._call_gemini` raises immediately the same way.
2. **A busy model is retried on every batch.** `gemini-3.5-flash` returned 503 on nearly every
   batch before the cascade fell back to `gemini-3.5-flash-lite`. Each batch spent one wasted
   call on the busy model, outside the 8 RPM pacing, which also invites 429s.

Not a prompt/rubric/model/batch change, so the eval gate doesn't apply: this changes the retry and
model-order policy only.

## Steps to Reproduce
1. A Gemini key on a project where `gemini-3.5-flash` is overloaded (503) and Google's backend
   intermittently returns 500.
2. Click Score now on the webapp digest (or run `score.py`).
3. Expected: transient 5xx is retried with backoff; a busy model is skipped for a while.
   | Actual: the batch is dropped on the first 5xx, and every batch first calls the busy model.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** `matcher/gemini_scorer.py`, `matcher/gap_analyzer.py`, `tests/test_gemini_cascade.py`
- **Spec files to update:** `CLAUDE.md` architecture section (score.py cascade line), `future_devs/SCORER_EVAL_HARNESS_SPEC.md` (note: retry policy only, no model change)
- **Night-ready:** no - filed and fixed in a daytime session
- **Owner split (2026-10-13):** the careers-day session owns `webapp/backend/routers/scoring.py` (background scoring, re-score rows without descriptions). This bug must not touch it.

## Fix Notes
- `generate()` orders the cascade by cooldown: a model that answered 429/5xx is tried last for
  `_COOLDOWN_S` (120s) and is never dropped. Saves the wasted call on a busy `gemini-3.5-flash`.
- `_is_retryable()`: 429/quota or 5xx. `score_jobs_batch` / `score_job` back off and retry 5xx like
  429. If 5xx is still failing on the last attempt, the jobs return as `scorer-error` (not saved,
  retried next run) instead of raising `QuotaExhaustedError`, which would end the whole Score now run.
- `gap_analyzer._call_gemini` uses the same retry rule.
- Tests (`tests/test_gemini_cascade.py`): cooldown skips the busy model, cooling models are still
  tried last, transient 5xx on every model is retried, lasting 5xx yields scorer-error not a stop.
