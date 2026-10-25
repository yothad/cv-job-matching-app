# Spec: Scheduled Automation via GitHub Actions

## Status
`wrapped`

## Goal

Automate the two daily/weekly pipeline runs without requiring manual execution:

| Workflow | Schedule | Commands |
|---|---|---|
| `collect-and-score` | Mon + Thu at 07:00 UTC | `collect_jobs.py` → `score.py` |
| `refresh-companies` | Every 2 weeks on Sun at 06:00 UTC | `refresh_companies.py` |

Both workflows commit updated output files back to `main`.

## Secrets required

In the GitHub repo Settings → Secrets → Actions:

| Secret | Value |
|---|---|
| `GEMINI_API_KEY` | Yotam's Gemini API key |

No other secrets needed. The repo is private; no deploy keys required for self-push.

## Files to create

```
.github/
  workflows/
    collect-and-score.yml
    refresh-companies.yml
```

## Workflow: `collect-and-score.yml`

```yaml
name: Collect and Score Jobs

on:
  schedule:
    - cron: '0 7 * * 1'   # Monday 07:00 UTC
    - cron: '0 7 * * 4'   # Thursday 07:00 UTC
  workflow_dispatch:        # allow manual trigger

jobs:
  collect-and-score:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Collect jobs
        run: uv run python collect_jobs.py

      - name: Score jobs
        env:
          GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
        run: uv run python score.py

      - name: Commit updated outputs
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add profiles/*/digest.md profiles/*/scored_jobs.json profiles/*/all_scores.jsonl companies.json
          git diff --cached --quiet || git commit -m "chore: auto collect+score $(date -u +%Y-%m-%d)"
          git push
```

## Workflow: `refresh-companies.yml`

```yaml
name: Refresh Companies

on:
  schedule:
    - cron: '0 6 * * 0/14'  # Every 2 weeks on Sunday 06:00 UTC
  workflow_dispatch:

jobs:
  refresh:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up uv
        uses: astral-sh/setup-uv@v4
        with:
          version: "latest"

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Refresh companies
        run: uv run python refresh_companies.py

      - name: Commit updated companies.json
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add companies.json
          git diff --cached --quiet || git commit -m "chore: auto refresh companies $(date -u +%Y-%m-%d)"
          git push
```

## Notes

- `git diff --cached --quiet || git commit` skips the commit if nothing changed - no empty commits.
- `workflow_dispatch` allows triggering both workflows manually from the GitHub Actions UI.
- The `collect-and-score` workflow stages `companies.json` in addition to profile outputs because `collect_jobs.py` updates `last_jobs_pulled_at` and `consecutive_failures` on each run.
- `new_jobs.json` is gitignored and is not committed.

## Exit gate

After creating the workflow files:

```bash
uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```

Manual verification: push a branch, trigger `workflow_dispatch` from the Actions tab, confirm it completes without error.

## CLAUDE.md update

Add to the "What NOT to build (yet)" section: remove the GitHub Actions bullet (it is now built).
