-- scored_jobs.first_seen: written by POST /score and read by GET /jobs.
-- Added by hand in June (POSITION_FIRST_SEEN, commit 30098ac) but never applied to
-- production; both endpoints 500'd with "column scored_jobs.first_seen does not exist"
-- until it was applied on 2026-10-13.
alter table scored_jobs add column if not exists first_seen date;

notify pgrst, 'reload schema';
