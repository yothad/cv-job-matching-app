# WEBAPP_INSTANT_LOAD_SWR

| Field | Value |
|---|---|
| **Phase** | P7 (Standalone) |
| **Status** | `not-started` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/(app)/digest/page.tsx`, `webapp/frontend/app/(app)/positions/page.tsx`, `webapp/frontend/lib/swrCache.ts` (new), `.github/workflows/keep-warm.yml` (new) |
| **Night-ready** | 🌙 yes |
| **Spec files to update** | `WEBAPP_SPEC.md` |

## Overview

**Problem:** Opening the webapp shows nothing but a skeleton for a long time before any real data appears. The experience reads as broken. Two independent causes:

1. **Render backend cold start (dominant).** The API is a separate Render service. On the free/hobby tier it spins down after ~15 min idle and takes 30-60s to wake on the next request. The first visit of a session waits on that wake-up behind a spinning skeleton. No client-side trick hides this - only a warm backend does.
2. **No cross-visit cache + serial fetches.** Every page mount refetches from zero. `/digest` fires three endpoints (`/jobs`, `/user/me`, `/jobs/stats`), each independently calling `supabase.auth.getSession()` first. Nothing is persisted, so a returning visitor with barely-changed data stares at skeletons on every single visit.

**Fix (both halves):**

- **Stale-while-revalidate (SWR) localStorage cache** on Digest + Positions. On mount, paint the last-seen list instantly from `localStorage`, then refetch in the background and reconcile. Solves the repeat-visit skeleton entirely.
- **Keep-warm ping.** A scheduled GitHub Actions workflow hits the backend `/health` every ~10 min during likely-active hours so the fetch behind the skeleton is fast even on a cold session. Far cheaper than upgrading the Render plan.

Result: on any repeat visit the user sees real data with zero skeleton; on a first/cold visit the backend is already warm so the fetch returns quickly.

## Behaviour

### SWR client cache (Digest + Positions)

- **Cache key** is per-user and per-endpoint, e.g. `cw:swr:jobs:<userId>` and `cw:swr:positions:<userId>`. Derive `<userId>` from the Supabase session so one browser shared across accounts never cross-contaminates. If no session/userId is available yet, skip the cache read (fall back to skeleton).
- **On mount:**
  1. Synchronously read the cached payload. If present and non-empty, render it immediately with `loading = false` (no skeleton).
  2. Kick off the live fetch in the background regardless of cache hit.
  3. When the live fetch resolves, replace state with fresh data and rewrite the cache. If it fails, keep showing the stale data (do not blank the screen) and surface a quiet "couldn't refresh" affordance - see edge cases.
- **Cold cache (first visit):** no cached payload → behave exactly as today (skeleton until fetch resolves). This is the only path that shows a skeleton, and keep-warm makes that fetch fast.
- **Reconcile signal:** while a background refresh is in-flight over stale data, show a subtle indicator (e.g. a small "Updating…" text or a thin top progress bar) so a returning user knows the numbers may tick. On success it disappears; the count-up / list simply updates. Keep it quiet - this is not a blocking spinner.
- **Cache freshness guard:** store a `savedAt` timestamp alongside the payload. If the cache is older than a hard ceiling (e.g. 24h), ignore it and show the skeleton instead of very stale data. Tune the ceiling to the pipeline cadence (jobs collected Mon & Thu).
- **Payload shape/versioning:** wrap the cached value as `{ v: <schemaVersion>, savedAt, userId, data }`. Bump `v` whenever the list row shape changes so an old cache from a prior deploy is discarded rather than rendered with missing fields. Wrap all reads in try/catch - a malformed/legacy entry must never crash the page; on parse failure, drop it and fall back to skeleton.
- **Digest specifics:** the cache covers the `/jobs` list (the heavy payload). `/user/me` and `/jobs/stats` may stay live-only, OR be cached with the same pattern - at minimum the job list must paint instantly. Filters/min-score are applied client-side to whatever list is present (cached or fresh), so filtering works immediately over the cached list.
- **Positions specifics:** cache the `/jobs/positions` catalog list. Search + pagination already run client-side over `positions`, so they work over the cached list with no change.

### Keep-warm ping

- Add `.github/workflows/keep-warm.yml`: a scheduled workflow that `curl`s the backend `/health` endpoint.
- **Cadence:** every ~10 min. Optionally scope the cron to daytime Israel hours (roughly 06:00-23:00 IST) to avoid pinging 24/7 - a warm service overnight has little value and it keeps the free-tier instance-hours down. Document the tradeoff in the workflow comments.
- The backend URL is provided via a repo secret/variable (do not hardcode). The job must be a no-op-on-failure (a missed ping is fine) and must never fail the Actions run in a way that pages anyone.
- `/health` already exists (`webapp/backend/main.py`) and is unauthenticated - no changes needed backend-side.
- **Note the ceiling:** keep-warm reduces cold starts but does not guarantee zero (deploys, long idle windows outside the cron scope, Render recycling). The SWR cache is the safety net for those cases; keep-warm just makes the uncached path fast most of the time.

## Files to Touch

- `webapp/frontend/lib/swrCache.ts` (new) - tiny helper: `readCache<T>(key, {maxAgeMs, userId, version})` and `writeCache(key, data, {...})`, both try/catch-wrapped, SSR-safe (guard `typeof window`).
- `webapp/frontend/app/(app)/digest/page.tsx` - read cache before first fetch; paint instantly on hit; background-refresh + reconcile indicator; write cache after `/jobs` resolves.
- `webapp/frontend/app/(app)/positions/page.tsx` - same pattern for the `/jobs/positions` list.
- `.github/workflows/keep-warm.yml` (new) - scheduled `/health` ping.
- `WEBAPP_SPEC.md` - document the SWR cache contract (keys, versioning, freshness ceiling) and the keep-warm workflow.

## How to QA

1. **Repeat visit is instant.** Load `/digest`, wait for data, navigate away, return (or reload). Real job cards render with **no skeleton frame**; a brief "Updating…" indicator appears and clears. Repeat for `/positions`.
2. **Cold cache still safe.** Clear `localStorage` (or open a fresh profile), load `/digest`. Skeleton shows, then data - no crash, no blank. Confirm the same for `/positions`.
3. **Stale cache survives a failed refresh.** With a cached list present, kill the backend (or block the API URL in devtools) and reload. The cached list stays on screen; a quiet "couldn't refresh" affordance appears instead of a blank/error page.
4. **Version + freshness guards.** Hand-edit a cache entry to an old `v` (or a `savedAt` older than the ceiling) and reload - the page ignores it and shows the skeleton, not malformed rows. Corrupt the JSON and reload - no crash, falls back to skeleton.
5. **No cross-account bleed.** Sign in as user A (populate cache), sign out, sign in as user B in the same browser. User B does not see user A's cached list.
6. **Keep-warm works.** Trigger `keep-warm.yml` manually (workflow_dispatch) and confirm a `200` from `/health`. After the backend has been idle past its spin-down window, confirm (via timing) that a request during active-cron hours returns fast, i.e. the service was already awake.
