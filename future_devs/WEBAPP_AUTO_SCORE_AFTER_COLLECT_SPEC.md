| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `completed` |
| **Effort** | M |
| **Epic** | — |
| **Depends on** | WEBAPP_SCORE_NOW_BACKGROUND ✅ |
| **Blocks** | — |
| **Touches** | webapp/backend/routers/scoring.py, webapp/backend/tests/test_scoring_background.py, scripts/push_scores_to_webapp.py, tests/test_push_scores_to_webapp.py, .github/workflows/collect-and-score.yml, webapp/frontend/app/(app)/digest/page.tsx, webapp/frontend/app/(app)/help/page.tsx, webapp/frontend/app/privacy/page.tsx, webapp/frontend/app/landing/page.tsx, CLAUDE.md |
| **Night-ready** | no (needs secrets on GitHub + Render) |

## Overview
The website digest only filled when the user pressed Score now, so after each collection the new
matches sat in the pipeline's digest.md but not on the site. Three parts:
1. **Auto-score after collect** - CI calls `POST /score/auto` (shared secret); the backend scores new
   catalog jobs for every user with a saved key + profile, with their own key, in the background.
2. **Auto-continue** - a clean run that stopped at the 200 cap starts the next batch by itself while
   the digest is open (new and rescore modes).
3. **Push pipeline scores** - for profiles mapped in the `WEBAPP_PROFILE_USERS` secret, CI copies the
   pipeline's scores into that account (new jobs + rows scored without a description), so they are
   not scored twice; auto-score then skips them.

## Behaviour
- `/score/auto`: 403 unless `X-Cron-Secret` equals env `AUTO_SCORE_SECRET` (constant-time compare;
  unset secret = always 403). Returns 202 at once; users are processed one after another. A user with
  a running run is skipped. Per user, capped runs chain until the backlog is clear, a run comes up
  short (quota / failures - retried next collection) or `AUTO_SCORE_MAX_RUNS` (5) is hit.
  Auto runs (mode `auto`) never count toward the weekly limit. The user's own filters apply.
- Push: latest non-error score per url from `profiles/<name>/all_scores.jsonl`, live catalog jobs
  only, never overwrites a row that already has a description; upsert keeps `applied`/`status`.
  Uses the pipeline's filters, not the user's webapp filters (accepted trade-off).
- Both CI steps are `continue-on-error` and no-op when their secrets are missing.
- Help, privacy and landing copy say the key is also used automatically after each collection.

## How to QA
1. Set the secrets (see Needs Omer), run collect-and-score manually: the push step logs
   "pushed N scores", the auto step gets 202, and the digest fills without a click.
2. Render logs show `auto-score: user xxxxxxxx done N/M` lines; runs used stays unchanged.
3. Press "Re-score N" with N > 200 - batches continue by themselves until done.
4. `curl -X POST .../score/auto` without the header → 403.

## Needs Omer
- Render (careerwatch-api) env var `AUTO_SCORE_SECRET` = the same value as the GitHub secret.
- GitHub secrets `AUTO_SCORE_SECRET` and `WEBAPP_PROFILE_USERS` (`omer=<your website email>`).
