| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `completed` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | BUG_WEBAPP_FILTERS_NEVER_SAVED |
| **Blocks** | — |
| **Touches** | webapp/backend/db/filters.py, webapp/backend/routers/{jobs,scoring,user}.py, webapp/backend/tests/*, webapp/frontend/app/(app)/digest/page.tsx, webapp/frontend/app/(app)/settings/page.tsx, webapp/frontend/app/onboarding/page.tsx, webapp/frontend/app/components/JobCard.tsx, webapp/frontend/app/(app)/help/page.tsx |

## Overview
Saved Settings filters only decided what got scored next, so jobs scored before a filter
was set (2,600 worldwide rows after filters failed to save) stayed on the Digest. Also the
location filter took a single term, and "israel" misses ~16% of Israeli jobs whose
location is a bare city ("Herzliya").

## Behaviour
- One filter rule, `db/filters.passes_filters`, used by scoring (`_new_pending`) and the job
  list. `load_filters` reads the newest score_configs row (duplicates tolerated).
- `GET /jobs/` flags each row `outside_filters` (not dropped). The Digest hides flagged rows
  by default with "N jobs hidden by your saved filters - Show them"; applied jobs always show.
  Closed/tier counts and "Showing N of M" use the visible set.
- Location accepts several terms separated by commas or semicolons (Settings + onboarding);
  a job matches if its location contains any of them.

## How to QA
1. Settings - Filters: Location `israel, herzliya`, Save, reload: both terms shown.
2. Digest: non-Israel jobs gone; the hidden-count line appears; "Show them" brings them back.
3. A job marked applied outside the filter still shows.
