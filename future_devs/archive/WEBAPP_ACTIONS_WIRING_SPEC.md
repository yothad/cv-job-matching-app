# Spec: webapp_actions_wiring

**Slug:** webapp_actions_wiring  
**Epic:** Web App v1  
**Effort:** S  
**Depends on:** webapp_scaffold ✅

---

## Goal

Decouple scoring from the GitHub Actions collect workflow. In the webapp, scoring is user-triggered via the web server — it must not run in CI. Update the existing `collect-and-score.yml` to only collect jobs and commit `new_jobs.json`. Leave `refresh-companies.yml` untouched.

---

## Context

The existing `.github/workflows/collect-and-score.yml` runs both `collect_jobs.py` AND `score.py`. In the webapp architecture:

- `collect_jobs.py` — stays in GitHub Actions (runs Mon + Thu, writes `new_jobs.json`, commits it)
- `score.py` — moves out of GitHub Actions; triggered per-user via the web API
- `refresh_companies.py` — stays in GitHub Actions (runs every 2 weeks, already correct)

---

## Changes

### `.github/workflows/collect-and-score.yml` — rename and strip scoring step

Rename the workflow (the `name:` field, not the filename) to `Collect Jobs` and remove the scoring step + GEMINI_API_KEY secret reference. Update the commit step to only commit `new_jobs.json` and `companies.json`.

New file content:

```yaml
name: Collect Jobs

on:
  schedule:
    - cron: '0 7 * * 1'   # Monday 07:00 UTC
    - cron: '0 7 * * 4'   # Thursday 07:00 UTC
  workflow_dispatch:

jobs:
  collect:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Install dependencies
        run: uv sync

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Collect jobs
        run: uv run python collect_jobs.py

      - name: Commit collected jobs
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add new_jobs.json companies.json
          git diff --cached --quiet || git commit -m "chore: auto collect $(date -u +%Y-%m-%d)"
          git push
```

### `.github/workflows/refresh-companies.yml` — no changes

Leave this file exactly as-is.

---

## Touches

- `.github/workflows/collect-and-score.yml` (update — remove score step, update name and commit step)

---

## Exit gate

```bash
# Verify score.py reference is gone from the workflow
grep -n "score.py" C:/repos/cv-job-matching-app/.github/workflows/collect-and-score.yml
# Expected: no output (grep returns exit code 1 = not found = correct)

# Verify collect step still present
grep -n "collect_jobs.py" C:/repos/cv-job-matching-app/.github/workflows/collect-and-score.yml

# Verify new_jobs.json is in the commit step
grep -n "new_jobs.json" C:/repos/cv-job-matching-app/.github/workflows/collect-and-score.yml

# Python pipeline unaffected
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
