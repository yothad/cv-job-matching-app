# Spec: webapp_landing

**Slug:** webapp_landing  
**Epic:** Web App v1  
**Effort:** S  
**Depends on:** webapp_scaffold ✅

---

## Goal

Build the public landing page at `/landing`. The root `/` redirects authenticated users to `/digest` and unauthenticated users to `/auth` (handled by `webapp_auth`); `/landing` is a standalone marketing page reachable from the auth page.

---

## Page: `webapp/frontend/app/landing/page.tsx`

Static server component (no `'use client'`).

### Sections (top to bottom)

**1. Hero**
```
CareerWatch

Find the right job without the noise.
AI-powered job matching for tech professionals in Israel.

[Get started free →]   [View on GitHub →]
```
- "Get started free" links to `/auth`
- "View on GitHub" links to `https://github.com/yothad/cv-job-matching-app` (use a placeholder `#` if unsure of exact URL - do not guess)
- Use large heading (`text-4xl font-bold`) + subheading + two CTA buttons

**2. How it works** (3 steps, horizontal on desktop / vertical on mobile)

```
1. Set up your profile
   Describe your background, target roles, and deal-breakers with AI assistance.

2. We scrape the market
   CareerWatch pulls open positions from 100+ Israeli cyber and fintech companies daily.

3. You get a ranked digest
   Every job scored 0-10 against your profile. You only read what matters.
```

**3. Trust line**

```
Built with your own AI key — your data never trains a model.
```
Centered, muted text.

**4. Footer**

```
CareerWatch · Built by Yotam Hadar · GitHub
```
- "GitHub" links to `#` placeholder

---

## Styling constraints

- Tailwind only — no external UI library needed for this page
- Dark background (`bg-gray-950` or `bg-slate-900`) with light text
- Green accent for the primary CTA (`bg-green-600 hover:bg-green-700`)
- The 3-step section: use a simple flex/grid layout with numbered circles
- Keep the component under 120 lines

---

## Touches

- `webapp/frontend/app/landing/page.tsx` (new)

---

## Exit gate

```bash
# File exists and has a default export
ls C:/repos/cv-job-matching-app/webapp/frontend/app/landing/page.tsx
grep "export default" C:/repos/cv-job-matching-app/webapp/frontend/app/landing/page.tsx

# Python pipeline unaffected
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
