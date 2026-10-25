| Field | Value |
|---|---|
| **Phase** | P10 |
| **Status** | `wrapped` |
| **Effort** | L |
| **Epic** | — (epic root) |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/**`, `webapp/frontend/tailwind.config.ts`, `webapp/frontend/app/globals.css` |

## Overview

Visual/appearance overhaul of the CareerWatch webapp, executed with the **Fable** design model. The app is functionally complete but visually unpolished: there is no design-token layer (every color/spacing is a raw Tailwind literal repeated across ~10 files), the shadcn/ui foundation was scaffolded but abandoned (`components/ui/` empty), icons are an inconsistent mix of inline SVGs / text glyphs (`▸ ▾ ✓ ✗`) / an emoji, the app uses the default system font, and motion is limited to spinner/pulse.

This epic establishes a real design system and applies it across the highest-visibility surfaces. It is **presentation only** — no behavior, data, or routing changes. Functional UX work lives in the P7 epics; this epic is purely aesthetic.

## Why

The webapp is Yotam's portfolio-grade public product (BYO-key job matcher). Current appearance reads as an unstyled internal tool. A cohesive visual identity raises perceived quality for both job-seeker users and as a portfolio showcase.

## Children (execution order)

The token foundation **must** land first — every downstream task depends on it, otherwise Fable bakes in one-off literals and the app drifts.

1. **WEBAPP_DESIGN_TOKENS** (S) — design-token + theme + typography foundation. **Blocks all others.**
2. **WEBAPP_DIGEST_VISUAL** (M) — redesign the main digest (job cards, score badges, legend, empty/loading states).
3. **WEBAPP_LANDING_VISUAL** (M) — landing-page visual glow-up; de-duplicate the mock preview card against the real `JobCard`.
4. **WEBAPP_ICONOGRAPHY_MOTION** (S) — unify on `lucide-react`; add consistent micro-interactions + skeletons.
5. **WEBAPP_ONBOARDING_VISUAL** (S) — polish the 4-step onboarding wizard (progress, transitions, styled form controls).

## Constraints

- Keep the intentional dark theme; make it deliberate rather than removing it.
- No new heavy dependencies. `lucide-react`, `clsx`, `tailwind-merge`, `class-variance-authority` are already installed — use them. `next/font` is built in.
- No copy/behavior changes that belong to P7 UX specs.
- Hyphens, not em-dashes, in any user-facing text (Yotam's preference).

## How to QA

1. Run `WEBAPP_DESIGN_TOKENS` first and confirm the token layer exists before starting any child.
2. Each child ships and QAs independently per its own spec.
3. After all children: `cd webapp/frontend && npm run build` succeeds with no type errors; the app renders in a browser with a consistent look across landing, onboarding, digest, positions, companies, gaps, settings.
4. Visual regression check: no page falls back to unstyled/default-browser controls.
