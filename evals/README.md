# Scorer eval

Measures how well `matcher/gemini_scorer.py` agrees with Omer's own scores on a
human-labelled golden set. It re-scores the set through the production path
(`score._score_jobs_batched` -> `score_jobs_batch`, same prompt, model, batch size and CV routing)
and reports:

- **Band accuracy** - share of jobs Gemini puts in the human's band (9-10 / 7-8 / 5-6 / 0-4). Headline number.
- **MAE** on the raw 0-10 score.
- **Hard-filter recall** - of jobs labelled `dealbreaker-location` or `non-ds`, the share Gemini scored <= 4. Reported separately, never averaged in.
- **Confusion table** (human band x Gemini band).
- **pass@1 / pass@k / pass^k** with `--runs k` (any run / every run in the right band).

`scorer-error` results are counted and excluded from every metric. If more than 10% of results
(jobs x runs) are `scorer-error`, the run fails with exit 1 - a dead model or key must never
look like a pass. Override with `--max-error-share 0.2` or `tolerance.scorer_error_share` in the
baseline file. A metric the baseline has but this run could not compute (`n/a`) counts as a
regression.

## Privacy

The golden set holds personal labels and the repo is public. Everything lives under the
gitignored `evals/private/`: `labelling_sheet.csv`, `golden_set.jsonl`, `baseline.json`.
Override with `--golden` / `--baseline` flags or the `EVAL_GOLDEN_SET` / `EVAL_BASELINE` env vars.

## Workflow

1. **Make the sheet**

   ```bash
   uv run python evals/make_labelling_sheet.py --n 60
   ```

   Samples jobs stratified across the Gemini bands in `profiles/omer/all_scores.jsonl`, plus
   jobs from `new_jobs.json` that score.py's hard filters drop. Gemini's score is not in the
   sheet, so the labelling stays blind.

2. **Label** - open `evals/private/labelling_sheet.csv` and fill `label_score` (0-10, your own
   judgement). Optional: `label_band` (overrides the band derived from the score), `label_flags`
   (comma separated, e.g. `dealbreaker-location, non-ds`), `notes`. Rows left blank are skipped.

3. **Import and record the baseline** (needs `GEMINI_API_KEY`)

   ```bash
   uv run python evals/make_labelling_sheet.py --import evals/private/labelling_sheet.csv
   uv run python evals/run_eval.py --runs 3 --write-baseline
   ```

   Then edit `evals/private/baseline.json`: fill `reason`, and set `tolerance` above the
   run-to-run noise that pass@1 vs pass@3 shows.

## Checking a scoring change

```bash
uv run python evals/run_eval.py --baseline     # exits 1 if any metric regresses beyond tolerance
```

Run it before and after changing the prompt, rubric, batch size, model, `profile.md`, CV or
`score_config.json`, and report both numbers.
