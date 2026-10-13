| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `completed` |
| **Effort** | S |
| **Epic** | WEBAPP_JOBSEEKER_WORKFLOW |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/(app)/digest/page.tsx` (+ a small `webapp/frontend/lib/` helper if useful) |
| **Night-ready** | 🌙 yes |

## Overview

Returning users can't tell what's new since they last looked - core to a recurring-use product.

## Behaviour

- Track `last_seen_at` in the browser (localStorage key per user id, every read/write wrapped in try/catch so a blocked storage just disables the feature) - decided 2026-10-12: per-browser, not cross-device, so no schema change. Updated when the digest loads. Jobs scored after the PREVIOUS `last_seen_at` get a "New" badge and a top summary "X new since your last visit".
- A quick "show only new" filter.
- Read the previous `last_seen_at` to compute "new", then update it to now - so the very next visit clears the "new" markers.
- Edge case: first-ever visit (no prior `last_seen_at`). Pick and document one behaviour: either show everything as new, or suppress the banner on first visit. (Documented choice: suppress the banner on first visit and do not badge anything, since "everything is new" is noise on first run.)

## Files to Touch

- `webapp/frontend/app/(app)/digest/page.tsx` — read/update `last_seen_at` in localStorage, "New" badge (compare each job's `scored_at`), summary banner, "show only new" filter
- No backend or schema change.

## How to QA

1. After a scan, jobs scored since the previous visit show a "New" badge and the summary count.
2. Reloading and returning clears "new" on the next visit (previous `last_seen_at` advanced).
3. The "show only new" filter works.
4. First-ever visit follows the documented behaviour (banner suppressed, nothing badged).
5. Storage blocked (private window) - the digest still renders, just without badges.
6. `npm run build` passes; `uv run python3 -m pytest tests/ -v` passes.
7. `uv run python score.py --dry-run` passes.

## Night run 2026-10-12
Shipped unattended (gate: pytest, score.py --dry-run, frontend build green; `node --test webapp/frontend/tests/*.mjs` 13/13; review pass).
Morning QA (browser):
1. Put an older `cw.digest.lastSeen.v1:<uid>` value in localStorage and load /digest - "New" badges, "N new since your last visit" banner, "Show only new" changes "Showing X of Y"; reload - badges gone.
2. First visit (key removed) - no banner, no badges. Private window - digest renders, no console error.
3. Leaving the digest and coming back within the app counts as a new visit. Decide whether it should be per session instead.
Open questions: jobs scored via "Score now" during a visit show as New again on the next visit; "Show only new" is not persisted; the banner count ignores the text filters.
