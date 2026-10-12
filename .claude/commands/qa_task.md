---
model: sonnet
effort: high
---
# /qa_task

Run QA on a completed task before wrapping.

## Usage

```
/qa_task <slug>
```

## QA Tiers

### Tier 1 — Automated (always run)

- `uv run python3 -m pytest tests/ -v` — full test suite
- `uv run python score.py --dry-run` — pipeline sanity, no API calls
- `uv run python -c "import score, collect_jobs, refresh_companies; print('imports OK')"` — no broken imports
- For scoring changes: verify output JSON schema matches expected fields (`score`, `reasoning`, `flags`, `apply_url`)

### Tier 2 — Integration smoke test (run when pipeline logic changed)

Run against sample data:
```
uv run python score.py --sample
```
Verify:
- Pre-filter log line appears
- At least 1 job reaches Gemini
- `scored_jobs.json` and `digest.md` are updated
- `all_scores.jsonl` grows (append, not truncate)

### Tier 3 — Manual verification (run when output format changed)

- Open `profiles/omer/digest.md` — check formatting looks correct
- Spot-check 2-3 scored positions: score is 0-10, reasoning is a real sentence, flags are short strings
- If `Applied: 0` fields changed: verify sync from digest → `scored_jobs.json` works

### Tier 4 — Data integrity (run after filter or dedup changes)

- Confirm no duplicate `apply_url` entries in `scored_jobs.json`
- Confirm previously-scored jobs don't re-appear after a second run
- Confirm filtered titles (from `score_config.json`) don't appear in the pending list

## Pass criteria

All Tier 1 checks pass AND no Tier 2/3/4 regressions observed.

Under `/night_run`, the orchestrator's exit gate + review agent replace this command; Omer runs `/qa_task` in the morning for the morning-QA items.

On pass: print a QA summary and **STOP**. Do NOT invoke `/wrap_task`. The user must explicitly run `/wrap_task <slug>` to proceed.
On fail: return to `/start_task` Phase B, fix, re-run QA. Only surface to the user if the failure needs their judgement.
