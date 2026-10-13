# Scoring Calibration Notes

LLM-as-evaluator design for the careers-watch pipeline. Intended for a technical reader who wants to understand whether the scoring is principled or a black box.

---

## 1. Scoring Rubric

Derived from `profile.md`. Criteria are injected verbatim into the prompt; Gemini never sees this table - it sees the full prose profile.

| Criterion | Weight | Notes |
|---|---|---|
| Role type (DS / ML / Applied ML) | High | Hard filter: non-DS roles score ≤4 regardless of other signals |
| Seniority (Senior IC / Lead / Team Lead) | High | Junior or VP+ penalized; title-laundering noted in reasoning |
| Domain fit (cyber / fraud / fintech / trust & safety) | Medium | Explicit boost signal; absence does not disqualify |
| Lead / management signals | High | Primary target; military command accepted as partial credit with flag |
| Location (75-min commute from Netanya) | Hard filter | Out-of-range with no remote option = score 0, `dealbreaker-location` flag |
| VC tier (Tier 1/2 cyber VCs) | Low | ~1-pt boost for Tier 1 (YL, Team8, Glilot, Cyberstarts); Tier 3 stricter |
| Company quality (large established) | Low | Google, Palo Alto, CyberArk etc. get small boost for stability / brand |

Score bands from the rubric:

| Band | Meaning |
|---|---|
| 9-10 | Lead role at Tier 1/2 cyber/fraud company, or strong role at major company. Act immediately. |
| 7-8 | Strong fit on domain OR seniority, weaker on the other. Worth a closer look. |
| 5-6 | Adjacent fit - right domain wrong level, or right level wrong domain. FYI only. |
| 3-4 | Tangential. Brief mention, don't expand. |
| 0-2 | Do not surface unless asked. |

---

## 2. Prompt Design

Implementation: `matcher/gemini_scorer.py` (`build_batch_prompt`, `score_jobs_batch`).

**Batch size:** 10 jobs per API call (configurable via `GEMINI_BATCH_SIZE` env var). Each call sends all 10 jobs in a single prompt and receives a JSON array of 10 results.

**Context injection:** The candidate profile (`profile.md`) and CV (`cv.md`) are injected verbatim as `<profile>` and `<cv>` XML blocks at the top of every prompt. Job details follow as numbered `<job index="N">` blocks.

**Output schema requested:**
```json
[
  {
    "score": <integer 0-10>,
    "reasoning": "<one concise sentence>",
    "flags": ["<short-flag>", ...]
  }
]
```
Flag vocabulary is supplied by example: `location-unclear`, `lead-path-implied`, `management-gap`, `wrong-domain`, `dealbreaker-location`, `title-laundering`, `llm-not-security`.

**Model:** cascade `gemini-3.5-flash` -> `gemini-3.5-flash-lite` (`MODELS`, env `GEMINI_MODELS`; a 404/429/5xx moves to the next model; switched from `gemini-2.5-flash` on 2026-10-13 because 2.5 Flash 404s for new API keys; not yet measured by the eval harness, so scores before and after the switch are not directly comparable) with `response_mime_type: application/json`. The structured MIME type reduces fencing issues, but the parser defensively strips markdown code fences (```` ``` ````) before `json.loads()` as a fallback.

**Rate limiting:** sliding-window RPM limiter (default 8 RPM) implemented in `_rpm_wait()`. Quota errors (429 / RESOURCE_EXHAUSTED) retry up to 5 times with exponential back-off; after 5 failures a `QuotaExhaustedError` is raised and the run stops with partial results.

---

## 3. Calibration Spot-Check

5 real rows from `profiles/omer/all_scores.jsonl`, one per score tier, selected to illustrate calibration (scorer-error rows excluded).

| Score | Company | Title | Reasoning (excerpt) | Why this score makes sense |
|---|---|---|---|---|
| 9 | Native | AI/ML Engineer - AI Foundations Group | "This is an extremely strong fit for an applied, production-focused AI/ML role within cloud security at a Tier 1 VC-backed company..." | Lead path implied, cloud security domain, Tier 1 VC (YL/Team8 backed), production ML focus. Every signal aligns. |
| 8 | Wiz | Detection Software Engineer | "Excellent domain fit in cloud security at a highly desired company, aligning with the candidate's production ML and security expertise, but..." | Right company and domain, but titled SWE not DS. Lead path unclear. One signal missing justifies the -1 to -2. |
| 6 | Orca Security | Software Engineer - Security Intelligence & Engagement | "The role offers an excellent domain (cloud security), a strong company (Orca, YL-backed), and a perfect location, but the role is infra-heavy..." | Right domain, wrong craft. Adjacent, not a miss - worth knowing about. |
| 4 | MIND | Senior Backend Engineer | "The company is in the candidate's target cyber security domain and location, backed by a strong VC, but the role is for a Senior Backend Engineer..." | Correct company/domain/VC tier, but the role itself is not DS. Brief mention only. |
| 2 | MIND | Product Manager | "While the company, domain, and location are excellent fits within cybersecurity, the Product Manager role is a fundamental mismatch..." | Same company as the score-4 row but a role that can never be a partial fit. Score reflects job type, not company quality. |

---

## 4. Known Failure Modes

From 665 scored rows in `profiles/omer/all_scores.jsonl` (as of 2026-06-17):

| Failure mode | Frequency | Mitigation |
|---|---|---|
| `scorer-error` (Gemini 503 / RESOURCE_EXHAUSTED) | ~22% of rows | Retried up to 5x with back-off. Surviving jobs get `scorer-error` flag and score=0; they appear in `all_scores.jsonl` but are excluded from `scored_jobs.json` by the relevance threshold. |
| `not-a-ds-role` / `wrong-role-type` | ~3% of rows | Partially mitigated at collection by `_SKIP_TITLE_TERMS` denylist (sales, recruiter, PM, etc.) and `_KEEP_TITLE_TERMS` allowlist. Non-DS roles that slip through get flagged by the scorer. |
| Wrong-domain flags (`wrong-domain`, `infra-not-ds`, etc.) | ~40% of rows | Not mitigated at collection - most of these are valid ATS results from cyber companies that have non-ML openings. The scorer correctly downgrades them; they don't reach the digest at score >= 5. |
| Location false positives | Rare | Location pre-filter in `score.py` (`_location_prefilter`) drops non-Israel jobs. Comeet and Ashby pullers append country to location string to prevent silent drops on city-only strings. Roles listed as "Israel" but effectively requiring relocation are flagged `dealbreaker-location` by the scorer. |

---

## 5. Reproducibility

**Reproducing a score:** `uv run python score.py --dry-run` prints the exact prompt sent to Gemini for the first job in `new_jobs.json`, without consuming quota. The model is pinned to `gemini-2.5-flash`. Same prompt + same input produces the same output modulo minor temperature stochasticity (the structured JSON mode reduces variance further).

**Audit log:** every scoring run appends to `profiles/omer/all_scores.jsonl`. This means the full scoring history is preserved across profile updates. When `score.py --rescore` is run after a profile change, the new scores appear as new rows in the JSONL; the old rows remain, making it possible to diff score distributions before and after any profile edit.
