| Field | Value |
|---|---|
| **Phase** | P8 |
| **Status** | `wrapped` |
| **Effort** | M |
| **Epic** | — (this is the epic root) |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `collect_jobs.py`, `score.py`, `webapp/backend/routers/jobs.py` |
| **Spec files to update** | `CLAUDE.md` architecture section |

## Overview

**What:** Track open/closed liveness on the jobs Yotam actually reads (the scored digest), so postings that have been taken down get marked `closed` and surfaced distinctly instead of sitting in the digest as live links that 404.

**Why:** The pipeline already gives us two of the three position states for free — `new` (recent `scored_at`, newest-first sort) and `seen` (anything already in `all_scores.jsonl` / `scored_jobs.json`; `score.py` skips re-scoring it). The genuinely missing state is `inactive`/`closed`: once a job lands in `scored_jobs.json` it lives there **forever**, even after the role is taken down. Yotam reads `digest.md`, clicks a promising link, and hits a dead posting. There is already an open bug about dead links (`BUG_LANDING_DEAD_GITHUB_LINKS.md`).

This epic scopes liveness to the curated, high-value set (scored jobs) rather than building a generic 3-state registry over the thousands of sub-threshold jobs Yotam never reads — where an "inactive" state carries near-zero value.

## Why this over a generic 3-state model

| State | Already exists? | Where |
|---|---|---|
| `new` | ✅ | `scored_at` recency + newest-first digest sort |
| `seen` | ✅ | `_load_seen_keys` skips anything in `all_scores.jsonl` + `scored_jobs.json` |
| `inactive`/`closed` | ❌ | **this epic** |

A generic registry over *all* positions would rebuild the `new`/`seen` machinery we already have, add a new persistent file for the long tail, and deliver value only on jobs Yotam reads. Scoping liveness to `scored_jobs.json` reuses the existing `apply_url` keying + merge function and attacks a documented bug.

## Children

| Order | Slug | Title | Effort | Depends on |
|---|---|---|---|---|
| 1 | `POSITION_LIVENESS_LIVE_SET` | Persist the live `apply_url` set from successful pulls | S | — |
| 2 | `POSITION_LIVENESS_STATUS_DIFF` | Diff scored jobs vs live set → `status` + `closed_at` | S | child 1 |
| 3 | `POSITION_LIVENESS_DIGEST_RENDER` | Render closed jobs distinctly in `digest.md` | S | child 2 |
| 4 | `POSITION_LIVENESS_WEBAPP` | Reflect `status` in the webapp digest API + cards | S | child 2 |

## The one critical guard (applies to every child)

A company that **errors on its pull** must NOT cause its jobs to be marked `closed` — an ATS hiccup would otherwise falsely "close" every role at that company. The live set persisted in child 1 must contain URLs **only from companies that pulled successfully this run**, and the diff in child 2 must only consider a job `closed` if its company was among the successful pulls. This is the load-bearing correctness constraint of the whole epic.

## How to QA

1. Run `collect_jobs.py` then `score.py` end-to-end; confirm scored jobs gain a `status` field and no live job is marked `closed`.
2. Simulate a company pull failure; confirm none of that company's previously-scored jobs flip to `closed`.
3. Confirm `digest.md` visually separates closed jobs from live ones.
4. Exit gate: `uv run python3 -m pytest tests/ -v` and `uv run python score.py --dry-run` both pass.
