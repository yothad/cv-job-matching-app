| Field | Value |
|---|---|
| **Phase** | P8 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | POSITION_LIVENESS |
| **Depends on** | POSITION_LIVENESS_STATUS_DIFF |
| **Blocks** | — |
| **Touches** | `score.py` (`_write_digest`) |
| **Spec files to update** | `CLAUDE.md` architecture section (`score.py` digest description) |

## Overview

**What:** Render `closed` jobs distinctly in `digest.md` so Yotam never wastes a click on a dead posting, while still keeping the mild signal of "a role I was eyeing just closed."

**Why:** The status computed in child 2 is only valuable if it changes what Yotam sees. This is the payoff step.

## Behaviour

In `_write_digest`:

- Partition visible jobs (already excludes `applied`) into **open** and **closed** by the `status` field. Treat missing/`open` as open.
- **Open jobs:** render exactly as today — grouped by `scored_at` date (newest first), score desc within date. No visual change.
- **Closed jobs:** collected into a single trailing section, e.g. `## Recently closed (N)`, sorted by `closed_at` newest-first. Render each with a muted treatment — strikethrough title and a `(closed YYYY-MM-DD)` suffix — and keep the link (so Yotam can still see what it was), but make it unmistakably not-live.
- If there are zero closed jobs, omit the section entirely (no empty header).
- Hyphens, not em-dashes, in all output (Yotam's preference per `CLAUDE.md`).
- Optionally cap the closed section to the most recent N (e.g. 30) and print a `(+K older closed hidden)` line rather than letting it grow unbounded — keep the digest readable. If capping, log the dropped count (no silent truncation).

## Files to Touch

- `score.py` — `_write_digest` partition + new closed-section renderer.

## How to QA

1. With at least one `status: closed` job in the store, run score; confirm `digest.md` has a `Recently closed` section with strikethrough titles and `closed` dates, placed after the live date groups.
2. Open jobs render identically to before (diff the open portion against a pre-change digest).
3. With no closed jobs, confirm the section is absent.
4. Confirm no em-dashes in the rendered output.
5. Exit gate: `pytest tests/ -v` and `score.py --dry-run` pass.
