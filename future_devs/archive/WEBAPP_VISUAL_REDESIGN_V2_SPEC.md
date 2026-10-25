| Field | Value |
|---|---|
| **Phase** | P12 |
| **Status** | `wrapped` |
| **Effort** | L |
| **Epic** | — (standalone; supersedes the wrapped P10 look) |
| **Depends on** | P10 visual design system (`archive/WEBAPP_VISUAL_DESIGN_SPEC.md`) ✅ |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/globals.css`, `webapp/frontend/tailwind.config.ts`, `webapp/frontend/app/layout.tsx`, `webapp/frontend/app/landing/page.tsx`, `webapp/frontend/app/auth/page.tsx`, `webapp/frontend/app/onboarding/page.tsx`, `webapp/frontend/app/(app)/layout.tsx`, `webapp/frontend/app/components/*`, `webapp/frontend/app/(app)/**/page.tsx`, `webapp/frontend/lib/scoreBands.ts`, `webapp/frontend/app/{privacy,terms}/page.tsx` |
| **Model** | Fable (`claude-fable-5`) |

## Overview

A bold visual **re-identity** of the CareerWatch web app, plus a **light/dark
theme toggle**. This is a v2 pass: P10 already gave the app a real Fable design
system (design tokens, redesigned digest/landing/onboarding, lucide-react icons,
tasteful motion). The current look is a competent dark-navy + green-accent SaaS
theme. Yotam's ask is to make it feel **much more modern and distinctive** - so
this task is deliberately *not* a refinement of the existing palette. It is a new
visual identity applied consistently across every page, with dark and light modes.

**Two direction decisions already made by Yotam (do not re-litigate):**
1. **Bold aesthetic pivot** - a fresh identity, not an evolution of green-on-navy.
   Fresh palette, expressive display typography for headings, a signature hero
   treatment, more depth/texture, modern layout patterns (bento, glass/depth
   accents where they earn their place).
2. **Light + dark modes** with a user-facing toggle (defaulting to system
   preference on first load).

**Why Fable:** this is a pure design-quality deliverable - identity, palette,
type, motion, and taste are the whole point, and distinctive non-generic visual
work at high effort is Fable's documented edge. The technical surface is small and
well-fenced; the value is entirely in the aesthetic judgment.

Hyphens, not em-dashes, in all user-facing output (Yotam's standing preference -
see CLAUDE.md).

## Design direction (a brief, not a pixel spec)

Fable owns the concrete aesthetic. This section sets intent and guardrails; make
the identity choices yourself and commit to them coherently across the app.

- **New palette.** Move off green-on-navy. Pick a distinctive, confident accent
  and a cohesive neutral ramp that reads as intentional and current, not a
  Tailwind default. It must work in **both** light and dark. Job scoring is the
  product's soul - the palette should feel sharp and trustworthy, not playful.
- **Typography with a point of view.** Introduce a display/heading face
  (via `next/font/google`, self-hosted - no external CDN fonts) paired with a
  clean body face (Inter is fine to keep for body). Establish a real type scale
  and use it consistently. Headings should have character; body should be
  quiet and legible.
- **Signature hero.** The landing hero is the single highest-leverage surface.
  Give it a memorable treatment (animated gradient mesh, subtle grain, layered
  depth, or similar) that still respects `prefers-reduced-motion` and does not
  hurt LCP or accessibility. This is where "wow" is allowed to live.
- **Depth and texture, tastefully.** Modern shadow/border/radius language, glass
  or layered surfaces where they add clarity - never decoration for its own sake.
- **Motion.** Keep it purposeful and fast. Preserve every existing
  `prefers-reduced-motion` guard and add none that can't be disabled.
- **Cohesion over novelty per page.** One identity, applied everywhere. A user
  moving landing -> auth -> onboarding -> digest should feel one product.

## Theme system (light + dark)

This is the one genuinely load-bearing piece of engineering in the task. Get it
right:

1. **Token-driven.** All colors flow through the CSS-variable token layer in
   `globals.css` (already the pattern) mapped in `tailwind.config.ts`. Define a
   full light ramp and a full dark ramp; components read tokens, never hardcoded
   hex. Audit for and remove hardcoded Tailwind color classes introduced in P10
   (e.g. `text-gray-300`, `bg-gray-700`, `text-green-500`, `from-white to-gray-400`)
   - these break in light mode. Replace with tokens.
2. **Toggle UI.** A clear, discoverable theme toggle (sun/moon lucide icon) in the
   app `Nav` and on the public pages' header/footer. Three-state (system / light /
   dark) is nice-to-have; light/dark with a system default is the floor.
3. **Persistence + no flash.** Persist choice (localStorage) and apply the theme
   class on `<html>` **before first paint** via a tiny inline script in
   `layout.tsx` (blocking, in `<head>`), so there is no flash of the wrong theme
   and no hydration mismatch. `color-scheme` must track the active theme (today
   it is hardcoded `dark` in `globals.css` - make it dynamic).
4. **Both themes are first-class.** Every page, every state (hover, focus,
   disabled, empty, skeleton, error) must be checked in both. Light mode is not an
   afterthought inversion; contrast and hierarchy must hold in both.

## Scope by surface

Presentation only. Redesign the appearance of all of the following; do not change
what any of them *do*.

- **Root** `app/layout.tsx`, `app/globals.css`, `tailwind.config.ts` - fonts,
  token layer (light+dark), theme bootstrap script.
- **Landing** `app/landing/page.tsx` - hero, "how it works" 3-step, "bring your
  own key" panel, digest preview, "who it's for", FAQ accordion, footer.
- **Auth** `app/auth/page.tsx` and `app/auth/reset/page.tsx`.
- **Onboarding** `app/onboarding/page.tsx` - wizard chrome, step indicator,
  form controls, transitions.
- **App shell** `app/(app)/layout.tsx` + `app/components/Nav.tsx` - navigation,
  theme toggle, active states.
- **Components** `app/components/JobCard.tsx`, `GettingStartedChecklist.tsx` -
  the JobCard is shared by the digest and the landing preview, so its redesign
  propagates to both (a feature, not a risk - keep it that way).
- **App pages** `app/(app)/{digest,positions,companies,gaps,settings,help}/page.tsx`
  - cards, tables, tabs, badges, empty/loading/error states.
- **Legal** `app/{privacy,terms}/page.tsx` - inherit the new type/color system.
- **Score bands** `lib/scoreBands.ts` - the three tier colors
  (`bg-score-high/mid/low`) are semantic and legally must stay mutually
  distinguishable in **both** themes and remain legible behind white badge text.
  Retune the underlying `--color-score-*` tokens per theme if the new palette
  demands it; keep the SCORE_BANDS structure and copy intact.

## Non-negotiable guardrails

- **Presentation only. No behavior, data, routing, prop-contract, or copy
  changes.** Preserve every `href`, route, component prop, state key, and string.
  (Copy is a separate task - `WEBAPP_COPY_POLISH_SPEC.md`.) If a redesign tempts a
  copy tweak, leave the copy and note it.
- **SSR determinism for the landing preview.** `landing/page.tsx` renders the real
  `JobCard` with a fixed far-future `scored_at` (`2099-01-01`) specifically so
  `timeAgo()` renders identically on server and client. Do not introduce any
  non-deterministic render (dates, `Math.random`, unguarded `window`) that
  reintroduces a hydration mismatch. The theme bootstrap is the one sanctioned
  pre-paint script and must itself be hydration-safe.
- **Accessibility holds or improves.** WCAG AA contrast in both themes; visible
  focus rings; every new icon-only control (esp. the theme toggle) has an
  `aria-label`. Do not regress the existing reduced-motion handling. (A dedicated
  a11y pass exists at `WEBAPP_ACCESSIBILITY_PASS_SPEC.md`; do not make its job
  harder.)
- **No new heavy dependencies.** Fonts via `next/font` (self-hosted). Icons stay
  on `lucide-react` (established in P10 - do not reintroduce inline SVGs, text
  glyphs, or emoji). Any dependency beyond that: ask first (CLAUDE.md rule).
- **No external network assets.** No CDN fonts, remote images, or external CSS -
  everything self-hosted/inlined, consistent with the rest of the app.
- **Performance.** The hero treatment must not tank LCP or jank scrolling. Prefer
  CSS/transform-based effects over large images or heavy JS animation loops.

## Suggested phasing (for `/start_task`)

The exit gate must pass at each phase boundary; `/start_task` stops at `completed`.

- **Phase A - Foundation.** Palette + type + token layer (light+dark) in
  `globals.css`/`tailwind.config.ts`/`layout.tsx`; theme toggle + no-flash
  bootstrap; retune `--color-score-*`. Deliverable: theme switches cleanly app-wide
  with the old layouts still intact (colors/fonts change, structure not yet).
- **Phase B - Public surfaces.** Landing (incl. signature hero) + auth +
  onboarding + legal pages redesigned in both themes.
- **Phase C - App surfaces.** App shell/Nav, JobCard, checklist, and all
  `(app)/*` pages redesigned in both themes; verify the landing preview still
  matches the real digest card.
- **Phase D - Polish + QA.** Cross-page cohesion sweep, both-theme state audit
  (hover/focus/empty/skeleton/error), reduced-motion check, contrast check.

## How to QA

1. `npm run build` (or the project's frontend build) completes with no type or
   lint errors; dev server renders every route with **zero console errors** and
   **no hydration warnings** (watch the landing preview specifically).
2. Toggle light <-> dark on every page: no flash on hard reload, choice persists
   across reloads, `color-scheme` tracks the active theme, and every page/state
   reads correctly in both.
3. Landing, auth, onboarding, digest, positions, companies, gaps, settings, help,
   privacy, terms - each looks cohesive, modern, and on-identity in both themes;
   no orphaned P10 green/navy, no hardcoded gray/green Tailwind classes surviving.
4. Score badges (9-10 / 7-8 / 5-6) remain visually distinct and legible in both
   themes; digest legend, popover, and help explainer still agree (all derive from
   `SCORE_BANDS`).
5. `prefers-reduced-motion: reduce` disables the hero animation and all reveals;
   keyboard focus is visible everywhere; icon-only controls have `aria-label`s.
6. Diff review confirms **presentation-only**: no route, prop, data-fetch, state,
   or copy changes. Backend, API, and Python are untouched.

## Out of scope

- Any copy/voice changes (owned by `WEBAPP_COPY_POLISH_SPEC.md`).
- Any functional UX / new features / new pages (owned by P7 specs).
- Backend, scoring, ATS, or pipeline changes.
- New illustration/photography commissions or a full brand/logo system beyond what
  the in-app identity needs.
- Mobile-native app.
