-- One filters row per user. Without this, upsert(on_conflict="user_id") fails (42P10)
-- and a racing first save can insert two rows (readers take the newest).
create unique index if not exists score_configs_user_id_key on score_configs(user_id);
