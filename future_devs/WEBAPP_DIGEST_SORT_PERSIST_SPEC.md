| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `completed` |
| **Effort** | S |
| **Epic** | WEBAPP_JOBSEEKER_WORKFLOW |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/digest/page.tsx` |
| **Night-ready** | 🌙 yes |

## Overview

Sort is implicit, filters reset on every reload, and there's no result count.

## Behaviour

- Explicit sort controls: score desc (default), date scored desc, company A-Z.
- Persist filter + sort + min-score state in `localStorage` so returning users keep their view.
- Show "Showing X of Y" and a small per-tier count summary (e.g. 9-10, 7-8, 5-6).

## Files to Touch

- `webapp/frontend/app/digest/page.tsx` — sort control, localStorage persistence of filter/sort/min-score, result count + per-tier summary

## How to QA

1. Changing sort reorders the list (score desc, date scored desc, company A-Z).
2. Filters, sort, and min-score persist across reload.
3. "Showing X of Y" and the per-tier count summary are shown.
4. `uv run python3 -m pytest tests/ -v` passes.
5. `uv run python score.py --dry-run` passes.

## Night run 2026-10-12
Shipped unattended (gate: pytest, score.py --dry-run, frontend build green; review pass). Morning QA (browser):
1. Switch between the three sorts - score high to low, newest scored first, company A-Z.
2. Set min score, text filters and sort, hard-reload - all restored; "Clear filters" resets sort to Score.
3. "Showing X of Y" and the 9-10 / 7-8 / 5-6 counts update as you filter; count line wraps cleanly at phone width.
4. Set `localStorage['cw.digest.view.v1']` to garbage and reload - defaults, no console errors.
Open questions: "Showing X of Y" counts applied/closed jobs in their own sections too; the "Show N applied" toggle is not persisted.
