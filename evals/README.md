# Scorer eval

Measures how well `matcher/gemini_scorer.py` agrees with Yotam's own scores on a
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

   Samples jobs stratified across the Gemini bands in `profiles/yotam/all_scores.jsonl`, plus
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

### Faster labelling and adding more labels

```bash
# slim sheet: type L / M / H in quick_band; the excerpt is the start of role_description
uv run python evals/make_labelling_sheet.py --n 60 --quick

# a second batch: quotas by Gemini band group (H = 7-10, M = 5-6, L = 0-4; a short group's
# remainder goes to the others in their ratio), skipping what is labelled, <= 2 jobs per company
uv run python evals/make_labelling_sheet.py --quick --n 100 --mix H=35,M=35,L=30 \
    --exclude evals/private/golden_set.jsonl --max-per-company 2 --out evals/private/labelling_sheet2.csv
uv run python evals/make_labelling_sheet.py --import evals/private/labelling_sheet2.csv --append

# --recheck 12 mixes 12 already-labelled jobs (4 per human L / M / H, Israel only) into the
# sheet to label again blind; import puts them in recheck.jsonl and prints your self-agreement -
# they never overwrite the golden set. --batch tags the new rows (existing ones become batch 1).
uv run python evals/make_labelling_sheet.py --import evals/private/labelling_final.csv --append --batch 2

# after a re-collect: re-fill role_description / responsibilities / requirements / ats
uv run python evals/make_labelling_sheet.py --refresh-sections
```

A `--quick` sheet keeps the full jobs in `<sheet>.jobs.jsonl` next to it - import needs it.
Gemini's score and band never reach the sheet or that file, and rows are shuffled.

### Job text mode

Gemini reads `role_description` + `requirements` (falling back to `description`).
`SCORER_TEXT=description` reproduces the pre-split prompt exactly. The baseline records the mode
(`scorer_text`) and it is part of `prompt_hash`, so compare runs in the same mode, or run both
modes to measure the switch.

## Checking a scoring change

```bash
uv run python evals/run_eval.py --baseline     # exits 1 if any metric regresses beyond tolerance
```

Run it before and after changing the prompt, rubric, batch size, model, `profile.md`, CV or
`score_config.json`, and report both numbers.

Exit codes: `0` pass, `1` regression or too many scorer errors (the gate failed), `2` bad input -
missing or empty golden set, `--runs` below 1, missing `GEMINI_API_KEY`, or a baseline that is
not valid JSON, lacks a gated metric, or measured nothing. A run that fails the gate never
writes a baseline.
