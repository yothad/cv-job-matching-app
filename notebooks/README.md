# Analysis Notebooks

## analysis.ipynb

Exploratory analysis of scored jobs from `profiles/yotam/all_scores.jsonl`. Six sections:

1. Pipeline coverage (companies, ATS systems, jobs per VC tier)
2. Score distribution histogram with tier annotations
3. Score by VC tier (horizontal boxplot)
4. Top 15 companies by mean score (≥2 jobs)
5. Flag frequency across all scored jobs
6. Qualitative spot-check of tier 9-10 reasoning

Interactive:

```bash
uv run jupyter notebook notebooks/analysis.ipynb
```

Headless execution (regenerates outputs in-place):

```bash
uv run jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb --output analysis.ipynb
```
