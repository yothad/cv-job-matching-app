# Scorer Eval Harness — measure whether Gemini's job scores are any good

| Field | Value |
|---|---|
| **Phase** | P13 |
| **Status** | `not-started` |
| **Effort** | S |
| **Epic** | — (standalone) |
| **Depends on** | SCORER_EVAL_HARNESS_CODE (the runner, metrics and labelling tool; this task is now the human part: label the golden set, record the baseline, turn on the CI gate) |
| **Blocks** | any future change to `matcher/gemini_scorer.py` prompt, rubric, batch size, or model |
| **Touches** | `evals/` (new), `matcher/gemini_scorer.py` (read-only), `docs/scoring_calibration.md`, `README.md`, `.github/workflows/` |
| **Night-ready** | no - labelling the golden set is Omer's (human grader); baseline needs live Gemini |
| **Owner** | — |

## Overview

`matcher/gemini_scorer.py` assigns a 0–10 score to every job in the pipeline, and the whole
digest is ranked by it. That number is currently **unvalidated**: `docs/scoring_calibration.md`
documents the rubric and a §3 "Calibration Spot-Check", but there is no labelled set and no
agreement metric. We cannot answer "did that prompt change make scoring better or worse?"
except by eyeballing a digest.

This task builds the missing measurement. It is deliberately small — a golden set, two
metrics, one CI gate — because the point is to *have a number*, not to build a platform.

**Reference:** `/Users/omerhedvat/git/ECC/skills/eval-harness/SKILL.md` (MIT) for the
vocabulary and structure — capability vs regression evals, the three grader types
(code-based / model-based / human), and pass@k. Follow its shape; the content below is
specific to this pipeline. Note what it does *not* provide: a runnable harness. That is
this task's actual work.

## Code shipped (SCORER_EVAL_HARNESS_CODE)

`evals/metrics.py`, `evals/run_eval.py` (`--golden`, `--profile`, `--runs`, `--baseline`,
`--write-baseline`), `evals/make_labelling_sheet.py` (make + `--import`), `evals/README.md`,
`tests/test_evals.py` (fake client). Confusion bands are 9-10 / 7-8 / 5-6 / 0-4 and hard-filter
flags are `dealbreaker-location` / `non-ds`. Because the repo is public, the golden set, sheet and
baseline default to the gitignored `evals/private/` instead of being committed (overrides the
"Committed to the repo" lines below). Remaining here: label, record the baseline, CI gate, docs.

## Behaviour

### `evals/golden_set.jsonl` (human-labelled, the ground truth)
- **50 real jobs** sampled from `live_positions.json` — stratified so every score band
  (9-10, 7-8, 5-6, 3-4, 0-2) is represented, and including the known-hard cases from
  `docs/scoring_calibration.md` §4 "Known Failure Modes".
- One line per job: `{job_id, company, title, location, description, label_score, label_band, label_flags, labelled_by, labelled_at, notes}`.
- `label_score` is **Omer's own score**, not Gemini's. This is a human-grader step and
  cannot be delegated to the model being evaluated — that would grade the scorer against itself.
- Committed to the repo. It is the asset; the harness around it is replaceable.

### `evals/run_eval.py`
- Re-scores every golden-set job through the real `score_jobs_batch(...)` path — same prompt,
  same batch size, same profile/CV injection — so the eval measures the shipped code path.
- Reports:
  - **Band accuracy** — % of jobs Gemini places in the same score band as the human label. This is the headline number.
  - **Mean absolute error** on the raw 0–10 score.
  - **Hard-filter recall** — of the jobs the human marked `dealbreaker-location` or non-DS, how many did Gemini also score ≤4? A miss here surfaces a bad job at the top of the digest, which is the failure mode that actually costs Omer time. Weight it separately; it must not be averaged away.
  - **Per-band confusion table**, so a regression shows *where* it moved.
- `--baseline evals/baseline.json` compares against the last recorded run and exits non-zero
  on regression beyond tolerance.
- **Run each job 3× and report pass@1 vs pass@3** (ECC's pass@k). Gemini at default
  temperature is not deterministic; a 1-point band wobble must be distinguishable from a
  real regression before anyone trusts the gate.
- `score_jobs_batch` returns `flags: ["scorer-error"]` (score 0) for a failed call or a
  malformed / missing item (per-item since PIPELINE_FAILURE_RESILIENCE). Count those
  separately and exclude them from band accuracy / MAE - they are infra noise, not scoring.
  But the run fails (exit 1) when more than 10% of results are `scorer-error`
  (`--max-error-share` / `tolerance.scorer_error_share`), and a baseline metric that comes
  back `n/a` counts as a regression - a dead model must never make the gate pass.

### `evals/baseline.json`
- The committed current-performance record: metric values, model name, prompt hash, date.
- Updated deliberately, in its own commit, with the reason stated. Never silently.

### CI gate
- A workflow (or an addition to the existing exit gate) that runs `evals/run_eval.py --baseline`
  on any PR touching `matcher/gemini_scorer.py`, `profile.md`, `cv.md`, or `profiles/*/score_config.json`.
- Gemini API cost per run is ~150 scored jobs — small, but gate it on those paths only, not on every push.

### Docs
- `docs/scoring_calibration.md` §3 gets replaced by the real numbers, with the spot-check
  demoted to an appendix.
- `README.md` states the band accuracy and hard-filter recall, with the date and sample size.
  **No number in the README without a run behind it.**

## Files to Touch
- `evals/golden_set.jsonl` — new (human labelling; the one step that cannot be automated)
- `evals/run_eval.py` — new
- `evals/baseline.json` — new
- `.github/workflows/` — new or extended workflow
- `docs/scoring_calibration.md` — replace §3 with measured results
- `README.md` — publish the headline metrics

## How to QA
1. `uv run python evals/run_eval.py` on the committed golden set prints band accuracy, MAE, hard-filter recall, and the confusion table.
2. Deliberately corrupt the rubric (e.g. delete the location hard-filter line from `profile.md`), re-run — hard-filter recall drops and `--baseline` exits non-zero. **This is the real test: an eval that never fails is not an eval.**
3. Restore, re-run — back to baseline, exit 0.
4. Run the full eval 3× — pass@1 vs pass@3 shows the run-to-run variance, and the baseline tolerance is set above that noise floor, not below it.
5. `uv run python3 -m pytest tests/ -v` passes.
6. `uv run python score.py --dry-run` passes.

## Why this task exists

Two reasons, and the second is not secondary:

1. **The pipeline needs it.** Every future prompt or rubric change is currently unmeasurable.
2. **Portfolio.** Eval design is the single most-cited 2026 AI-engineering screening signal,
   and this repo is a *shipped, cron-running LLM pipeline* — an eval here is worth more than
   the same eval on a toy project. A README that says "band accuracy 78% on a 50-job
   human-labelled golden set, hard-filter recall 94%, measured 2026-08" is the artifact.
   A README that says "scores jobs with Gemini" is not.
