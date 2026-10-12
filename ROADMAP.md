# CareerWatch — Roadmap

> Active tasks only. Wrapped items live in `ROADMAP_ARCHIVE.md`.
> Read the relevant spec before touching files in that domain.
> Use `/tasks_status` for a dashboard view.

---

## Status Legend

| Symbol | Meaning |
|---|---|
| `not-started` | Ready to build (all dependencies met) |
| `in-progress` | Currently being implemented |
| `completed` | Dev done, awaiting `/qa_task` |
| `wrapped` | QA passed, committed, archived |

## Effort Legend

| Size | Scope |
|---|---|
| XS | < 1 hour, single file |
| S | 1–2 days |
| M | 3–5 days |
| L | 1–2 weeks |
| XL | 2+ weeks |

---

## Epics

| Slug | Title | Status | Effort | Children |
|---|---|---|---|---|
| [WEBAPP_FIRST_RUN_COMPREHENSION](future_devs/archive/WEBAPP_FIRST_RUN_COMPREHENSION_SPEC.md) | First-run comprehension (what/why/what-you-get before & during onboarding) | `wrapped` | L | 5 |
| [WEBAPP_JOBSEEKER_WORKFLOW](future_devs/WEBAPP_JOBSEEKER_WORKFLOW_SPEC.md) | Job-seeker workspace (detail view, status tracker, hide, new, sort) | `in-progress` | L | 5 (1 wrapped) |
| [WEBAPP_APP_SHELL_ACCOUNT](future_devs/archive/WEBAPP_APP_SHELL_ACCOUNT_SPEC.md) | App shell + account UX (nav, sign-out, help, auth recovery) | `wrapped` | M | 4 |
| [POSITION_LIVENESS](future_devs/archive/POSITION_LIVENESS_SPEC.md) | Position liveness — mark & surface closed postings in the scored digest | `wrapped` | M | 4 |
| [WEBAPP_VISUAL_DESIGN](future_devs/archive/WEBAPP_VISUAL_DESIGN_SPEC.md) | Webapp visual design system + appearance overhaul (Fable) | `wrapped` | L | 5 |

Run `/orchestrate_epic <slug>` to execute an epic's children in waves.

---

## Phase P0 — Pipeline (complete)

All Phase P0 tasks are wrapped. See `ROADMAP_ARCHIVE.md`.

---

## Phase P1 — Pipeline improvements (complete)

All Phase P1 tasks are wrapped. See `ROADMAP_ARCHIVE.md`.

---

## Phase P2 — Web App v1 (complete)

All Phase P2 tasks are wrapped. See `ROADMAP_ARCHIVE.md`.

---

## Phase P2 — Web App v1 (post-launch)

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_SUPABASE_SETUP_GUIDE](future_devs/archive/WEBAPP_SUPABASE_SETUP_GUIDE_SPEC.md) | Supabase initial setup guide (schema, OAuth, RLS) | `wrapped` | XS | — |
| [WEBAPP_PDF_CV_UPLOAD](future_devs/archive/WEBAPP_PDF_CV_UPLOAD_SPEC.md) | PDF CV upload in onboarding Step 2 | `wrapped` | S | — |
| [WEBAPP_OLD_PROFILE_BADGE](future_devs/archive/WEBAPP_OLD_PROFILE_BADGE_SPEC.md) | "Scored with old profile" badge on digest cards | `wrapped` | S | — |

---

## Phase P3 — Coverage expansion

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [NEW_VC_ADAPTERS](future_devs/archive/NEW_VC_ADAPTERS_SPEC.md) | Add VC adapters: State of Mind / Sequoia IL / Aleph / Lightspeed IL / Greylock / Insight IL | `wrapped` | M | — |
| [TLV_PORTFOLIO_FIX](future_devs/archive/TLV_PORTFOLIO_FIX_SPEC.md) | Fix TLV Partners scraper + clean stale entries + add missing portfolio companies | `wrapped` | M | — |
| [BIG_COMPANIES_ATS_PARAMS](future_devs/archive/BIG_COMPANIES_ATS_PARAMS_SPEC.md) | Fill ATS params for ~30 unfilled big_companies.yml stubs | `wrapped` | M | — |
| [PIPELINE_TEST_COVERAGE](future_devs/archive/PIPELINE_TEST_COVERAGE_SPEC.md) | Add test suite for pipeline scripts (ATS pullers, filters, scorer parser) | `wrapped` | M | — |

---

## Phase P4 — Portfolio showcase

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [DS_ANALYSIS_NOTEBOOK](future_devs/archive/DS_ANALYSIS_NOTEBOOK_SPEC.md) | DS analysis notebook — score distribution, VC tier signal, top companies | `wrapped` | S | — |
| [REPO_SHOWCASE](future_devs/archive/REPO_SHOWCASE_SPEC.md) | README rewrite — engineering showcase with architecture diagram and scale callouts | `wrapped` | S | — |
| [SCORING_RUBRIC_ABLATION](future_devs/archive/SCORING_RUBRIC_ABLATION_SPEC.md) | Scoring calibration doc — rubric design, spot-check, failure modes | `wrapped` | S | — |

---

## Phase P5 — Webapp v2 improvements

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_CV_SETTINGS_UPLOAD](future_devs/archive/WEBAPP_CV_SETTINGS_UPLOAD_SPEC.md) | CV re-upload section in Settings (outside onboarding) | `wrapped` | S | — |
| [WEBAPP_CV_UPLOAD_FORMATS](future_devs/archive/WEBAPP_CV_UPLOAD_FORMATS_SPEC.md) | CV upload: add DOCX + TXT support alongside PDF | `wrapped` | S | WEBAPP_PDF_CV_UPLOAD ✅ |
| [WEBAPP_SETTINGS_STATE_VISIBILITY](future_devs/archive/WEBAPP_SETTINGS_STATE_VISIBILITY_SPEC.md) | Settings shows current state: CV file/text, filters, API-key present/missing, account name+email | `wrapped` | S | — |
| [WEBAPP_PROFILE_UPLOAD_OR_PROMPT](future_devs/archive/WEBAPP_PROFILE_UPLOAD_OR_PROMPT_SPEC.md) | Profile upload OR AI-prompt generator for building profile.md | `wrapped` | M | — |
| [WEBAPP_POSITIONS_VIEW](future_devs/archive/WEBAPP_POSITIONS_VIEW_SPEC.md) | Positions page — browse all open roles from pipeline | `wrapped` | S | WEBAPP_COMPANIES_VIEW ✅ |
| [PROFILE_CV_GAP_ANALYSIS](future_devs/archive/PROFILE_CV_GAP_ANALYSIS_SPEC.md) | Gap analysis: profile vs CV, position vs CV, position vs profile | `wrapped` | M | — |
| [WEBAPP_COUNTUP_ANIMATION](future_devs/archive/WEBAPP_COUNTUP_ANIMATION_SPEC.md) | Count-up animation on Companies + Positions page load | `wrapped` | XS | — |
| [POSITION_FIRST_SEEN](future_devs/archive/POSITION_FIRST_SEEN_SPEC.md) | Stamp first_seen date on each position — persist across daily runs, show in digest + webapp cards | `wrapped` | S | — || [WEBAPP_POSITIONS_CATALOG_SYNC](future_devs/WEBAPP_POSITIONS_CATALOG_SYNC_SPEC.md) | Shared `positions` catalog auto-synced from pipeline — Positions page shows the full market to every user, not per-user scored_jobs | `in-progress` | S | WEBAPP_POSITIONS_VIEW ✅ |
| [WEBAPP_POSITIONS_DETAIL_DESCRIPTION](future_devs/WEBAPP_POSITIONS_DETAIL_DESCRIPTION_SPEC.md) | Positions detail: show real job description (add `description` to shared catalog + sync + endpoint) | `not-started` | S | WEBAPP_POSITIONS_CATALOG_SYNC |

---

## Phase P6 — AI / Experimental

### Epic: RAG_CHATBOT (Fable)

RAG sandbox + "Chat with the Job Market" chatbot. Assigned to **Fable**: the
spec is fully pinned (see the "Pre-flight decisions" block in the epic root), so
the work is execution-shaped. Split into three children — run under
`/start_task`, and review child 1's retrieval golden set before starting child 2.

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [RAG_CHATBOT](future_devs/RAG_CHATBOT_SPEC.md) | RAG sandbox + chat epic (root + shared brief) | `not-started` | L | — |
| [RAG_CORE](future_devs/archive/RAG_CORE_SPEC.md) | `rag/` module: ingest + query + refresh (CLI-runnable retrieval core) | `wrapped` | M | RAG_CHATBOT |
| [RAG_EMBEDDINGS_BACKFILL](future_devs/RAG_EMBEDDINGS_BACKFILL_SPEC.md) | Finish full embedding ingest (blocked on free-tier 1k/day quota) + re-run golden set on complete store | `not-started` | XS | RAG_CORE ✅ |
| [RAG_CHAT_API](future_devs/RAG_CHAT_API_SPEC.md) | `POST /api/chat` router over `rag/query.py` + rate limit | `not-started` | S | RAG_CORE ✅ |
| [RAG_CHAT_UI](future_devs/RAG_CHAT_UI_SPEC.md) | `/chat` page + Sources panel + nav link | `not-started` | S | RAG_CHAT_API |

### Downstream

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [MULTI_AGENT_RESUME_TAILOR](future_devs/MULTI_AGENT_RESUME_TAILOR_SPEC.md) | Actor/critic multi-agent resume tailor for high-scoring jobs | `not-started` | M | RAG_CHATBOT |

---

## Phase P7 — Webapp UX & first-run experience

First-time-user comprehension, digest trust, the job-seeker workspace, and the app shell. Filed from a UX review of the live webapp through a new job-seeker's eyes: what they need, what's missing, and which explanations a first-timer lacks.

### Epic: First-run comprehension

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_FIRST_RUN_COMPREHENSION](future_devs/archive/WEBAPP_FIRST_RUN_COMPREHENSION_SPEC.md) | First-run comprehension (epic root) | `wrapped` | L | — |
| [WEBAPP_LANDING_REVAMP](future_devs/archive/WEBAPP_LANDING_REVAMP_SPEC.md) | Landing revamp — value prop, BYO-key explainer, digest preview, FAQ | `wrapped` | S | WEBAPP_FIRST_RUN_COMPREHENSION ✅ |
| [WEBAPP_ONBOARDING_ORIENTATION](future_devs/archive/WEBAPP_ONBOARDING_ORIENTATION_SPEC.md) | Onboarding orientation + why-this-matters copy + setup summary | `wrapped` | S | WEBAPP_FIRST_RUN_COMPREHENSION ✅ |
| [WEBAPP_PROFILE_EXAMPLE_GUIDANCE](future_devs/archive/WEBAPP_PROFILE_EXAMPLE_GUIDANCE_SPEC.md) | Profile example + section guidance + completeness hint | `wrapped` | S | WEBAPP_FIRST_RUN_COMPREHENSION ✅ |
| [WEBAPP_FILTER_PLAIN_LANGUAGE_PREVIEW](future_devs/archive/WEBAPP_FILTER_PLAIN_LANGUAGE_PREVIEW_SPEC.md) | Plain-language filters + live "X of Y jobs" preview | `wrapped` | M | WEBAPP_FIRST_RUN_COMPREHENSION ✅ |
| [WEBAPP_ONBOARDING_KEY_TEST](future_devs/archive/WEBAPP_ONBOARDING_KEY_TEST_SPEC.md) | Inline "Test key" in onboarding Step 3 | `wrapped` | XS | WEBAPP_FIRST_RUN_COMPREHENSION ✅ |

### Epic: Job-seeker workspace

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_JOBSEEKER_WORKFLOW](future_devs/WEBAPP_JOBSEEKER_WORKFLOW_SPEC.md) | Job-seeker workspace (epic root) | `in-progress` | L | — |
| [WEBAPP_APPLICATION_TRACKER](future_devs/WEBAPP_APPLICATION_TRACKER_SPEC.md) | Application status tracker (saved/applied/interviewing/...) | `not-started` | M | WEBAPP_JOBSEEKER_WORKFLOW |
| [WEBAPP_POSITIONS_MARK_APPLIED](future_devs/WEBAPP_POSITIONS_MARK_APPLIED_SPEC.md) | Mark-applied on Positions (shared catalog) — needs per-user overlay; confirm scope first | `not-started` | S | WEBAPP_POSITIONS_CATALOG_SYNC |
| [WEBAPP_HIDE_DISMISS_JOBS](future_devs/WEBAPP_HIDE_DISMISS_JOBS_SPEC.md) | Hide / dismiss irrelevant jobs | `not-started` | S | WEBAPP_JOBSEEKER_WORKFLOW |
| [WEBAPP_NEW_SINCE_LAST_VISIT](future_devs/WEBAPP_NEW_SINCE_LAST_VISIT_SPEC.md) | "New since last visit" badges + filter | `not-started` | S | WEBAPP_JOBSEEKER_WORKFLOW |
| [WEBAPP_DIGEST_SORT_PERSIST](future_devs/WEBAPP_DIGEST_SORT_PERSIST_SPEC.md) | Sort controls + persist filter/sort view + counts | `completed` | S | WEBAPP_JOBSEEKER_WORKFLOW |

### Epic: App shell & account UX

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_APP_SHELL_ACCOUNT](future_devs/archive/WEBAPP_APP_SHELL_ACCOUNT_SPEC.md) | App shell + account UX (epic root) | `wrapped` | M | — |
| [WEBAPP_GLOBAL_APP_SHELL_NAV](future_devs/archive/WEBAPP_GLOBAL_APP_SHELL_NAV_SPEC.md) | Global nav shell + sign-out + auth guard | `wrapped` | M | WEBAPP_APP_SHELL_ACCOUNT ✅ |
| [WEBAPP_GETTING_STARTED_CHECKLIST](future_devs/archive/WEBAPP_GETTING_STARTED_CHECKLIST_SPEC.md) | Getting-started checklist on the digest | `wrapped` | S | WEBAPP_APP_SHELL_ACCOUNT ✅ |
| [WEBAPP_IN_APP_HELP_FAQ](future_devs/archive/WEBAPP_IN_APP_HELP_FAQ_SPEC.md) | In-app Help / FAQ page | `wrapped` | S | WEBAPP_GLOBAL_APP_SHELL_NAV ✅ |
| [WEBAPP_AUTH_RESET_CONFIRM_LEGAL](future_devs/archive/WEBAPP_AUTH_RESET_CONFIRM_LEGAL_SPEC.md) | Auth: forgot-password + email-confirm + terms/privacy | `wrapped` | M | WEBAPP_APP_SHELL_ACCOUNT ✅ |

### Standalone

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_COPY_POLISH](future_devs/WEBAPP_COPY_POLISH_SPEC.md) | Voice/clarity pass on onboarding + landing + help + profile.md notes (Fable) | `not-started` | S | — |
| [WEBAPP_INSTANT_LOAD_SWR](future_devs/WEBAPP_INSTANT_LOAD_SWR_SPEC.md) | Instant load — SWR localStorage cache on Digest + Positions + keep-warm ping to kill Render cold start | `completed` | S | — |
| [WEBAPP_FIRST_LOGIN_JOURNEY](future_devs/WEBAPP_FIRST_LOGIN_JOURNEY_SPEC.md) | First-login journey - redirect new users to a short welcome + resumable guided setup (profile, CV, API key, filters) | `not-started` | S | - |
| [WEBAPP_MULTI_PROFILE](future_devs/WEBAPP_MULTI_PROFILE_SPEC.md) | Multiple named profiles per user (own profile text, CV, filters, scores) with a profile switcher | `not-started` | L | WEBAPP_FIRST_LOGIN_JOURNEY |

> Bug: [BUG_LANDING_DEAD_GITHUB_LINKS](bugs_to_fix/BUG_LANDING_DEAD_GITHUB_LINKS.md) — dead `href="#"` GitHub links on landing (filed in `bugs_to_fix/`).

---

## Phase P8 — Position liveness

Track open/closed liveness on the scored digest so postings taken down get marked `closed` and surfaced distinctly instead of sitting as live links that 404. The `new`/`seen` states already exist (`scored_at` recency + `_load_seen_keys` skip); only `closed` is missing.

### Epic: Position liveness

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [POSITION_LIVENESS](future_devs/archive/POSITION_LIVENESS_SPEC.md) | Position liveness (epic root) | `wrapped` | M | — |
| [POSITION_LIVENESS_LIVE_SET](future_devs/archive/POSITION_LIVENESS_LIVE_SET_SPEC.md) | Persist live `apply_url` set from successful pulls | `wrapped` | S | POSITION_LIVENESS ✅ |
| [POSITION_LIVENESS_STATUS_DIFF](future_devs/archive/POSITION_LIVENESS_STATUS_DIFF_SPEC.md) | Diff scored jobs vs live set → `status` + `closed_at` | `wrapped` | S | POSITION_LIVENESS_LIVE_SET ✅ |
| [POSITION_LIVENESS_DIGEST_RENDER](future_devs/archive/POSITION_LIVENESS_DIGEST_RENDER_SPEC.md) | Render closed jobs distinctly in `digest.md` | `wrapped` | S | POSITION_LIVENESS_STATUS_DIFF ✅ |
| [POSITION_LIVENESS_WEBAPP](future_devs/archive/POSITION_LIVENESS_WEBAPP_SPEC.md) | Reflect `status` in webapp digest API + cards | `wrapped` | S | POSITION_LIVENESS_STATUS_DIFF ✅ |

---

---

## Phase P9 — ATS expansion II

New ATS pullers for high-value companies currently stuck in `ats: other` or `ats: unknown`. Ordered by company impact.

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [ATS_SMARTRECRUITERS](future_devs/archive/ATS_SMARTRECRUITERS_SPEC.md) | SmartRecruiters puller - CyberArk + Palo Alto Networks | `wrapped` | S | — |
| [ATS_BAMBOOHR](future_devs/archive/ATS_BAMBOOHR_SPEC.md) | BambooHR puller - Nilus + 4 others | `wrapped` | S | — |
| [ATS_CHECKPOINT_CAREERS](future_devs/ATS_CHECKPOINT_CAREERS_SPEC.md) | Check Point custom careers puller (single-tenant) - blocked by AWS WAF human-verification challenge | `not-started` | S | — |
| [ATS_TALEO](future_devs/archive/ATS_TALEO_SPEC.md) | Oracle Taleo puller - Radware | `wrapped` | M | — |
| [ATS_ORACLE_HCM](future_devs/archive/ATS_ORACLE_HCM_SPEC.md) | Oracle HCM puller - Dell Technologies Israel | `wrapped` | M | — |

---

## Phase P10 — Webapp visual design system

Appearance overhaul executed with the **Fable** design model. The app is functionally complete but visually unpolished: no design-token layer, abandoned shadcn/ui scaffold, inconsistent icons (inline SVGs + text glyphs + an emoji), default system font, minimal motion. This epic establishes a real design system and applies it. Presentation only — no behavior/data/routing changes; functional UX lives in P7.

### Epic: Webapp visual design system

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [WEBAPP_VISUAL_DESIGN](future_devs/archive/WEBAPP_VISUAL_DESIGN_SPEC.md) | Webapp visual design system (epic root) | `wrapped` | L | — |
| [WEBAPP_DESIGN_TOKENS](future_devs/archive/WEBAPP_DESIGN_TOKENS_SPEC.md) | Design tokens + theme + typography foundation | `wrapped` | S | — |
| [WEBAPP_DIGEST_VISUAL](future_devs/archive/WEBAPP_DIGEST_VISUAL_SPEC.md) | Digest visual redesign (cards, badges, legend, states) | `wrapped` | M | WEBAPP_DESIGN_TOKENS ✅ |
| [WEBAPP_LANDING_VISUAL](future_devs/archive/WEBAPP_LANDING_VISUAL_SPEC.md) | Landing visual glow-up + reuse real JobCard in preview | `wrapped` | M | WEBAPP_DESIGN_TOKENS ✅, WEBAPP_DIGEST_VISUAL ✅ |
| [WEBAPP_ICONOGRAPHY_MOTION](future_devs/archive/WEBAPP_ICONOGRAPHY_MOTION_SPEC.md) | Unify on lucide-react + consistent micro-interactions | `wrapped` | S | WEBAPP_DESIGN_TOKENS ✅ |
| [WEBAPP_ONBOARDING_VISUAL](future_devs/archive/WEBAPP_ONBOARDING_VISUAL_SPEC.md) | Onboarding wizard visual polish | `wrapped` | S | WEBAPP_DESIGN_TOKENS ✅ |

> All 5 children wrapped. Epic archived.

---

## Phase P11 — Pipeline reliability & hardening (Fable)

Cross-file correctness + resilience sweeps over the pipeline, sized for the
**Fable** model's edge in high-recall bug-finding and intermittent-failure
debugging. Give each the full file set up front; run at `high`/`xhigh` effort;
enable server-side `fallbacks` to `claude-opus-4-8` for cyber-content refusals.

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [PIPELINE_FAILURE_RESILIENCE](future_devs/PIPELINE_FAILURE_RESILIENCE_SPEC.md) | Diagnose + harden intermittent collect/score/refresh failures | `not-started` | M | — |

---

## Phase P12 — Webapp visual re-identity v2 (Fable)

All Phase P12 tasks are wrapped. See `ROADMAP_ARCHIVE.md`.

---

## Phase P13 — Scorer evaluation

The scorer is the one part of the pipeline nothing measures. Everything downstream —
digest ranking, the webapp, the RAG corpus — inherits its quality, and no change to the
prompt, rubric, or model can currently be shown to be an improvement rather than a
regression. Build the golden set and the two metrics before touching the scorer again.

| Slug | Title | Status | Effort | Depends on |
|---|---|---|---|---|
| [SCORER_EVAL_HARNESS](future_devs/SCORER_EVAL_HARNESS_SPEC.md) | Human-labelled golden set + band accuracy / hard-filter recall + CI gate on `gemini_scorer.py` | `not-started` | S | — |

---

## Spec Index

| Spec | Domain |
|---|---|
| `future_devs/archive/WEBAPP_SUPABASE_SETUP_GUIDE_SPEC.md` | P2 post-launch — Supabase setup guide (wrapped) |
| `future_devs/WEBAPP_PDF_CV_UPLOAD_SPEC.md` | P2 post-launch — PDF CV upload in onboarding |
| `future_devs/WEBAPP_OLD_PROFILE_BADGE_SPEC.md` | P2 post-launch — "Scored with old profile" badge |
| `future_devs/archive/PROPRIETARY_ATS_PULLERS_SPEC.md` | P3 — Big-corp ATS pullers epic (wrapped) |
| `future_devs/archive/ATS_TALENTBREW_SPEC.md` | P3 — TalentBrew puller (Intuit) (wrapped) |
| `future_devs/archive/ATS_AMAZON_JOBS_SPEC.md` | P3 — amazon.jobs puller (AWS) (wrapped) |
| `future_devs/archive/ATS_MICROSOFT_CAREERS_SPEC.md` | P3 — Microsoft careers puller (wrapped) |
| `future_devs/archive/ATS_GOOGLE_CAREERS_SPEC.md` | P3 — Google careers puller (wrapped) |
| `future_devs/archive/ATS_EIGHTFOLD_SPEC.md` | P3 — Eightfold puller (PayPal) (wrapped) |
| `future_devs/archive/ATS_JOBVITE_SPEC.md` | P3 — Jobvite puller (Varonis) (wrapped) |
| `future_devs/archive/ATS_SUCCESSFACTORS_SPEC.md` | P3 — SuccessFactors puller (SAP) (wrapped) |
| `future_devs/archive/ATS_TEAMME_SPEC.md` | P3 — TeamMe puller (Claroty, QM) (wrapped) |
| `future_devs/archive/ATS_BREEZY_SPEC.md` | P3 — Breezy HR puller (Descope) (wrapped) |
| `future_devs/SCORER_EVAL_HARNESS_SPEC.md` | P13 — Scorer eval harness (golden set + CI gate) |
| `future_devs/NEW_VC_ADAPTERS_SPEC.md` | P3 — Add VC adapters: State of Mind / Sequoia IL / Aleph / Lightspeed IL / Greylock / Insight IL |
| `future_devs/archive/TLV_PORTFOLIO_FIX_SPEC.md` | P3 — Fix TLV Partners scraper + clean stale entries (wrapped) |
| `future_devs/archive/BIG_COMPANIES_ATS_PARAMS_SPEC.md` | P3 — Fill ATS params for ~30 unfilled big_companies.yml stubs (wrapped) |
| `future_devs/PIPELINE_TEST_COVERAGE_SPEC.md` | P3 — Pipeline test suite |
| `future_devs/archive/VIOLA_GETRO_DEDUP_SPEC.md` | P1 — Deduplicate Viola Getro jobs before scoring (wrapped) |
| `future_devs/archive/RESCORE_EXISTING_SPEC.md` | P1 — Re-score stored jobs with updated profile (wrapped) |
| `future_devs/archive/GITHUB_ACTIONS_SCHEDULE_SPEC.md` | P1 — Automate collect + refresh with GitHub Actions (wrapped) |
| `future_devs/archive/WEBAPP_SCAFFOLD_SPEC.md` | P2 — Project scaffold + Supabase schema (wrapped) |
| `future_devs/archive/WEBAPP_AUTH_SPEC.md` | P2 — Auth: email + Google OAuth (wrapped) |
| `future_devs/archive/WEBAPP_SCORING_ENDPOINT_SPEC.md` | P2 — Scoring API endpoint per user (wrapped) |
| `future_devs/archive/WEBAPP_LANDING_SPEC.md` | P2 — Landing page (wrapped) |
| `future_devs/archive/WEBAPP_ACTIONS_WIRING_SPEC.md` | P2 — GitHub Actions cron wiring (wrapped) |
| `future_devs/archive/WEBAPP_DEPLOY_SPEC.md` | P2 — Render.com deployment (wrapped) |
| `future_devs/archive/WEBAPP_ONBOARDING_SPEC.md` | P2 — Onboarding flow (4 steps) (wrapped) |
| `future_devs/archive/WEBAPP_DIGEST_SPEC.md` | P2 — Digest view with score cards (wrapped) |
| `future_devs/archive/WEBAPP_SETTINGS_SPEC.md` | P2 — Settings tabs (wrapped) |
| `future_devs/archive/DS_ANALYSIS_NOTEBOOK_SPEC.md` | P4 — DS analysis notebook (wrapped) |
| `future_devs/archive/REPO_SHOWCASE_SPEC.md` | P4 — README rewrite / engineering showcase (wrapped) |
| `future_devs/archive/SCORING_RUBRIC_ABLATION_SPEC.md` | P4 — Scoring calibration doc (wrapped) |
| `future_devs/archive/WEBAPP_FAVICON_SPEC.md` | P5 — Website favicon + Open Graph (wrapped) |
| `future_devs/archive/WEBAPP_CV_SETTINGS_UPLOAD_SPEC.md` | P5 — CV re-upload in Settings (wrapped) |
| `future_devs/archive/WEBAPP_CV_UPLOAD_FORMATS_SPEC.md` | P5 — CV upload: DOCX + TXT support alongside PDF (wrapped) |
| `future_devs/archive/WEBAPP_UNIFIED_UPLOAD_FORMATS_SPEC.md` | P5 — Full format set for both CV + profile uploads; centralized allowed-types (wrapped) |
| `future_devs/archive/WEBAPP_SETTINGS_STATE_VISIBILITY_SPEC.md` | P5 — Settings reflects current state (CV, filters, API-key status, account identity) (wrapped) |
| `future_devs/archive/WEBAPP_PROFILE_UPLOAD_OR_PROMPT_SPEC.md` | P5 — Profile upload or AI prompt generator (wrapped) |
| `future_devs/archive/WEBAPP_COMPANIES_VIEW_SPEC.md` | P5 — Companies page (wrapped) |
| `future_devs/archive/WEBAPP_COUNTUP_ANIMATION_SPEC.md` | P5 — Count-up animation on Companies + Positions page load (wrapped) |
| `future_devs/archive/WEBAPP_POSITIONS_VIEW_SPEC.md` | P5 — Positions page (wrapped) |
| `future_devs/archive/WEBAPP_POSITIONS_TOTAL_COUNT_SPEC.md` | P5 — Digest toolbar: "n suitable roles out of N collected" (retargeted from Positions) (wrapped) |
| `future_devs/archive/WEBAPP_POSITIONS_DETAIL_VIEW_SPEC.md` | P5 — Positions page: in-app detail view on row click + link out to posting (wrapped) |
| `future_devs/archive/WEBAPP_MULTI_FILTER_SPEC.md` | P5 — Multi-value filters with ';' (wrapped) |
| `future_devs/archive/PROFILE_CV_GAP_ANALYSIS_SPEC.md` | P5 — Gap analysis: profile vs CV, positions vs CV (wrapped) |
| `future_devs/archive/POSITION_FIRST_SEEN_SPEC.md` | P5 — Stamp first_seen date on each position; show in digest + webapp (wrapped) |
| `future_devs/RAG_CHATBOT_SPEC.md` | P6 — RAG sandbox + chat epic (root + shared brief) |
| `future_devs/archive/RAG_CORE_SPEC.md` | P6 — RAG child 1: `rag/` retrieval core (ingest/query/refresh) (wrapped) |
| `future_devs/RAG_EMBEDDINGS_BACKFILL_SPEC.md` | P6 — RAG follow-up: finish full embedding ingest + golden set |
| `future_devs/RAG_CHAT_API_SPEC.md` | P6 — RAG child 2: `/api/chat` router |
| `future_devs/RAG_CHAT_UI_SPEC.md` | P6 — RAG child 3: `/chat` frontend page |
| `future_devs/MULTI_AGENT_RESUME_TAILOR_SPEC.md` | P6 — Multi-agent CV tailor |
| `future_devs/archive/MARKITDOWN_PDF_INGEST_SPEC.md` | P6 — MarkItDown doc→Markdown for CV upload + future RAG doc ingest (wrapped) |
| `future_devs/WEBAPP_FIRST_RUN_COMPREHENSION_SPEC.md` | P7 — First-run comprehension (epic root) |
| `future_devs/WEBAPP_LANDING_REVAMP_SPEC.md` | P7 — Landing revamp (value prop, BYO-key, digest preview, FAQ) |
| `future_devs/WEBAPP_ONBOARDING_ORIENTATION_SPEC.md` | P7 — Onboarding orientation + setup summary |
| `future_devs/WEBAPP_PROFILE_EXAMPLE_GUIDANCE_SPEC.md` | P7 — Profile example + section guidance |
| `future_devs/WEBAPP_FILTER_PLAIN_LANGUAGE_PREVIEW_SPEC.md` | P7 — Plain-language filters + live preview |
| `future_devs/WEBAPP_ONBOARDING_KEY_TEST_SPEC.md` | P7 — Inline key test in onboarding |
| `future_devs/archive/WEBAPP_DIGEST_TRUST_SPEC.md` | P7 — Digest legibility & trust (epic root, wrapped) |
| `future_devs/archive/WEBAPP_SCORE_LEGEND_SPEC.md` | P7 — Score legend & tier explainer (wrapped) |
| `future_devs/archive/WEBAPP_FLAG_GLOSSARY_SPEC.md` | P7 — Flag glossary & friendly labels (wrapped) |
| `future_devs/archive/WEBAPP_CADENCE_RUN_LIMIT_EXPLAINER_SPEC.md` | P7 — Cadence & run-limit explainer (wrapped) |
| `future_devs/archive/WEBAPP_DIAGNOSTIC_STATES_SPEC.md` | P7 — Diagnostic empty & progress states (wrapped) |
| `future_devs/WEBAPP_JOBSEEKER_WORKFLOW_SPEC.md` | P7 — Job-seeker workspace (epic root) |
| `future_devs/archive/WEBAPP_JOB_DETAIL_VIEW_SPEC.md` | P7 — In-app job detail view (wrapped) |
| `future_devs/WEBAPP_APPLICATION_TRACKER_SPEC.md` | P7 — Application status tracker |
| `future_devs/WEBAPP_POSITIONS_MARK_APPLIED_SPEC.md` | P7 — Mark-applied on Positions shared catalog (per-user overlay) |
| `future_devs/WEBAPP_POSITIONS_DETAIL_DESCRIPTION_SPEC.md` | P5 — Positions detail: show real job description from shared catalog |
| `future_devs/WEBAPP_HIDE_DISMISS_JOBS_SPEC.md` | P7 — Hide / dismiss jobs |
| `future_devs/WEBAPP_NEW_SINCE_LAST_VISIT_SPEC.md` | P7 — New-since-last-visit badges |
| `future_devs/WEBAPP_DIGEST_SORT_PERSIST_SPEC.md` | P7 — Digest sort + persist view |
| `future_devs/archive/WEBAPP_APP_SHELL_ACCOUNT_SPEC.md` | P7 — App shell + account UX (epic root, wrapped) |
| `future_devs/archive/WEBAPP_GLOBAL_APP_SHELL_NAV_SPEC.md` | P7 — Global app shell + nav + sign-out (wrapped) |
| `future_devs/archive/WEBAPP_GETTING_STARTED_CHECKLIST_SPEC.md` | P7 — Getting-started checklist (wrapped) |
| `future_devs/archive/WEBAPP_IN_APP_HELP_FAQ_SPEC.md` | P7 — In-app Help / FAQ page (wrapped) |
| `future_devs/archive/WEBAPP_AUTH_RESET_CONFIRM_LEGAL_SPEC.md` | P7 — Auth reset / confirm / legal (wrapped) |
| `future_devs/archive/WEBAPP_ACCESSIBILITY_PASS_SPEC.md` | P7 — Accessibility pass (wrapped) |
| `future_devs/WEBAPP_COPY_POLISH_SPEC.md` | P7 — Voice/clarity copy pass (onboarding, landing, help, profile.md) (Fable) |
| `future_devs/WEBAPP_INSTANT_LOAD_SWR_SPEC.md` | P7 — Instant load: SWR localStorage cache (Digest + Positions) + keep-warm ping vs Render cold start |
| `future_devs/WEBAPP_FIRST_LOGIN_JOURNEY_SPEC.md` | P7 - First-login journey: redirect to welcome + resumable guided setup |
| `future_devs/WEBAPP_MULTI_PROFILE_SPEC.md` | P7 - Multiple named profiles per user (profile/CV/filters/scores per profile) |
| `future_devs/archive/POSITION_LIVENESS_SPEC.md` | P8 — Position liveness (epic root, wrapped) |
| `future_devs/archive/POSITION_LIVENESS_LIVE_SET_SPEC.md` | P8 — Persist live apply_url set from successful pulls (wrapped) |
| `future_devs/archive/POSITION_LIVENESS_STATUS_DIFF_SPEC.md` | P8 — Status diff: scored jobs vs live set (wrapped) |
| `future_devs/archive/POSITION_LIVENESS_DIGEST_RENDER_SPEC.md` | P8 — Render closed jobs in digest.md (wrapped) |
| `future_devs/archive/POSITION_LIVENESS_WEBAPP_SPEC.md` | P8 — Reflect status in webapp digest (wrapped) |
| `future_devs/archive/ATS_SMARTRECRUITERS_SPEC.md` | P9 — SmartRecruiters puller (CyberArk + PAN) (wrapped; see BUG_SMARTRECRUITERS_ROUTING for live regression) |
| `future_devs/archive/ATS_BAMBOOHR_SPEC.md` | P9 — BambooHR puller (Nilus + 4 others) (wrapped) |
| `future_devs/ATS_CHECKPOINT_CAREERS_SPEC.md` | P9 — Check Point custom careers (single-tenant) |
| `future_devs/archive/ATS_TALEO_SPEC.md` | P9 — Oracle Taleo puller (Radware) (wrapped) |
| `future_devs/archive/ATS_ORACLE_HCM_SPEC.md` | P9 — Oracle HCM puller (Dell Technologies Israel) (wrapped) |
| `future_devs/archive/WEBAPP_VISUAL_DESIGN_SPEC.md` | P10 — Webapp visual design system (epic root, wrapped) |
| `future_devs/archive/WEBAPP_DESIGN_TOKENS_SPEC.md` | P10 — Design tokens + theme + typography foundation (wrapped) |
| `future_devs/archive/WEBAPP_DIGEST_VISUAL_SPEC.md` | P10 — Digest visual redesign (wrapped) |
| `future_devs/archive/WEBAPP_LANDING_VISUAL_SPEC.md` | P10 — Landing visual glow-up + reuse real JobCard (wrapped) |
| `future_devs/archive/WEBAPP_ICONOGRAPHY_MOTION_SPEC.md` | P10 — Unify on lucide-react + micro-interactions (wrapped) |
| `future_devs/archive/WEBAPP_ONBOARDING_VISUAL_SPEC.md` | P10 — Onboarding wizard visual polish (wrapped) |
| `future_devs/archive/ATS_PULLER_HARDENING_AUDIT_SPEC.md` | P11 — Repo-wide ATS puller correctness + resilience audit (Fable, wrapped) |
| `future_devs/PIPELINE_FAILURE_RESILIENCE_SPEC.md` | P11 — Diagnose + harden intermittent pipeline failures (Fable) |
| `future_devs/archive/WEBAPP_VISUAL_REDESIGN_V2_SPEC.md` | P12 — Bold visual re-identity + light/dark theme toggle (Fable, wrapped) |
