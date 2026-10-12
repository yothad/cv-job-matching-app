"""Read the shared `positions` catalog (one copy for all users).

The pipeline (collect_jobs.py -> scripts/sync_positions.py) mirrors every open
role into this table, so it is the backend's source of truth for "the market".
new_jobs.json is gitignored and never exists on Render - don't read it here.
"""
from db.supabase_client import supabase

PAGE = 1000  # PostgREST caps responses at 1000 rows per request
BASE_COLUMNS = "apply_url,company,title,location,first_seen"


def _fetch_all(columns: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        chunk = (
            supabase.table("positions")
            .select(columns)
            .order("apply_url")  # stable order so pages don't overlap/skip
            .range(start, start + PAGE - 1)
            .execute()
            .data
        ) or []
        rows.extend(chunk)
        if len(chunk) < PAGE:
            return rows
        start += PAGE


def fetch_positions(with_description: bool = False) -> list[dict]:
    """All catalog rows. With with_description, also pull `description`
    (migration 008); if that column isn't there yet, fall back to rows without
    it rather than failing."""
    if with_description:
        try:
            return _fetch_all(BASE_COLUMNS + ",description")
        except Exception as e:  # postgrest APIError: column does not exist
            if "description" not in str(e):
                raise
            print("positions.description missing - apply migration 008; scoring without descriptions")
    return _fetch_all(BASE_COLUMNS)


def latest_sync_time() -> str | None:
    """ISO timestamp of the most recent catalog sync (max synced_at), or None."""
    rows = (
        supabase.table("positions")
        .select("synced_at")
        .order("synced_at", desc=True)
        .limit(1)
        .execute()
        .data
    )
    return rows[0]["synced_at"] if rows else None
