# BUG: Pipeline filters are Yotam-only - not driven by each user's preferences

## Status
🔵 Open

## Severity
P2

## Description
The CI pipeline (`score.py`, then `scripts/push_scores_to_webapp.py`) filters and scores jobs with
one person's preferences only. Webapp users have their own filters, but those live in a second,
separate implementation that the pipeline never reads.

**Yotam's preferences hardcoded in the pipeline:**
- `score.py:_location_prefilter` (score.py:58) - keeps Israel or empty-location jobs, drops
  everything else including remote. No config knob.
- `score.py:_SKIP_TITLE_TERMS` / `_KEEP_TITLE_TERMS` - module defaults tuned for a senior data
  scientist (keep list is DS/ML/security titles).
- `profiles/yotam/score_config.json` - `skip_title_terms` (incl. `product manager`,
  `software engineer`, `analyst`), `keep_title_terms`, `skip_companies`, `lead_title_terms`.

**The webapp's own filters:**
- Stored per user in Supabase `score_configs` (`location_terms`, `skip_title_terms`,
  `keep_title_terms`, `skip_companies`, `skip_industries`), applied by
  `webapp/backend/db/filters.py:passes_filters` in `routers/scoring.py` and `routers/jobs.py`.

**Consequences:**
1. The pipeline only does work for profiles under `profiles/` (Yotam). Every other webapp user's
   jobs are scored only by the backend's `POST /score/auto` with their own key. The pipeline's
   scores reach the webapp only for accounts mapped in `WEBAPP_PROFILE_USERS`.
2. Two filter implementations that already disagree. Example: a job with an empty location is
   **kept** by `score.py:_location_prefilter` but **dropped** by `passes_filters` once any
   `location_terms` is set. Skip-industries exists only in the webapp. Lead-title routing
   (`lead_title_terms` -> `cv_lead`) exists only in the pipeline.
3. Collection-level `location_filter: israel` in `big_companies.yml` / `companies.json`
   (`collect_jobs.py:104`) drops non-Israel jobs for **all** users before anyone's filters run.
   Fine while the product is Israel-only, but it's a global preference, not a per-user one.

**Goal (when fixed):** one filter implementation, shared by the pipeline and the webapp, driven
per user/profile. The pipeline applies each user's own saved preferences (location terms,
skip/keep titles, skip companies/industries) instead of Yotam's hardcoded ones. Yotam becomes
just one user whose preferences happen to be in `profiles/yotam/score_config.json` (or in
Supabase).

**Decisions (Yotam, 2026-10-26):**
1. **Yotam's profile lives in two places, same format.** `profiles/yotam/` (repo) stays the
   training/eval/local-run copy - git-pinned so eval baselines are reproducible. His webapp
   account is an ordinary user in Supabase. What makes the system adapt is one shared
   format + one filter function, not one storage location:
   - `score_config.json` filter keys are renamed to match Supabase `score_configs`
     (`location_terms`, `skip_title_terms`, `keep_title_terms`, `skip_companies`,
     `skip_industries`); pipeline-only keys (`lead_title_terms`, `cv_default`, `cv_lead`) stay.
   - One filter function used by both `score.py` and the webapp backend.
   - Optional small script to push `profiles/yotam/` to his webapp account when he wants
     them in sync.
2. **The pipeline prefilters and scores for every webapp user, from that user's profile.**
   A US user gets US filters. Scoring uses the one shared Gemini key (`GEMINI_API_KEY`
   secret), not per-user keys.
3. **Location rule:** a job passes if its location matches one of the user's `location_terms`,
   or it is fully remote. Empty/unknown location is dropped. Same rule in pipeline and webapp.
4. **No hardcoded location default.** `_location_prefilter`'s Israel-only rule and the
   `_SKIP_TITLE_TERMS` / `_KEEP_TITLE_TERMS` module defaults go away; filters come only from
   the profile. Yotam's Israel filter becomes `location_terms` in his own config.
5. **No collection-level location filter.** Drop `location_filter` from `collect_jobs.py`
   (and `big_companies.yml` / `companies.json`); collect everything, filter per profile
   after collection.

**Consequences to handle in the implementation:**
- (2) One key for every user means every user's scoring spends the shared Gemini quota and
  bill. Needs a per-user cap (the webapp already has `scoring_runs_this_week`) and a decision
  on what happens to `/score/auto` and the per-user key in onboarding (keep as optional
  override, or remove).
- (3) "Fully remote" needs a definition: the location string contains `remote` and no
  on-site/hybrid marker? Remote-but-country-restricted (e.g. "Remote - US") should probably
  match only users whose `location_terms` cover that country. Decide in the spec.
- (5) Removing `location_filter` makes collection pull every global job from the big
  companies (Amazon, Microsoft, Google, Workday tenants...). Expect a much longer
  `collect_jobs.py`, a much larger `new_jobs.json` and Supabase `positions` table (free tier
  is 500 MB), and it makes BUG_WORKDAY_DETAIL_BEFORE_LOCATION_FILTER worse (detail fetch per
  global job). Measure row count/size before switching it off for all companies.
- Rubric for prompt-level behaviour is unchanged, but what reaches the scorer for Yotam must
  stay identical after the refactor (regression check: same job set passes his filters
  before and after, except the agreed empty-location change).

## Steps to Reproduce
1. Sign up on the webapp as a product manager with no title filters, or with
   `keep_title_terms: ["product manager"]`.
2. Run the CI pipeline (`collect_jobs.py` -> `sync_positions.py` -> `score.py` -> `push_scores_to_webapp.py`).
3. Expected: the pipeline applies the PM's own filters and their matching jobs get scored with
   the same filter rules used everywhere else.
   Actual: `score.py` filters with Yotam's lists only (which **skip** `product manager`), scores
   only Yotam's profile, and pushes only to Yotam's mapped account. The PM's jobs depend
   entirely on the separate `/score/auto` path and its separate filter code.

## Dependencies
- **Depends on:** —
- **Blocks:** WEBAPP_MULTI_PROFILE (shared per-profile filters would be built on this)
- **Touches:** score.py, profiles/yotam/score_config.json, webapp/backend/db/filters.py,
  webapp/backend/routers/scoring.py, webapp/backend/routers/jobs.py,
  scripts/push_scores_to_webapp.py, collect_jobs.py, big_companies.yml, companies.json,
  webapp/frontend/app/onboarding/page.tsx (Gemini key step), .github/workflows/collect-and-score.yml,
  tests/
- **Spec files to update:** CLAUDE.md (architecture section - score.py, collect_jobs.py;
  score_config schema), docs/scoring_calibration.md (if score_config.json changes),
  future_devs/SCORER_EVAL_HARNESS_SPEC.md (if profile/score_config changes),
  WEBAPP_SPEC.md (filters)
- **Night-ready:** no - shared Gemini key changes cost/quota (needs a cap decision),
  removing collection-level location_filter needs a size measurement against the Supabase
  free tier, and "fully remote" still needs a definition

## Fix Notes
<!-- populated after fix -->
