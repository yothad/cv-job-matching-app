| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `completed` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | WEBAPP_FIRST_LOGIN_JOURNEY (both edit onboarding copy - polish the new flow, not the old one) |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/onboarding/page.tsx`, `webapp/frontend/app/landing/page.tsx`, `webapp/frontend/app/(app)/help/page.tsx`, `webapp/frontend/app/components/*` (NOT `profile.md` - it is Omer's personal scoring rubric; rubric changes are eval-gated per CLAUDE.md) |
| **Night-ready** | 🌙 yes - Omer reviews the new wording in the morning |
| **Model** | Fable (`claude-fable-5`) |

## Overview

Prose-quality pass over the app's human-facing copy: onboarding wizard, landing
page (hero, "how it works", BYO-key explainer, FAQ), in-app Help, and the
`profile.md` "notes for the matcher" guidance. The features already exist and
work — this is a *voice and clarity* pass, not new functionality.

**Why Fable:** clearer, warmer, less-hedged prose at higher effort is Fable's
documented edge. Copy quality is the deliverable here, so the model choice is the
point. Softer advantage than the pipeline tasks — worth it because the whole task
is writing.

Hyphens, not em-dashes, in all output (Omer's standing preference — see CLAUDE.md).

## Behaviour

1. **Onboarding** (`onboarding/page.tsx`) — tighten step explanations, the
   profile-generation questionnaire copy, the CV/Gemini-key step guidance, and
   filter-field labels/tooltips/placeholders. First-timer should understand *why*
   each step matters, not just *what* to type.
2. **Landing** (`landing/page.tsx`) — sharpen hero value prop, the 3-step "how it
   works", the "bring your own free AI key" section, and the `FAQ_ITEMS` array
   (update frequency, tracked companies, cost, privacy, audience fit).
3. **Help** (`(app)/help/page.tsx`) — align tone with landing; no contradictions.
4. **`profile.md`** — refine the "notes for the matcher" prose for precision (this
   is injected verbatim into the scorer, so clarity here changes match quality).
5. **No behaviour, data, or routing changes** — copy and static strings only.
   Preserve all `href`s, keys, and component props.

## Files to Touch

- `webapp/frontend/app/onboarding/page.tsx`
- `webapp/frontend/app/landing/page.tsx`
- `webapp/frontend/app/(app)/help/page.tsx`
- `webapp/frontend/app/components/*` (checklist / nav / card microcopy only)
- `profile.md` (matcher-notes prose)

## How to QA

1. Frontend builds and renders (dev server) with no console errors.
2. Onboarding, landing, and help pages read cleanly end-to-end in a browser;
   no truncated/overflowing strings; no em-dashes.
3. `uv run python score.py --dry-run` runs clean after any `profile.md` edit
   (rubric/notes still parse and inject correctly).
4. Diff shows copy-only changes — no JSX structure, prop, route, or data edits.

## Night run 2026-10-12
Shipped unattended on the second attempt (dev on Fable). The first review found false claims: "key/CV used only for scoring" (the Gaps page also sends them) and an industries tooltip describing "tagging"; both fixed. Gate green; review pass. `profile.md` not edited (eval-gated).
Morning QA (browser): read onboarding, landing and help end to end at mobile width and in both themes; filter-step tooltips and preview line; profile-skip warning.
Needs Omer: `privacy/page.tsx` + `terms/page.tsx` still say the key is used "only to score"; help says "jobs below 5 never reach your digest" (min score is user-adjustable) and "export all your data" (`/user/export` only exports scored_jobs).
