| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `in-progress` |
| **Effort** | S |
| **Epic** | - |
| **Depends on** | - (supersedes nothing; builds on wrapped WEBAPP_FIRST_RUN_COMPREHENSION and WEBAPP_GETTING_STARTED_CHECKLIST) |
| **Blocks** | WEBAPP_MULTI_PROFILE (the journey's Profile/CV steps become "create your first profile") |
| **Touches** | webapp/frontend/app/auth/callback/route.ts, webapp/frontend/middleware.ts, webapp/frontend/app/onboarding/page.tsx, webapp/frontend/app/(app)/digest/page.tsx, webapp/backend/routers/user.py |
| **Night-ready** | 🌙 yes |

## Overview

The onboarding wizard (Profile / CV / API key / Filters, with orientation copy) already exists, but a new user never reaches it: `auth/callback/route.ts` redirects every login to `/digest`, and nothing sends an incomplete account to `/onboarding`. A first-time user lands on an empty Digest with a small checklist and has to discover the setup flow on their own.

Goal: the first time someone connects, they get a short explanation of what the app does and are walked through everything it needs (profile, CV, Gemini API key, optional filters), one step at a time, and can leave and resume without losing progress.

## Behaviour

- **Setup state** comes from `GET /user/me`: add a derived `setup` object `{ profile, cv, api_key, filters_seen, complete }` so the frontend does not re-derive it from raw fields. `complete` = profile AND api_key present (CV and filters are recommended, not required; the wizard says so).
- **First login redirect:** after auth, if `setup.complete` is false, send the user to `/onboarding` instead of `/digest`. Returning users with a complete setup go to `/digest` as today.
- **Short welcome (step 0):** 3 bullets max - what CareerWatch does (tracks 100+ Israeli cyber/fraud/fintech companies, scores roles against YOUR profile), why it needs a profile + CV + free Gemini key, and roughly how long setup takes. One "Get started" button. Shown once per browser (flag in localStorage, wrapped in try/catch), and never again once `setup.complete` is true - no schema change.
- **Guided journey:** reuse the existing 4-step wizard, but start at the first INCOMPLETE step (resume), show progress ("2 of 4 done"), and let the user skip optional steps. Each step keeps its existing why-it-matters caption.
- **Leaving and returning:** each step saves on "Next" (not only at the end), so closing the tab mid-way loses nothing. Opening `/onboarding` again resumes; the Digest "Getting started" checklist links straight to the first incomplete step.
- **Finish:** setup summary, then "Start my first scan". A completed user visiting `/onboarding` sees a "You're all set" state with links to Settings, not the wizard.
- **Never block the app:** a user may dismiss onboarding and browse Digest/Positions/Companies; the checklist stays until setup is complete.
- Hyphens, not em-dashes, in all UI copy.

## Files to Touch

- `webapp/frontend/app/auth/callback/route.ts` - redirect target by setup state
- `webapp/frontend/middleware.ts` - optional: guard so `/digest` for a brand-new user nudges to `/onboarding` (decide in implementation; the callback redirect alone covers the first login)
- `webapp/frontend/app/onboarding/page.tsx` - welcome step, resume at first incomplete step, per-step save, complete state
- `webapp/frontend/app/(app)/digest/page.tsx` - checklist deep-links to the first incomplete step
- `webapp/backend/routers/user.py` - derived `setup` object in `/user/me` (no new columns)
- Specs to update: `WEBAPP_SPEC.md`, `future_devs/archive/WEBAPP_ONBOARDING_SPEC.md` (note the resume behaviour)

## How to QA

1. Sign up with a brand-new email: after auth you land on `/onboarding` showing the 3-bullet welcome, not on `/digest`.
2. Complete only the Profile step, close the tab, sign back in: you land on the API key (or CV) step, Profile shows as done, nothing was lost.
3. Complete all required steps: the summary appears, "Start my first scan" works, and the next login goes to `/digest`.
4. Dismiss onboarding midway and open `/digest`: the app works and the checklist links to the first incomplete step.
5. `npm run build` passes; `GET /user/me` returns the `setup` object and no secrets.
