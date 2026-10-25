---
model: sonnet
effort: high
---
# /orchestrate_epic

Execute all children of an epic in dependency-respecting waves.

## Usage

```
/orchestrate_epic <epic_slug>
```

e.g. `/orchestrate_epic WEBAPP`

## Behavior

### 1. Resolve children

- Read the epic's spec file to get the child list
- Filter out any already `wrapped` children
- Topologically sort by `Depends on` to determine wave order

### 2. Pre-flight

- `git status` must be clean (no uncommitted changes)
- All `Depends on` items for Wave 1 must be ✅

### 3. Wave grouping rules

| Condition | Rule |
|---|---|
| DB migration (Supabase schema change) | Solo wave — nothing else in same wave |
| Shared core module change (`score.py`, `collect_jobs.py`, `ats/`) | Solo wave |
| Disjoint file sets | Parallel in same wave |
| Max wave size | 5 children |

### 4. Present wave plan

Print the wave breakdown for visibility, then proceed immediately. Do NOT pause for user confirmation — Yotam trusts autonomous execution for this project. Only pause if the plan reveals something genuinely ambiguous (e.g. an undeclared dependency, conflicting Touches sets).

### 5. Execute wave by wave (autonomous)

For each wave:
1. Call `/start_task <slug>` (Phase A only — status flip + validation)
2. Dispatch sub-agents in parallel for Phase B (implementation)
   - Sub-agent prompt must include: spec content, Touches list, exit gate commands
   - Sub-agents must NOT call `/start_task` or `/wrap_task` themselves
3. After all sub-agents return: run exit gate
   - `uv run python3 -m pytest tests/ -v`
   - `uv run python score.py --dry-run`
4. If exit gate passes: flip all wave children to `completed`
5. Call `/qa_task` for each child — auto-chains to `/wrap_task` on pass
6. Proceed to the next wave without user confirmation

Only stop the epic mid-flight if: exit gate fails and the fix isn't obvious, scope expansion is needed, or a spec is ambiguous enough to require Yotam's judgement.

### 6. Epic completion

When all children are wrapped:
- Mark epic row as `wrapped` in `ROADMAP.md`
- Move epic row to `ROADMAP_ARCHIVE.md`
- Move epic spec to root archive (or `future_devs/archive/` if small)

## Sub-agent prompt template

```
You are implementing <slug> as part of the <epic> epic.

Spec: <full spec content>
Touches: <file list>

Implement exactly what the spec says. Do not expand scope.
Exit gate (run before stopping):
  uv run python3 -m pytest tests/ -v -k "<keyword>"
  uv run python score.py --dry-run

Report: files changed, test results, any scope questions.
```
