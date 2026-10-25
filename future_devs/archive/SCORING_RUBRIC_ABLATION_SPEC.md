| Field | Value |
|---|---|
| **Phase** | P4 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `docs/scoring_calibration.md` (new), `docs/` (new dir) |

## Overview

Write `docs/scoring_calibration.md` — a short document framed as "LLM-as-evaluator calibration notes." It demonstrates that the scoring pipeline is principled, not a black box: the rubric has intentional design choices, the model's output is reproducible and inspectable, and the author understands the failure modes. Directly relevant to roles in applied ML and LLM evaluation.

Audience: a technical hiring manager who clicked into the repo and wants to understand how the scoring actually works and whether it's rigorous.

## Behaviour

### Document structure

**Section 1 — Scoring rubric summary**
A clear table of the scoring criteria used in `profile.md`, presented as a scoring rubric. Extract the real criteria from `profiles/yotam/profile.md` and format as:

| Criterion | Weight | Notes |
|---|---|---|
| Role type match (DS / ML / Applied ML) | High | Hard filter: non-DS roles score ≤4 regardless of other signals |
| Seniority match (senior IC / lead) | High | Junior or VP+ roles penalised |
| Domain fit (cyber / fraud / fintech) | Medium | Bonus, not required |
| Company quality (VC tier, stage) | Low | Tie-breaker only |
| Location (75-min commute from Netanya) | Hard filter | Out-of-range = auto-disqualify |

Extract the actual weights/criteria from profile.md — do not invent them.

**Section 2 — Prompt design**
Describe the actual prompting approach (read `matcher/gemini_scorer.py` for the real prompt):
- Batch size used
- How the candidate profile and CV are injected
- Output schema requested (score, reasoning, flags)
- How JSON extraction is done (the markdown-fence strip before json.loads)

**Section 3 — Calibration spot-check**
A table of 5 real scored jobs selected from `profiles/yotam/all_scores.jsonl` to illustrate calibration across the score range. Pick one from each tier: 9-10, 7-8, 5-6, 3-4, 0-2 (excluding scorer-error rows). For each show: company, title, score, reasoning (first 150 chars), and one-line human annotation.

Example format:
| Score | Company | Title | Reasoning (excerpt) | Why this score makes sense |
|---|---|---|---|---|
| 9 | … | … | … | … |

**Section 4 — Known failure modes**
Short list of observed failure patterns with frequency:
- `scorer-error` — Gemini 503 during high-demand spikes; handled by flag, not excluded from digest
- `not-a-ds-role` — most common flag; pipeline pre-filters by title allowlist but some slip through
- Misclassified domain — role at a cyber company but actually a pure backend/infra role
- Location false positives — remote roles, or roles listed as "Israel" but actually hybrid with travel

For each: how common it is (rough % from the data), and whether it's mitigated at collection, scoring, or not at all.

**Section 5 — Reproducibility**
Two short paragraphs:
1. How to reproduce a score: `uv run python score.py --dry-run` prints the exact prompt. The model is pinned to `gemini-2.5-flash`. Same input → same output ±minor stochasticity.
2. The `all_scores.jsonl` append log means every scoring run is auditable — you can see how a job's score changed if profile.md was updated and `--rescore` was run.

### Tone
- Technical but concise. Write for a peer who understands LLM eval, not a PM.
- No fluff. Each section earns its place.
- Hyphens, not em-dashes.

## Files to Touch

- `docs/scoring_calibration.md` — new (create `docs/` directory)

## How to QA

1. `docs/scoring_calibration.md` exists and renders cleanly as markdown.
2. Section 1 rubric table matches actual criteria in `profiles/yotam/profile.md` — not invented.
3. Section 3 spot-check uses 5 real rows from `profiles/yotam/all_scores.jsonl` (verify company names exist in file).
4. Section 2 prompt design matches what's actually in `matcher/gemini_scorer.py`.
5. `uv run python3 -m pytest tests/ -v` passes.
6. `uv run python score.py --dry-run` passes.
