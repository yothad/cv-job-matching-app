---
model: sonnet
effort: high
---
# /file_task

File a new bug or feature task.

## Usage

```
/file_task <description>
```

## Behavior

### Phase 1 — Parse & Draft

1. Detect type: **bug** or **feature**
2. For bugs: check `bugs_to_fix/BUG_TRACKER.md` for an existing similar entry — prefer updating over filing a duplicate
3. For features: check `ROADMAP.md` to see if a related item already exists
4. Generate a slug: `BUG_<SCREAMING_SNAKE>` for bugs, `<SCREAMING_SNAKE>` for features
5. Identify affected files (Touches)
6. Identify which spec files need updating when this ships

### Phase 2 — Write

**Bug → `bugs_to_fix/BUG_<slug>.md`:**
```markdown
# BUG: <title>

## Status
🔵 Open

## Severity
P<0-3>

## Description
<root cause + affected scripts/modules>

## Steps to Reproduce
1. <precondition>
2. <exact steps>
3. Expected: <X> | Actual: <Y>

## Dependencies
- **Depends on:** <slug or —>
- **Blocks:** <slug or —>
- **Touches:** <file list>
- **Spec files to update:** <spec list or —>
- **Night-ready:** 🌙 yes | no — <reason>

## Fix Notes
<!-- populated after fix -->
```

Then add a row to `bugs_to_fix/BUG_TRACKER.md`:
```
| [BUG_slug](BUG_slug.md) | Title | 🔵 Open | P<N> | — | — | — |
```

**Feature → `future_devs/<slug>_SPEC.md`:**
```markdown
| Field | Value |
|---|---|
| **Phase** | P<N> |
| **Status** | `not-started` |
| **Effort** | XS/S/M/L/XL |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | <file list> |
| **Night-ready** | 🌙 yes / no — <reason> |

## Overview
<what + why>

## Behaviour
<rules, edge cases>

## Files to Touch
<exact list>

## How to QA
1. <falsifiable step>
2. <falsifiable step>
3. <falsifiable step>
```

Then add a row to the appropriate phase in `ROADMAP.md` and a line in the Spec Index.

## Night-ready (🌙)

Set `🌙 yes` only when an unattended `/night_run` can take the task from spec to a green exit gate alone:
- The spec is unambiguous and every "How to QA" step is either automatable or explicitly a morning-QA check.
- No human-only step: no Supabase SQL / schema change, no secrets or env vars, no scorer prompt/rubric/model/batch change (eval-gated), no login, no force push, no deleting data.
- Depends on items are wrapped (or ship earlier in the same run).
Otherwise write `no — <reason>`. Marking a task night-ready is a daytime, human-present decision; the night run never sets it.

## Severity guide (bugs)

| Severity | Meaning |
|---|---|
| P0 | Pipeline broken — nothing scores, data loss |
| P1 | Wrong results surfaced, significant scoring errors |
| P2 | UX / output quality issue, workaround exists |
| P3 | Polish / cosmetic |

## Effort guide (features)

| Size | Scope |
|---|---|
| XS | < 1 hour, single file |
| S | 1–2 days |
| M | 3–5 days |
| L | 1–2 weeks |
| XL | 2+ weeks |
