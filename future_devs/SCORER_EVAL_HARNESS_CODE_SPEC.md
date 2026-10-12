| Field | Value |
|---|---|
| **Phase** | P13 |
| **Status** | `in-progress` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | SCORER_EVAL_HARNESS |
| **Touches** | `evals/` (new: `run_eval.py`, `metrics.py`, `make_labelling_sheet.py`, `README.md`), `tests/test_evals.py` (new), `.gitignore`, `matcher/gemini_scorer.py` (read-only) |
| **Night-ready** | 🌙 yes |

## Overview

Code half of `SCORER_EVAL_HARNESS` (read that spec first - it defines the metrics, file formats and CI gate). This task builds everything that does not need a human or a live Gemini call, so Omer only has to label jobs and run it.

## Behaviour

- `evals/metrics.py` - pure functions: band accuracy, MAE, hard-filter recall, confusion table (bands 9-10 / 7-8 / 5-6 / 0-4), pass@k across repeated runs. No I/O.
- `evals/run_eval.py` - loads the golden set, re-scores it through the real `score_jobs_batch(...)` path (same prompt, model, batch size as production - import, never copy, the scorer), prints the metrics, `--runs k` for pass@k, `--baseline <file>` compares and exits non-zero on a regression beyond the tolerance stored in the baseline file, `--write-baseline <file>` records one. The Gemini client is injectable so tests use a fake.
- **Privacy (repo is public):** the golden set holds Omer's personal labels. Default golden-set and baseline paths live under a gitignored directory (`evals/private/`, added to `.gitignore`); paths are overridable by flags/env. Nothing personal is committed.
- `evals/make_labelling_sheet.py` - samples N jobs (default 60, stratified across the score bands of the last `profiles/omer/all_scores.jsonl` run plus jobs the hard filters dropped) from `new_jobs.json` into a CSV in `evals/private/` with empty `label_score`, `label_band`, `label_flags`, `notes` columns, and `--import <csv>` converts the filled sheet to `golden_set.jsonl`.
- `evals/README.md` - the 3-step human workflow: make sheet, label, import + `--write-baseline`.
- Tests (`tests/test_evals.py`): metric functions on hand-made fixtures; `run_eval.py` end to end with a fake client and a synthetic 6-job golden set (exit 0 at baseline, non-zero after a simulated regression); sheet round-trip import.
- Do NOT change `matcher/gemini_scorer.py`, `profile.md` or `score.py`. Do NOT call Gemini. Do NOT add the CI workflow step yet (it needs the real golden set - parent task).

## Files to Touch

`evals/run_eval.py`, `evals/metrics.py`, `evals/make_labelling_sheet.py`, `evals/README.md`, `tests/test_evals.py`, `.gitignore`; update `future_devs/SCORER_EVAL_HARNESS_SPEC.md` with a "Code shipped" note per CLAUDE.md spec routing.

## How to QA

1. `uv run python3 -m pytest tests/test_evals.py -v` passes (fake client, no network).
2. `uv run python evals/make_labelling_sheet.py --n 20` writes a CSV under `evals/private/` and `git status` shows nothing new to commit there.
3. `uv run python evals/run_eval.py --help` documents `--runs`, `--baseline`, `--write-baseline`, and the golden-set path flag.
4. Full `pytest tests/` and `score.py --dry-run` still pass.
