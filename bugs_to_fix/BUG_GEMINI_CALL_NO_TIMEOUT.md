# BUG: Gemini calls have no HTTP timeout - a hung call stalls a scoring run indefinitely

## Status
✅ Wrapped

## Severity
P2

## Description
`matcher/gemini_scorer.generate()` calls `client.models.generate_content` with no request
timeout. A call that hangs (PowerME measured `-latest` models hanging 60s on device) blocks the
scoring batch with no limit. Since background Score now (WEBAPP_SCORE_NOW_BACKGROUND), a run with no
progress for 10 minutes reads as interrupted. The button re-enables while the worker is still
stuck, and a second run can overlap it (review note on day/score-async, 2026-10-13).

## Steps to Reproduce
1. A Gemini model that accepts the connection but never answers.
2. Score now, or `score.py`.
3. Expected: the call gives up after a bounded time and the cascade tries the next model.
   | Actual: the batch waits indefinitely.

## Dependencies
- **Depends on:** BUG_GEMINI_5XX_DROPS_JOBS ✅
- **Blocks:** —
- **Touches:** `matcher/gemini_scorer.py`, `tests/test_gemini_cascade.py`
- **Spec files to update:** `CLAUDE.md` architecture section (score.py cascade line)
- **Night-ready:** no - filed and fixed in a daytime session
- **Owner split:** careers-day owns `webapp/backend/routers/scoring.py`. The timeout is set per request
  inside `generate()`, so no change is needed where the client is created.

## Fix Notes
- `generate()` adds `http_options.timeout` (`_TIMEOUT_MS`, default 60s, env `GEMINI_TIMEOUT_S`) to every
  call; google-genai 1.74 accepts it per request, so the client construction in scoring.py is untouched.
- `_status_code()` maps a client-side timeout to 504, so it falls through the cascade, puts the model
  on cooldown and is retried with backoff like any 5xx.
- Worst case for one batch is now bounded (two models x 60s per attempt plus backoff). An extreme run of
  backoffs can still exceed the 10-min stale window; that's the accepted residual.
- Tests: every call carries the timeout; a timeout on model A falls through to model B.
