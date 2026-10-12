---
model: opus
effort: high
---
# /night_run

Run several night-ready tasks one after another, unattended, and leave a morning report.

## Usage

```
/night_run [slug ...]
```

No slugs → build the run-list from every task whose spec sets Night-ready to `🌙 yes` (feature table row `| **Night-ready** | 🌙 yes |`, bug line `- **Night-ready:** 🌙 yes`). Slugs given → run those, in that order, but still only if each is night-ready (a slug that isn't is skipped and reported, never guessed at).

## Design invariants

- **Sequential.** One task at a time, in run-list order. One task's dev agent is the only writer while it runs.
- **Never stall.** Anything that would make a day session stop and ask (a failing gate, an ambiguous spec, a scope question) becomes *retry once, then park* and the run moves on. Only a global stop condition ends the run early.
- **Never end a turn between tasks.** Every turn except the final report ends with the tool call that starts the next unit of work (dispatching an agent, running the gate, or waiting on an agent). A turn that ends on prose ends the run.
- **Nothing wrong lands, and nothing lands on `main`.** `main` auto-deploys to Render (production). The night works on an integration branch `night/<date>`; a task's commits stay on it only when the full exit gate passed. Omer merges `night/<date>` into `main` in the morning.
- **The files are the run's memory, not the context.** Progress lives in the ledger (below), so a compaction or a crash loses nothing: re-read the ledger and continue.
- **Human-only steps are queued, never done:** Supabase SQL (no DDL access), secrets / env vars on Render or GitHub, scorer prompt/rubric/model/batch changes (gated on `evals/`, see CLAUDE.md), force pushes, deleting data, anything that needs a login. A task that cannot finish without one parks with the step written into the report.
- **Never work around a denial.** If a tool call is denied (permission system, auto-mode classifier, hook), do not retry it in another form and never edit settings. Park the task if it depends on it, send one `PushNotification` with the denied command (no secrets) and the reason, and continue with the next task.

## Paths

| What | Where |
|---|---|
| Day checkout (never touched by the run) | `/Users/omerhedvat/git/careers-watch` |
| Night worktree | `/Users/omerhedvat/git/careers-watch-night` on branch `night/<YYYY-MM-DD>` |
| Ledger (untracked, append-only) | `~/.careers-night/<YYYY-MM-DD>/ledger.md` |
| Agent reports | `~/.careers-night/<YYYY-MM-DD>/reports/<slug>.<role>.md` |
| Morning report (committed on the night branch) | `night_reports/<YYYY-MM-DD>.md` |

Every Bash call starts with `cd /Users/omerhedvat/git/careers-watch-night` or uses `git -C`. Never `cd` into the day checkout to make changes: Omer may have uncommitted work there.

## Step 0. Preflight (abort the run if a hard check fails)

1. `git -C /Users/omerhedvat/git/careers-watch fetch origin`.
2. Create or resume the worktree: if `night/<date>` exists, reuse it (resume); else `git -C /Users/omerhedvat/git/careers-watch worktree add /Users/omerhedvat/git/careers-watch-night -b night/<date> origin/main`.
3. In the worktree: `uv sync`, and `npm ci` in `webapp/frontend` (once).
4. Baseline exit gate on the untouched branch (Step 2 gate). Red baseline → abort: report "baseline red" with the failing command. Nothing can be judged against a red baseline.
5. `mkdir -p ~/.careers-night/<date>/reports`; if the ledger exists, this is a resume: skip every slug that already has a `SHIPPED` or `PARK` row.
6. Never copy `.env` files into the worktree. Checks that need secrets or production (live Supabase writes, Gemini calls, Render) are morning-QA items, not night checks.

## Step 1. Build the run-list

For each candidate, read its spec (`future_devs/<slug>_SPEC.md` or `bugs_to_fix/<slug>.md`) and admit it only if all hold, else record `SKIP | <slug> | <reason>`:

- `Night-ready` is `🌙 yes`.
- Status is `not-started` / `🔵 Open` (an `in-progress` task belongs to a human session).
- Every `Depends on` is wrapped, or ships earlier in this same run.
- No human-only step is required to finish it (see invariants). If the spec needs Supabase SQL, it is not night-ready; skip.

Order: dependencies first, then the given order (or bugs by severity, then features by effort, smallest first).

## Step 2. Per task (the loop)

1. **Start.** Record `PRE_SHA=$(git rev-parse HEAD)`. Flip the task to in-progress in its tracker + spec (as `/start_task` Phase A does) and commit `chore(<slug>): start` on the night branch. Ledger: `START | <slug> | <epoch>`.
2. **Dev agent** (fresh background Agent, `general-purpose`; if the spec has a `**Model**` field, pass that model). Prompt = the spec's full text + Touches list + the CLAUDE.md conventions that matter (hyphens not em-dashes in UI text, `ats/utils.py` helpers, no new dependencies, never `git add -A`) + "work only in /Users/omerhedvat/git/careers-watch-night, commit on the current branch, never push, never switch branches, never edit settings or permission files" + "if the spec is ambiguous, choose the conservative reading and write the question under `## Open questions` in your report instead of stopping". It writes its full report to `reports/<slug>.dev.md` and returns only: `verdict: done|blocked`, commits, files changed, open questions, `report: <path>`.
3. **Exit gate — the orchestrator runs it itself; never trust the dev agent's claim.** All must pass:
   ```bash
   cd /Users/omerhedvat/git/careers-watch-night
   uv run python3 -m pytest tests/ -q
   uv run python score.py --dry-run
   (cd webapp/backend && uv run python -c "import main" && uv run --with pytest python -m pytest tests -q)
   (cd webapp/frontend && NEXT_PUBLIC_SUPABASE_URL=https://example.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=dummy NEXT_PUBLIC_API_URL=https://example.invalid npm run build)
   ```
   Only the frontend build when `webapp/frontend` changed, only the backend lines when `webapp/backend` changed; pytest + dry-run always. Write long output to `reports/<slug>.gate.txt`; keep only pass/fail lines in context.
4. **Review agent** (a fresh agent, never the dev agent continued). Input: the spec, `git diff $PRE_SHA..HEAD`, and the gate result. It checks: every "How to QA" item is covered or explicitly listed as morning-QA, no files outside Touches without a reason, no scorer prompt/model change, no secrets, no schema change. Returns `pass` or `finding: <one line>`.
5. **Ship** (gate green and review pass): flip status to `completed` (feature) / `🟢 Completed` (bug), add a `## Night run <date>` note to the spec listing morning-QA items, commit `chore(<slug>): completed (night run)`. Ledger: `SHIPPED | <slug> | <commits> | <epoch>`. Do NOT wrap: wrapping (archive + push to main) happens in the morning after Omer's QA.
6. **Retry once** on a red gate or a review finding: a fresh dev agent with the failing output / finding (it must not see the first agent's reasoning, only the facts), then gate + a fresh review again. Rate-limit/quota deaths (HTTP 429, "usage limit") are environmental: wait for the reset if it's within the night, never count them as the retry.
7. **Park** if attempt 2 is still red: `git branch night-park/<slug> HEAD`, then `git reset --hard $PRE_SHA` on the night branch (the tracker flip goes with it, so the task returns to not-started). Ledger: `PARK | <slug> | <failing check + likely cause + branch> | <epoch>`. Send a `PushNotification` (one line). Continue with the next task.
8. After every SHIPPED, re-check skipped tasks whose only blocker was this one.

## Step 3. Global stop conditions

- 3 consecutive parks (rate-limit parks don't count) → something systemic broke; stop and report.
- The baseline gate turns red between tasks without a task causing it (environment broke) → stop and report.
- Rate limit with no reset inside the night → stop and report what's left.

## Step 4. Morning report

Write `night_reports/<date>.md`, commit it on the night branch, then `git push -u origin night/<date>` (the night branch, never `main`). Sections, slug + one line each, `none` when empty:

- **Summary** (max 10 lines): shipped / parked / skipped counts, and the one-line merge instruction.
- **✅ Shipped** - with commits and the morning-QA checks each needs (from the spec's How to QA items the night couldn't verify: browser checks, live Supabase, real Gemini).
- **⏸️ Parked** - failing check, likely cause, `night-park/<slug>` branch.
- **⏭️ Skipped** - reason.
- **🧑 Needs Omer** - every human-only step found (SQL to paste, env vars, decisions), copy-pasteable.
- **Open questions** - collected from the dev agents' reports.
- **How to land it:** `git checkout main && git pull && git merge --no-ff night/<date> && git push` (Render deploys on push), then `/wrap_task <slug>` per shipped task after QA.

Then send one `PushNotification`: `night done: <n> shipped, <n> parked - see night_reports/<date>.md`. Leave the worktree in place.

## Guardrails

- Never push to `main`, never force-push, never merge into `main`, never run `/wrap_task`.
- Never stage `.claude/settings.json`, `.env*`, or personal files under `profiles/`.
- Never call Gemini or write to production Supabase from the night run.
- One task's failure never stops the queue; only Step 3 does.
