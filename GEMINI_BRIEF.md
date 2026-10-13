# Planning brief for Gemini

You are helping plan the next phase of **careers-watch**, a personal job-search
automation pipeline. This document orients you. Several raw repo files are
attached alongside it — read them, then help plan.

## Your job

Act as a planning collaborator. Propose the next phase of work: new features,
coverage expansion, quality improvements, or strategic direction. For each
proposal give: the problem it solves, rough effort (XS/S/M/L), dependencies,
and why it fits this candidate's actual goals. Rank by value-to-effort.

Do **not** write code. Output a plan.

## What the project is

Personal job-search automation for Omer Hedvat — Israeli senior data scientist
(~8 yrs), specialized in fintech-fraud and cloud-security ML, targeting Team
Lead / Lead DS / Applied ML roles in cyber and fraud companies, Israel-based,
max ~75 min commute (Netanya south through greater Tel Aviv).

Pipeline (three independently-runnable scripts, three cadences):

1. `refresh_companies.py` (weekly) — Playwright scrapes 22 VC portfolios +
   merges a manual `big_companies.yml`, auto-detects each company's ATS, caches
   to `companies.json` (~2000 companies).
2. `collect_jobs.py` (daily) — hits each ATS REST API directly (18 ATS
   integrations: Comeet, Greenhouse, Lever, Workday, Ashby, etc.), filters by
   location, writes `new_jobs.json`.
3. `score.py` (daily) — sends each job to Gemini 3.5 Flash, scores against
   `profile.md` + `cv.md`, writes a ranked `digest.md`.

There is also a multi-user web app layer (Next.js + FastAPI + Supabase, on
Render) that was built out in Phase P2 — see `WEBAPP_SPEC.md`.

## Current state (read the ROADMAP files for detail)

- P0 Pipeline, P1 pipeline improvements, P2 Web App v1, and most of P3
  (coverage expansion) are **wrapped**.
- Active/open: `SCORING_RUBRIC_ABLATION` (scoring calibration doc), a few
  webapp post-launch polish items, and the long tail of VC/ATS coverage.
- No active epics. The bug tracker is essentially empty.
- Recent webapp UX polish (2026-06-17): onboarding now makes the Profile and CV
  steps optional (skippable, addable later in Settings), and both the onboarding
  API-key step and the Settings API Key tab now stress that Gemini's API is fully
  free with a direct AI Studio key link and how-to-get-a-key steps. Intent: lower
  signup friction for the multi-user web app. (Scoring still requires a profile,
  so a skipped profile means no results until one is added.)

So the interesting question is **what the next epic should be**, not finishing
an in-flight one.

## Hard constraints — do not propose anything that violates these

**Experimental Phase:** the project is now also a learning sandbox for RAG and
Agentic systems. Vector databases (e.g. Chroma, FAISS), multi-agent frameworks,
automated resume tailoring, and LLM calls anywhere in the pipeline (upstream or
downstream of scoring) are explicitly permitted and actively wanted.

The project still has deliberate scope discipline. These remain intentionally
OUT of scope unless there's an overwhelming reason:

- No email / Slack / Telegram delivery — Omer reads `digest.md` directly.
- No generic scraping framework or plugin system — per-VC and per-ATS adapters
  are the chosen design; don't refactor to a generic engine.
- User-facing output uses hyphens, never em-dashes.

If a proposal would cross one of these lines, flag it explicitly and explain
the tradeoff rather than assuming it's fine.

## Good directions to consider (not exhaustive — push back and add your own)

- Scoring quality: calibration, rubric ablation, reducing false positives/
  negatives, spot-check tooling, measuring score stability.
- Coverage: more Israeli VCs / ATSes, dedup quality, dead-company pruning.
- Signal: trend analysis over time (which companies hire, score drift), the
  analysis notebook direction.
- Web app: turning the personal pipeline into a real multi-user product, or
  deciding to keep it personal.
- Reliability: failure recovery, stale-entry handling, observability of the
  weekly/daily runs.

## Attached files and why

- `CLAUDE.md` — architecture, conventions, gotchas, full scope discipline.
  This is the most important file.
- `profile.md`, `cv.md` — the candidate's filter intent and capability ground
  truth. Any feature about matching quality must respect these.
- `ROADMAP.md`, `ROADMAP_ARCHIVE.md` — what's planned vs. already shipped, so
  you don't re-propose finished work.
- `README.md` — external summary, architecture diagram, scale numbers.
- `WEBAPP_SPEC.md` — the web app product layer.
