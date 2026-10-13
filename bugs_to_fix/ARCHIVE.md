# Bug Archive

Wrapped bugs only. Active bugs live in `BUG_TRACKER.md`.

| Slug | Title | Status | Severity |
|---|---|---|---|
| BUG_WEBAPP_STALE_JOBS_FROM_UNCOLLECTED_COMPANIES | Website keeps months-old jobs open when their company is no longer collected | ✅ Wrapped | P2 |
| BUG_GEMINI_CALL_NO_TIMEOUT | Gemini calls have no HTTP timeout - a hung call stalls a scoring run indefinitely | ✅ Wrapped | P2 |
| BUG_GEMINI_5XX_DROPS_JOBS | Gemini 5xx drops scoring batches instead of retrying; busy model wastes a call per batch | ✅ Wrapped | P2 |
| BUG_SCORED_JOBS_UNBOUNDED_GROWTH | scored_jobs.json keeps closed positions forever | ✅ Wrapped | P3 |
| BUG_WEBAPP_CLOSED_JOBS_NEVER_CLOSE | Website digest never marks closed positions as closed | ✅ Wrapped | P1 |
| BUG_VIOLA_GETRO_DUPES | Viola Getro board sends same 3 job titles to every portfolio company, burning Gemini quota on duplicates | ✅ Wrapped | P2 |
| BUG_RENDER_JOBS_PATH | Scoring endpoint always 503 - new_jobs.json unreachable on Render (re-fixed 2026-10-12: reads Supabase `positions`) | ✅ Wrapped | P0 |
| BUG_LANDING_DEAD_GITHUB_LINKS | Landing page GitHub links are dead (href="#") | ✅ Wrapped | P3 |
| BUG_MARK_APPLIED_MISSING | "Mark applied" button missing / not persisting on digest page | ✅ Wrapped | P2 |
| BUG_SMARTRECRUITERS_ROUTING | SmartRecruiters puller returns 0 jobs — site routing changed | ✅ Wrapped | P2 |
| BUG_SETTINGS_SAVED_STATE | Settings showed "No file chosen" after save; Digest checklist all-unchecked for a set-up user | ✅ Wrapped | P2 |
| BUG_TEST_KEY_STORED_ONLY | Settings "Test key" ignored the typed key; AIza-only placeholder/mask | ✅ Wrapped | P2 |
| BUG_AUTH_500_NO_CORS | Bad/expired token returned CORS-less 500 ("Failed to fetch") instead of 401 | ✅ Wrapped | P1 |
| BUG_SCORE_MISSING_KEY_EXIT0 | score.py exited 0 without GEMINI_API_KEY - CI green while nothing scored | ✅ Wrapped | P1 |
| BUG_CI_SYNC_BLOCKS_SCORING | Positions sync failure (paused Supabase) blocked the Score step in CI | ✅ Wrapped | P1 |
| BUG_SCORE_LOCAL_CV_PATH | score.py crashed in CI on local-only cv_default/cv_lead .docx paths | ✅ Wrapped | P1 |
| BUG_DIGEST_NO_FRESHNESS | Digest header had no last-collected timestamp | ✅ Wrapped | P3 |
