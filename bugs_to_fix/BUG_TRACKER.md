# Bug Tracker

Active bugs only. Wrapped bugs live in `ARCHIVE.md`.

| Slug | Title | Status | Severity | Depends on | Blocks | Files Changed |
|---|---|---|---|---|---|---|
| [BUG_WEBAPP_FILTERS_NEVER_SAVED](BUG_WEBAPP_FILTERS_NEVER_SAVED.md) | Settings filters are never saved (Save failed, empty on reload) | 🟢 Completed | P1 | — | — | webapp/backend/routers/user.py |
| [BUG_POSITIONS_DETAIL_DUP_LINK](BUG_POSITIONS_DETAIL_DUP_LINK.md) | Positions detail panel shows "Go to posting" twice (button + redundant inline link) | 🟢 Completed | P3 | — | — | — |
| [BUG_WORKDAY_DETAIL_BEFORE_LOCATION_FILTER](BUG_WORKDAY_DETAIL_BEFORE_LOCATION_FILTER.md) | Workday puller fetches every global job's description before location_filter (GE HealthCare ~30 min silent) | 🔵 Open | P2 | — | — | — |
| [BUG_PIPELINE_FILTERS_YOTAM_ONLY](BUG_PIPELINE_FILTERS_YOTAM_ONLY.md) | Pipeline filters are Yotam-only - not driven by each user's preferences | 🔵 Open | P2 | — | WEBAPP_MULTI_PROFILE | — |
| [BUG_DESCRIPTION_COMPANY_BOILERPLATE](BUG_DESCRIPTION_COMPANY_BOILERPLATE.md) | Job description text leads with company boilerplate, not the role (excerpt + text feature) | 🟢 Completed | P2 | — | — | ats/utils.py, ats/comeet.py, ats/lever.py, ats/amazon_jobs.py, ats/* (cap removed), collect_jobs.py, matcher/gemini_scorer.py, evals/make_labelling_sheet.py, evals/run_eval.py |
