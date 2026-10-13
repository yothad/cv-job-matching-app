# BUG: scored_jobs.json keeps closed positions forever

## Status
✅ Wrapped

## Severity
P3

## Description
`score.py:_reconcile_status` marks vanished jobs `closed` but never removes them, so
`profiles/*/scored_jobs.json` (committed by CI twice a week) grows without bound. The digest only
shows the 30 most recent closed jobs anyway.

## Steps to Reproduce
1. Run the pipeline for a few months.
2. Expected: closed jobs age out | Actual: 75 of 135 entries were closed, some since July.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** score.py, tests/test_score_prune_closed.py
- **Spec files to update:** CLAUDE.md architecture section

## Fix Notes
Fixed 2026-10-13. New `score.py:_prune_closed` drops closed, non-applied jobs whose `closed_at` is
more than `_CLOSED_RETENTION_DAYS` (30) ago. Runs after the applied-from-digest sync (so a job just
marked applied is kept), skipped on --dry-run. Applied jobs are kept as history. A pruned job that
reappears is not rescored - its key is still in all_scores.jsonl. QA on the real file: 135 -> 111
(24 July closures pruned, 27 applied kept). Tests: tests/test_score_prune_closed.py.
