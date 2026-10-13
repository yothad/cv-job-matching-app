| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `completed` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | WEBAPP_SCORE_NOW_BACKGROUND |
| **Blocks** | — |
| **Touches** | webapp/backend/routers/scoring.py, webapp/frontend/app/(app)/digest/page.tsx |
| **Night-ready** | no |

## Overview
On 2026-10-13 a Score now run scored 580 jobs while `positions.description` was still empty, so they
were judged on title/company/location only - and are deduped by apply_url forever. Let the user
re-score jobs that were saved without a description once the catalog has one.

## Behaviour
- `POST /score/` with `{"mode": "rescore"}`: candidates are this user's `scored_jobs` rows with a
  null/empty `description` whose catalog `positions` row now has a non-empty description. Same
  background run, cap and progress as WEBAPP_SCORE_NOW_BACKGROUND.
- Re-scored rows get the new score/reasoning/flags/description and a fresh `scored_at`; `applied` is
  untouched (upsert only writes the scored columns).
- Free: never checked against or counted toward the weekly limit (the missing descriptions were our bug).
- `GET /score/status` returns `rescore_available`; the digest shows "Re-score N with full descriptions"
  when N > 0 and nothing is running.

## How to QA
1. After a sync has filled `positions.description`, the digest shows "Re-score N with full descriptions".
2. Click it - progress runs, runs-used stays the same, scores/reasoning change, applied marks stay.
3. Afterwards the link disappears (or shows only jobs whose catalog row still lacks a description).
