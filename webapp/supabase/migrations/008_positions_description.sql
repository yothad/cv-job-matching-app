-- Store the job description in the shared positions catalog.
--
-- The webapp's "Score now" endpoint reads jobs from this table (new_jobs.json is
-- gitignored and never exists on Render) and the scorer needs the JD. Also lets
-- the Digest detail view fall back to the catalog for rows scored before 006.
-- Populated by scripts/sync_positions.py; the next collect run backfills it.
alter table positions add column if not exists description text;
