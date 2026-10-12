---
model: sonnet
effort: high
---
# /start_task

Begin work on a bug or feature task.

## Usage

```
/start_task <slug>
```

e.g. `/start_task BUG_VIOLA_GETRO_DUPES` or `/start_task WEBAPP_AUTH`

## Behavior

### Phase A — Always runs (including when called from /orchestrate_epic)

1. Read the task spec (`bugs_to_fix/<slug>.md` or `future_devs/<slug>_SPEC.md`)
2. Verify all `Depends on` items are ✅ wrapped — block if not
3. Flip status to `🟡 In Progress` (bug) or `in-progress` (feature) in tracker + spec
4. Print **Touches** list — these are the only files that should change
5. If this task is a child of an epic, update the epic's rollup count in `ROADMAP.md`
6. If called from `/orchestrate_epic`: **stop here** — do not implement

### Phase B — Implementation (manual invocation only)

7. Implement the fix or feature per the spec
8. Exit gate before marking complete:
   - Run relevant tests: `uv run python3 -m pytest tests/ -v -k "<relevant keyword>"`
   - Run pipeline sanity: `uv run python score.py --dry-run`
   - No import errors, no tracebacks
9. Flip status to `🟢 Completed` (bug) or `completed` (feature)
10. Print summary of what changed

**STOP HERE.** Do not auto-invoke `/qa_task` or `/wrap_task`. The task stays `completed` until the user explicitly runs `/wrap_task <slug>`.

## Rules

- Exception: under `/night_run` the orchestrator drives the task end to end (dev → gate → review → `completed`) on the `night/<date>` branch; it still never wraps or touches `main`.

- Never touch files outside the **Touches** list without updating the spec first
- Never mark `completed` if the sanity checks fail
- If scope expands during implementation, pause and update the spec before continuing
- Do NOT auto-chain to QA or wrap — always stop at `completed` and wait for the user
