# BUG: Positions detail panel shows "Go to posting" twice (button + redundant inline link)

## Status
🟢 Completed

## Severity
P3

## Description
The Positions page in-app detail view (`PositionDetailPanel` in
`webapp/frontend/app/(app)/positions/page.tsx`) renders the same "Go to posting"
call-to-action twice:

1. As the primary action button in the panel's `actions` row (the intended CTA).
2. As an inline text link inside the "Job description" fallback copy
   ("Open the posting via *Go to posting*.").

Both link to the same `apply_url`. The inline link is redundant and reads as a
duplicate. Keep the button; drop the inline link from the description fallback
(reword the sentence so it no longer repeats the CTA).

## Steps to Reproduce
1. Open the webapp, go to the Positions page.
2. Click any open position row to open the slide-over detail panel.
3. Observe the "Go to posting →" button near the top (actions row).
4. Scroll to the "Job description" section.
5. Expected: one "Go to posting" CTA. Actual: a second inline "Go to posting"
   link appears in the description fallback text.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** `webapp/frontend/app/(app)/positions/page.tsx`
- **Night-ready:** 🌙 yes
- **Spec files to update:** — (behavior unchanged; no spec owns this copy)

## Fix Notes
<!-- populated after fix -->
Fixed 2026-10-12 (night run): removed the inline `<a>` from the "Job description"
fallback. With an `apply_url` the copy now reads "The full description isn't stored
in the shared catalog. Use the Go to posting button above to open the original
posting." The no-link branch is unchanged. The actions-row button is the only CTA.
Verified with `npm run build`.

Original plan: remove the inline `<a>Go to posting</a>` at lines ~84-88 of `positions/page.tsx`
and reword the fallback sentence (e.g. "The full description isn't stored in the
shared catalog - use the Go to posting button above to open the original
posting."). The `actions`-row button is the single CTA.

## Night run 2026-10-12
Shipped unattended (gate: pytest, score.py --dry-run, frontend build all green; review pass). Morning QA:
1. Open a position with an `apply_url` - exactly one "Go to posting" button at the top, no link inside the "Job description" text.
2. Open a position without an `apply_url` (if any) - no button, text reads "...No application link is available for this position yet."
3. Read the fallback sentence at mobile width.
