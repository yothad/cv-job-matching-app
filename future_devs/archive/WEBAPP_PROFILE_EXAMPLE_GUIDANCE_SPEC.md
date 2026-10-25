| Field | Value |
|---|---|
| **Phase** | P7 |
| **Status** | `completed` |
| **Effort** | S |
| **Epic** | WEBAPP_FIRST_RUN_COMPREHENSION |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | webapp/frontend/app/onboarding/page.tsx, webapp/frontend/app/settings/page.tsx |

## Overview

Users are asked to produce a profile.md but are never shown what a good one looks like; the Settings Profile tab is a bare textarea. This task adds an example profile, section-by-section guidance, and a lightweight completeness hint so users can self-check their profile.

This complements (does not duplicate) WEBAPP_PROFILE_UPLOAD_OR_PROMPT, which covers profile generation paths. This task is specifically about an EXAMPLE plus section guidance.

## Behaviour

- Add a collapsible "See an example profile" block in onboarding Step 1 and in the Settings Profile tab, showing a well-structured, generic (NOT Yotam-specific), anonymized example with these sections:
  - Who I am
  - What I'm looking for, in priority order
  - Location
  - Strong-fit signals
  - Weak-fit / skip
  - Dealbreakers
  - Notes for the matcher
  - Scoring rubric
- Inline guidance listing the required sections and one line on why each matters, so users can self-check completeness.
- A lightweight client-side "profile completeness" hint that checks for presence of the key section headings and nudges the user if a section (for example, the scoring rubric) is missing.
- The same example/guidance content is shared between onboarding and settings (single source, no copy drift).
- Keep the dark theme; copy uses hyphens, not em-dashes; the example is generic.

## Files to Touch

- webapp/frontend/app/onboarding/page.tsx
- webapp/frontend/app/settings/page.tsx

## How to QA

1. In onboarding Step 1, the "See an example profile" block is present and expands/collapses.
2. The same example block appears in the Settings Profile tab.
3. The example is generic (not Yotam-specific) and contains all listed sections.
4. Required-sections guidance with per-section "why it matters" is shown in both places.
5. Pasting a profile that omits the scoring rubric triggers the completeness hint flagging the missing section.
6. `uv run python3 -m pytest tests/ -v` passes and `uv run python score.py --dry-run` passes.
