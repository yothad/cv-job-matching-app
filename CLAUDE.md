# CLAUDE.md

This file gives you (Claude Code) the context you need to work productively in this repo. Read it at the start of every session. It is not user-facing documentation - that's the README.

## What this project is

Personal job-search automation for Omer Hedvat - Israeli senior data scientist, ~8 years experience, deep specialization in fintech fraud and cloud security ML, currently targeting Team Lead / Lead DS / Applied ML roles in cyber and fraud companies. Israel-based, commutes from home up to 75 minutes max (Netanya south to south Tel Aviv area).

The system scrapes Israeli cyber/fintech VC portfolios plus a curated list of large security companies, pulls open jobs from each company's ATS, scores each job with Gemini against the candidate profile, and outputs a ranked markdown digest.

## Permissions

Before asking the user for any permission, run `/fewer-permission-prompts` to auto-add the missing pattern to `.claude/settings.json`.

## Always read these two files first

- `profile.md` - Omer's filter intent (what he wants, what to skip, scoring rubric)
- `cv.md` - Omer's CV (capability ground truth)

These are the source of truth for matching. When in doubt about whether something is a fit, re-read these rather than guessing from session memory.

## Architecture

> **Experimental Phase:** We are actively extending this project with RAG and Agentic modules. Vector databases, multi-agent frameworks, and upstream/downstream LLM calls are explicitly permitted.

Three scripts, three cadences. They must remain independently runnable.

```
refresh_companies.py  (weekly)
  └─ scrapes VC portfolio pages (auto-discovered)
  └─ merges big_companies.yml (manually maintained, never auto-discovered)
  └─ for new VC companies: discovers careers URL + detects ATS
  └─ for stale VC entries (30d+ since last_verified_at, or consecutive_failures >= 3): re-verifies
  └─ big_companies.yml entries are NEVER re-verified automatically - edit the YAML to update
  └─ writes to companies.json (merge, never overwrite)

collect_jobs.py  (daily)
  └─ reads companies.json
  └─ hits each ATS API directly using cached careers_url + ats_params
  └─ if location_filter is set: drops jobs whose location doesn't contain the filter string
  └─ writes new_jobs.json
  └─ NEVER does careers discovery - that's refresh's job
  └─ on failure: increment consecutive_failures, continue with next company

score.py  (daily, after collect_jobs.py)
  └─ reads new_jobs.json + profile.md + cv.md
  └─ cv_default / cv_lead in score_config.json may point at local-only files; if a
     path is missing (e.g. in CI) it warns and falls back to profile cv.md (lead -> default)
  └─ sends each job to Gemini 2.5 Flash
  └─ writes digest.md grouped by score tier (9-10, 7-8, 5-6)
  └─ exits non-zero if GEMINI_API_KEY is missing for any profile (so CI goes red)
```

In CI (`.github/workflows/collect-and-score.yml`) `scripts/sync_positions.py` runs
between collect and score with `continue-on-error: true` - it mirrors new_jobs.json
(incl. descriptions) into the webapp's shared Supabase `positions` table, which is
also what the webapp's "Score now" endpoint reads. A Supabase outage must never
block scoring.

## Two sources of companies

**VC portfolios** (automated): One file per VC under `vcs/`. Playwright scrapes portfolio pages. For each company found, `ats/detect.py` auto-discovers the careers URL and ATS. Stale entries get re-verified on every weekly run.

**`big_companies.yml`** (manual): Large established companies whose portfolio is not scraped. All fields (`careers_url`, `ats`, `ats_params`) must be verified by hand. `refresh_companies.py` merges this file into `companies.json` on every run but never auto-discovers or re-verifies these entries - edit the YAML to update.

**Rule: never try to scrape or auto-discover big_companies.yml entries.** The whole point of the manual list is that these companies don't come from a VC portfolio and their ATS params are known upfront.

### big_companies.yml schema

```yaml
- name: Wiz                          # required - display name
  website: https://wiz.io            # required - company homepage
  careers_url: https://...           # required - manually verified ATS/careers URL
  ats: greenhouse                    # required - greenhouse|comeet|lever|workday|smartrecruiters|ashby|other
  ats_params:                        # required - params the ATS puller needs (empty dict {} if not yet configured)
    board_token: wiz                 #   Greenhouse: board_token
                                     #   Comeet: company_uid + token
  category: cyber                    # required - cyber|fraud|fintech|security|general
  location_filter: israel            # optional - substring filter on job location (case-insensitive)
  notes: "free text"                 # optional
```

### Adding a new big company

1. Add an entry to `big_companies.yml` with all required fields
2. If `ats: greenhouse`: verify `board_token` by checking `https://boards.greenhouse.io/<board_token>` loads jobs
3. If `ats: comeet`: visit the careers page, extract `company_uid` and `token` (see Common gotchas below)
4. Set `location_filter: israel` to drop non-Israel jobs before scoring
5. Run `uv run python refresh_companies.py` - the entry appears in `companies.json`
6. Run `uv run python collect_jobs.py` - confirm jobs appear in `new_jobs.json`

### TODO entries in big_companies.yml

Entries with `ats_params: {}` are skipped by `collect_jobs.py` (no params = nothing to pull). They appear in `companies.json` as placeholders. To activate one: fill in `ats_params` in the YAML, then re-run `refresh_companies.py`.

## companies.json schema

This is a persistent cache, not a throwaway. Treat it as the project's state of the world.

```json
{
  "name": "Acme Security",
  "website": "https://acme.io",
  "source_vc": "YL Ventures",
  "vc_tier": 1,
  "careers_url": "https://acme.comeet.co/jobs",
  "ats": "comeet",
  "ats_token": "acme_xyz123",
  "discovered_at": "2026-05-04T07:00:00Z",
  "last_verified_at": "2026-05-04T07:00:00Z",
  "last_jobs_pulled_at": "2026-05-04T07:00:00Z",
  "consecutive_failures": 0
}
```

## Conventions

- Python 3.11+, `uv` for dependency and venv management
- One file per VC under `vcs/` (e.g. `vcs/yl_ventures.py`) - per-VC adapters, not a generic scraper
- One file per ATS under `ats/` (e.g. `ats/comeet.py`) - per-ATS pullers, not a generic puller; shared utilities in `ats/utils.py`
- `ats/__init__.py` owns the `ATS_PULLERS` dispatch dict - `collect_jobs.py` imports from there
- Each adapter/puller fails per-company; orchestrators never crash on a single company error
- Print clear progress at every stage so manual runs are inspectable
- Hyphens, not em-dashes, in any user-facing output (Omer's preference)

## Dependencies (intentionally minimal)

- `playwright` - JS-rendered VC portfolio pages
- `httpx` - ATS APIs and any other HTTP
- `google-genai` - the new unified Gemini SDK. NOT `google-generativeai` (the old package)
- `python-dotenv` - loading `.env`

If you need something else, ask first. The simpler this dependency tree stays, the easier this project is to maintain a year from now.

## Secrets

- `.env` in repo root, gitignored
- `GEMINI_API_KEY=...`
- Never commit, never log, never include in error messages

## What NOT to build (yet)

These are intentionally out of scope for the current iteration. Do not add them unless explicitly asked:

- Email, Slack, or Telegram delivery (Omer reads `digest.md` directly)
- A generic scraping framework or plugin system (per-X adapters are the right choice here)
- VCs not already implemented (add one at a time, end-to-end, with verification)
- ATSes not already implemented (same)

If a user request would add any of these, confirm explicitly before building.

## Israeli context that matters

- Comeet is the dominant ATS for Israeli startups. Prioritize Comeet support over Greenhouse/Lever. Many YC-style global ATSes are also present (Greenhouse, Lever, Workday, Ashby) but Comeet covers the long tail of Israeli companies.
- Hebrew may appear in job titles and descriptions. Do NOT translate before sending to Gemini - the model handles Hebrew well and translation loses signal.
- Location parsing matters. Omer's commute radius is max 75 minutes from home. Anywhere from Netanya south through Herzliya, Ra'anana, Petach Tikva, Tel Aviv, Ramat Gan, Bnei Brak, Holon, Bat Yam is in range. Haifa, Beer Sheva, and Jerusalem are out of range without remote flexibility.
- VC tiering for the matcher's `vc_tier` field:
  - Tier 1 (cyber-pure): YL Ventures, Team8, Glilot, Cyberstarts, Hyperwise, Merlin, JVP, Magenta VC, Greenfield Partners, Hetz Ventures, 10D
  - Tier 2 (generalist with strong cyber/fintech): Viola, Viola Ventures, Viola Growth, Pitango, TLV Partners, Vertex Israel, Bessemer, Insight, 83North, Grove, StageOne Ventures, Elron Ventures, Red Dot Capital, Qumra Capital, Entrée Capital
  - Tier 3 (adjacent, lower signal): NFX, Firstime, FinTLV, Champel, Amiti Ventures, Triventures, Target Global

## Common gotchas

- **Comeet token discovery:** the careers page HTML embeds a per-company token in the embed script URL. Extract via regex on the page source, don't rely on a public directory API.
- **Lazy-loaded portfolios:** some VC pages load portfolio entries on scroll. Playwright needs to scroll to bottom and wait for network idle before extracting.
- **ATS redirects:** company "Careers" links sometimes go through one or two redirects before landing on the actual ATS URL. Follow redirects in `ats/detect.py` and detect from the final URL.
- **Gemini JSON wrapping:** Gemini Flash sometimes returns JSON wrapped in markdown code fences (```json ... ```). Strip these before `json.loads()`. Robust parser, not strict.
- **Hebrew filenames or content:** make sure all file I/O is UTF-8. Default on modern Python but worth being explicit.
- **location_filter vs. bare city names:** `location_filter` is a plain substring match on the job's location string. Comeet often returns a location `name` of just "Tel Aviv" (country only in the `country` ISO code), and Ashby returns a bare city (country in the structured `address`). A naive "israel" filter silently drops these Israeli jobs. The Comeet and Ashby pullers therefore append the expanded country to the location string (e.g. "Tel Aviv, Israel") so the filter matches on country, not just city. When adding a new ATS, do the same - use `ats/utils.py:expand_country` (ISO alpha-2 -> country name) and `qualify_location` (append the country name when a string carries only a bare ISO code). Two other collapse shapes to watch: SuccessFactors/jobs2web emits `"Ra'anana, IL, 4366202"` (ISO code, run it through `qualify_location`), and Workday collapses multi-location postings to `"N Locations"` in the list view - the puller substitutes the real set from the detail endpoint's `location` + `additionalLocations`.

## Debugging workflow

When something breaks, in this order:

1. **Issue with a specific company?** Check that company's entry in `companies.json` for `last_verified_at` and `consecutive_failures`. If failures are high, the careers URL is probably stale.
2. **Issue with a VC scrape?** Run the adapter directly: `uv run vcs/yl_ventures.py`. Each adapter should have a `__main__` block that prints results.
3. **Issue with an ATS pull?** Run the puller directly with a known token: `uv run ats/comeet.py <token>`.
4. **Issue with scoring?** Use `score.py --dry-run` to see the exact prompt being sent to Gemini without burning quota.

## Adding a new VC

1. Create `vcs/<vc_name>.py` modeled on `vcs/yl_ventures.py`
2. Export a function that returns `list[{"name": str, "website": str}]`
3. Register it in `refresh_companies.py`'s VC list
4. Run `refresh_companies.py` and verify new entries appear correctly in `companies.json`

## Adding a new ATS

1. Create `ats/<ats_name>.py` modeled on `ats/comeet.py`
2. Export a function `fetch_positions(*args) -> list[dict]` returning normalized `{title, location, description, apply_url}` dicts
3. Add a lambda to `ATS_PULLERS` in `ats/__init__.py` mapping the ATS name to the right call signature
4. Update `ats/detect.py` to identify it from URL pattern or HTML signature
5. Test against a known company that uses this ATS

Use `ats/utils.py` for the shared `HEADERS` and `strip_html` - don't redefine them per module.

**Single-tenant pullers:** some companies self-host careers (no third-party ATS) - e.g. `ats/lemonade.py` (Next.js `__NEXT_DATA__`), `ats/privya.py` (WordPress REST API). These take no params; register them as `"name": lambda params: _fetch_name()` and wire the company via `scripts/import_careers.py` (which locks the entry as `skip_reason=manual_verified` so refresh never re-discovers it). Detection (`ats/detect.py`) is skipped for these - they are hand-verified, not auto-discovered.

## Scope discipline

This is plumbing - scrape, score, surface. The mission is not to expand into a full job-application platform. Specific anti-patterns:

- Building "smart" features that add LLM calls to non-matcher code (e.g. LLM-based careers page discovery). Cheaper deterministic methods exist for almost everything except scoring.
- Building abstractions before there are 3+ concrete cases. Per-adapter approach is correct - don't refactor to a generic scraper after only two VCs are done.
- Adding state beyond what's strictly needed. companies.json + new_jobs.json + digest.md are the only persistent files. Resist the urge to add caches, indexes, or audit logs.

If a request feels like mission expansion, surface that to Omer before implementing.

## Reference implementations (read, do not vendor)

Local read-only clone of the closest prior art. Consult before designing, cite in the spec.

| Building | Read first |
|---|---|
| The scorer eval harness (P13), or any grader / golden-set / pass@k work | `/Users/omerhedvat/git/ECC/skills/eval-harness/SKILL.md` — eval-driven-development vocabulary, capability vs regression evals, the three grader types, pass@k. Structure only; it ships no runnable harness. |
| Model routing, batch cost control, or budget caps on Gemini calls | `/Users/omerhedvat/git/ECC/skills/cost-aware-llm-pipeline/SKILL.md` — complexity-based model selection and an immutable `CostTracker`. Its thresholds are hand-tuned, so treat them as a starting shape, not as tuned values. |

MIT-licensed. Borrowing structure is fine; copying code requires attribution.

## Task management

This project uses a lightweight task system modeled on the PowerME project. Read before filing or starting any task.

### Tracker files

- `ROADMAP.md` — active features and epics
- `ROADMAP_ARCHIVE.md` — wrapped features (history)
- `bugs_to_fix/BUG_TRACKER.md` — active bugs
- `bugs_to_fix/ARCHIVE.md` — wrapped bugs (history)

### Slash commands (in `.claude/commands/`)

| Command | Purpose |
|---|---|
| `/file_task` | File a new bug or feature |
| `/start_task <slug>` | Begin implementation of a task |
| `/qa_task <slug>` | Run QA tiers before wrapping |
| `/wrap_task <slug>` | Archive a completed+QA'd task |
| `/orchestrate_epic <slug>` | Execute all children of an epic in waves |
| `/tasks_status` | Print a dashboard of all active work |

### Task lifecycle

```
not-started → in-progress (/start_task Phase A)
            → completed   (/start_task Phase B — exit gate passes; STOPS HERE)
            → wrapped     (user runs /qa_task, then /wrap_task — commits + pushes)
```

**Rule: `/start_task` always stops at `completed`. Never auto-chains to QA or wrap. The user must explicitly run `/wrap_task <slug>` to land changes.**

### Exit gate (required before marking completed)

```bash
uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```

Both must pass with no errors.

### Scoring changes are gated on the eval

`matcher/gemini_scorer.py` produces the number the entire digest is ranked by, and it is
currently unmeasured. Before changing the scoring prompt, rubric, batch size, or model:

1. If `evals/` does not exist yet, the change you are about to make is unmeasurable — say so
   to the user and offer `future_devs/SCORER_EVAL_HARNESS_SPEC.md` (P13) first. Do not
   silently proceed and do not claim the change is an improvement.
2. If `evals/` exists, run `uv run python evals/run_eval.py --baseline evals/baseline.json`
   before and after. Report both numbers. A change that moves band accuracy or hard-filter
   recall down is a regression regardless of how much better the new prompt reads.

This is the repo's instance of the honesty rule: **no scoring claim without an eval behind it.**

### Domain → Spec routing

When you touch these files, update the corresponding spec:

| Files touched | Spec to update |
|---|---|
| `score.py` | `CLAUDE.md` architecture section |
| `matcher/gemini_scorer.py` | `CLAUDE.md` architecture section **+ `future_devs/SCORER_EVAL_HARNESS_SPEC.md`** |
| `profile.md`, `cv.md`, `profiles/*/score_config.json` (scoring rubric) | `docs/scoring_calibration.md` **+ `future_devs/SCORER_EVAL_HARNESS_SPEC.md`** |
| `evals/*` | `future_devs/SCORER_EVAL_HARNESS_SPEC.md` |
| `collect_jobs.py` | `CLAUDE.md` architecture section |
| `refresh_companies.py` | `CLAUDE.md` architecture section |
| `ats/*.py` | `CLAUDE.md` Adding a new ATS section |
| `vcs/*.py` | `CLAUDE.md` Adding a new VC section |
| `profiles/*/score_config.json` | `CLAUDE.md` score_config schema |
| `WEBAPP_SPEC.md` | Update in place |
