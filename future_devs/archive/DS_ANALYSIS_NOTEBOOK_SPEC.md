| Field | Value |
|---|---|
| **Phase** | P4 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `notebooks/analysis.ipynb` (new), `notebooks/README.md` (new), `pyproject.toml` |

## Overview

A Jupyter notebook that turns `profiles/yotam/all_scores.jsonl` into a data science showcase. Demonstrates DS craft: data loading, cleaning, exploratory analysis, and visualisation — the kind of work a DS hiring manager opens immediately. Serves as proof that the pipeline surfaces real signal, not random noise.

The notebook must run end-to-end with `jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb` without errors.

## Behaviour

### Data source
- Primary: `profiles/yotam/all_scores.jsonl` — one JSON object per line
- Schema fields available: `company`, `title`, `location`, `score`, `reasoning`, `flags`, `source_vc`, `vc_tier`, `ats`, `apply_url`
- Filter out rows where `"scorer-error"` is in `flags` before any score analysis (these are Gemini failures, score=0 is not real signal)

### Notebook sections (in order)

**Section 0 — Setup**
- Imports: `pandas`, `matplotlib.pyplot`, `matplotlib.ticker`, `collections`, `json`, `pathlib`, `re`
- Load `all_scores.jsonl` into a DataFrame
- Print dataset summary: total rows, scorer-error rows dropped, clean rows

**Section 1 — Pipeline Coverage**
A single summary stats block printed as a markdown table or formatted print:
- Total companies tracked (from `company` column)
- Unique ATS systems seen
- Score range (min, max, mean, median) on clean rows
- Applied count (rows where `"applied"` flag or `applied` field is truthy — check schema)

**Section 2 — Score Distribution**
Histogram of scores (0–10 bins) on clean rows. Annotate with:
- Mean score (vertical dashed line)
- Counts per tier: tier-9-10 (strong fit), tier-7-8 (good fit), tier-5-6 (maybe), tier-0-4 (no fit)
Title: "Score Distribution — {N} jobs scored"

**Section 3 — Score by VC Tier**
Horizontal box plot: `vc_tier` on Y axis (1, 2, 3, unknown/manual), score on X axis.
- Shows whether Tier-1 VCs (cyber-pure) produce higher-scoring jobs than Tier-2/3
- Include N per tier in the Y-axis label: "Tier 1 (n=X)"

**Section 4 — Top Companies by Score**
Bar chart: top 15 companies by mean score, minimum 2 scored jobs per company.
- Sort descending
- Colour bars by vc_tier (tier-1 = dark blue, tier-2 = medium blue, tier-3 = light grey, manual = orange)
- Include job count as bar label

**Section 5 — Flag Frequency**
Horizontal bar chart of the 15 most common flags across all jobs (including scorer-error).
Flags are short strings like `"not-a-ds-role"`, `"infra-not-ds"`, `"scorer-error"`.
Shows what kinds of mismatches are most common.

**Section 6 — Score Over Time** *(include only if `scored_at` field exists in the data)*
Line chart: daily mean score over time. If field missing, skip this section and add a comment.

**Section 7 — Scoring Reasoning Quality Check**
Print 3 randomly-sampled jobs from tier 9-10, showing:
- company, title, score, reasoning (first 200 chars)
This is a qualitative calibration check embedded in the notebook output.

### Style
- Use `matplotlib` only (no seaborn, plotly, or other plot libs — keep dependencies minimal)
- Figure size: 10x5 for bar/line, 8x5 for histograms
- All plots save inline (no `plt.savefig` calls)
- Use `plt.style.use('seaborn-v0_8-whitegrid')` or `'ggplot'` — whichever is available, with a try/except fallback to default
- Colour palette: consistent blues/greys matching a professional DS portfolio

## Files to Touch

- `notebooks/analysis.ipynb` — new notebook (create `notebooks/` directory)
- `notebooks/README.md` — one paragraph: what the notebook shows, how to run it
- `pyproject.toml` — add `jupyter`, `matplotlib`, `pandas` as dev dependencies via `uv add --dev`

## How to QA

1. `uv run jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb --output notebooks/analysis_executed.ipynb` runs without error and the output notebook has no empty cells/exceptions.
2. Each of sections 1-5 produces visible output (printed table or a rendered chart).
3. `uv run python3 -m pytest tests/ -v` still passes (no regressions).
4. `uv run python score.py --dry-run` still passes.
5. Open the executed notebook and verify: score distribution histogram is non-trivial (not all one bin), top-companies bar chart has ≥5 companies, flag chart has ≥5 flags.
