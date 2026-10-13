-- Background "Score now": progress of the user's latest scoring run, polled by
-- the digest via GET /score/status. Shape (written by routers/scoring.py):
-- {id, mode, status: running|done|failed, total, scored, failed, remaining,
--  error, warning, started_at, updated_at, finished_at}
alter table users add column if not exists score_run jsonb;
