"""A user's saved Settings filters (score_configs) and the one rule that applies them.

Used by scoring (which catalog jobs to score) and by the job list (which already
scored jobs fall outside the filters, so the Digest can hide them).
"""
from db.supabase_client import supabase


def load_filters(user_id: str) -> dict:
    """The user's score_configs row, or {}. Newest wins: score_configs.user_id isn't
    unique, so a racing first save can leave two rows (maybe_single() would 500)."""
    rows = getattr(supabase.table("score_configs").select("*").eq("user_id", user_id)
                   .order("updated_at", desc=True).limit(1).execute(), "data", None)
    return rows[0] if rows else {}


def _terms(cfg: dict, key: str) -> list[str]:
    return [t.strip().lower() for t in (cfg.get(key) or []) if t and t.strip()]


def passes_filters(job: dict, cfg: dict) -> bool:
    """True if the job matches the saved filters. Any location term may match;
    skip-industries also checks the description when the job carries one."""
    title = (job.get("title") or "").lower()
    location = (job.get("location") or "").lower()
    company = (job.get("company") or "").lower()
    desc = (job.get("description") or "").lower()
    location_terms = _terms(cfg, "location_terms")
    keep_title = _terms(cfg, "keep_title_terms")
    if location_terms and not any(t in location for t in location_terms):
        return False
    if any(t in title for t in _terms(cfg, "skip_title_terms")):
        return False
    if keep_title and not any(t in title for t in keep_title):
        return False
    if any(c in company for c in _terms(cfg, "skip_companies")):
        return False
    if any(i in desc or i in company for i in _terms(cfg, "skip_industries")):
        return False
    return True
