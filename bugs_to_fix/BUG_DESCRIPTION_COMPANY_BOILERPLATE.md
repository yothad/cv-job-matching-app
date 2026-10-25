# BUG: Job description text leads with company boilerplate, not the role

## Status
🟢 Completed

## Severity
P2

## Description
Most job posts open with an "About us" paragraph (company pitch, values, diversity
statement); the role itself ("About the role", "What you'll do", "Responsibilities",
"Requirements") usually starts in the second paragraph or later. Three places in the repo
take the *start* of the description, so they mostly see the company, not the job:

1. **Labelling sheet excerpt** - `evals/make_labelling_sheet.py:write_quick_sheet` shows the
   first `EXCERPT_CHARS` (600) chars. On the 2026-10-20 golden-set sheet most excerpts were
   company pitches (e.g. Talkspace, A Security), so labelling leaned on title + location.
2. **Text feature for the text-vs-metadata experiment** - TF-IDF on the full description is
   dominated by company boilerplate, which is shared by every job at that company. That is
   noise for the text model and, under leave-one-company-out, a signal that can't transfer.
   The text feature should be the role section (title + role/responsibilities/requirements).
3. **The 4000-char cap in the pullers** (`description[:4000]` in ashby, greenhouse, comeet,
   lever, breezy, bamboohr, eightfold, google_careers, lemonade) - 20 of 60 golden-set
   descriptions hit the cap, so a long company intro pushes the requirements off the end.

Why "take the second paragraph" can't be done as-is: `ats/utils.py:strip_html` replaces every
tag with a space, so paragraph breaks are lost - only 11 of 60 golden-set descriptions contain
a newline at all. Role-section extraction needs either block tags (`</p>`, `<br>`, `</li>`,
`<h*>`) turned into newlines, or heading-keyword detection on the flat text ("about the
role", "the role", "what you'll do", "responsibilities", "requirements", "who you are",
"התפקיד", "דרישות", ...), falling back to the full text when no heading is found.

Side observation (separate issue if it recurs): some descriptions carry U+FFFD replacement
characters (Claroty: "We�re"), i.e. a decoding problem upstream of the golden set.

## Steps to Reproduce
1. `uv run python evals/make_labelling_sheet.py --n 60 --quick`
2. Open `evals/private/labelling_sheet.csv`, read the `excerpt` column.
3. Expected: the excerpt describes the role (responsibilities / requirements). | Actual: most
   excerpts describe the company.

## Fix scope
- **In scope (not eval-gated):** an `extract_role_section(text) -> str` helper used by (1) the
  labelling-sheet excerpt and (2) the experiment's text feature. Unit tests on English and
  Hebrew samples, including the no-heading fallback.
- **Out of scope here, eval-gated:** changing `strip_html` or the 4000-char cap changes what
  Gemini sees, i.e. the scoring input. Per CLAUDE.md that needs a before/after
  `evals/run_eval.py --baseline` run. File separately once the golden set baseline exists.

## Dependencies
- **Depends on:** —
- **Blocks:** the text-vs-metadata experiment (A vs B vs C) - its text feature should use the role section
- **Touches:** `evals/make_labelling_sheet.py`, a new helper (e.g. `evals/text_utils.py`), `tests/test_evals.py`
- **Spec files to update:** `future_devs/SCORER_EVAL_HARNESS_SPEC.md` (evals/* touched)
- **Night-ready:** no - the heading list and fallback rule need Yotam to eyeball real excerpts (English + Hebrew) before it is trusted as the text feature

## Fix Notes
Scope grew at Yotam's call (2026-10-21) from "eval-only extractor" to collect-time sections and
a Gemini input switch:

- **Collect time** (`ats/utils.py`): `split_sections` finds the role start, drops the company pitch
  and trailing EEO / benefits boilerplate, and splits out `responsibilities` and `requirements` by
  heading (English headings must be capitalised or end in ":" so prose doesn't match; Hebrew
  headings included). `role_description` excludes the requirements block so role + requirements
  never repeat text. `sections_from_named` maps named sections by heading.
- **Pullers return the full text** - the 18 per-puller `[:4000]` caps are gone. `collect_jobs.py`
  splits sections from the full text, then caps `description` at 4000 (unchanged value). This
  recovers requirements that used to fall past the cap (Wiz, PayPal, Cursor...).
- **Named sections:** Comeet's `Requirements` / `Responsibility` / `Who You Are` details (dropped
  before - only `Description` was kept, so Gemini never saw requirements for most Israeli startup
  jobs), Lever `lists`, Amazon `basic_qualifications` / `preferred_qualifications`.
  On the 60-job golden sheet, requirements were found in 16/60 from the stored (capped,
  Description-only) text; 26 of the misses were Comeet and most others were cap truncation.
- **Gemini input** (`matcher/gemini_scorer.py:_job_text_fields`): `role_description` +
  `requirements`, falling back to `description`. `SCORER_TEXT=description` reproduces the old prompt;
  verified byte-identical `score.py --dry-run` output in both modes on pre-split data. **Eval-gated
  and unmeasured** - no baseline existed; see `future_devs/SCORER_EVAL_HARNESS_SPEC.md`.
- **Webapp:** the Supabase `positions` catalog has no section columns, so webapp "Score now" keeps
  scoring from `description` (fallback) until a migration adds them - a separate, human step.
- Still open, out of scope: U+FFFD mis-decoding upstream; `strip_html` still flattens paragraphs.

Tests: `tests/test_role_sections.py` (splitter EN/HE, named sections, caps, Comeet / Lever pullers,
collect integration, prompt modes) + labelling-tool tests in `tests/test_evals.py`.
