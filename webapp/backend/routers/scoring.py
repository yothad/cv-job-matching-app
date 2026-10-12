from fastapi import APIRouter, HTTPException, Header
from pathlib import Path
import os
import sys
from datetime import date
from cryptography.fernet import Fernet
from auth import require_user
from db.positions import fetch_positions
from db.supabase_client import supabase

router = APIRouter(prefix="/score", tags=["scoring"])

FERNET_KEY = os.environ.get("FERNET_KEY", "")


def _decrypt_key(encrypted: str) -> str:
    f = Fernet(FERNET_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()


BATCH_SIZE = int(os.environ.get("GEMINI_BATCH_SIZE", "10"))  # mirrors score.py


def _scored_urls(user_id: str) -> set[str]:
    """apply_urls this user already has scored (paginated - PostgREST caps at 1000)."""
    urls: set[str] = set()
    start, page = 0, 1000
    while True:
        chunk = (
            supabase.table("scored_jobs").select("apply_url").eq("user_id", user_id)
            .order("apply_url").range(start, start + page - 1).execute().data
        ) or []
        urls.update(r["apply_url"] for r in chunk)
        if len(chunk) < page:
            return urls
        start += page


def _safe_error(errors: list[str], secret: str) -> str:
    """Last scorer error, trimmed for the UI, with the API key scrubbed."""
    msg = next((e for e in reversed(errors) if e), "unknown error")
    msg = msg.removeprefix("scorer error: ")
    if secret:
        msg = msg.replace(secret, "[key]")
    return msg[:300]


def _reset_if_new_week(user: dict) -> dict:
    last_reset = date.fromisoformat(str(user["last_week_reset"]))
    today = date.today()
    if (today - last_reset).days >= 7 or today.isocalendar()[1] != last_reset.isocalendar()[1]:
        supabase.table("users").update({
            "scoring_runs_this_week": 0,
            "last_week_reset": today.isoformat(),
        }).eq("id", user["id"]).execute()
        user = dict(user)
        user["scoring_runs_this_week"] = 0
    return user


@router.post("/")
def trigger_score(authorization: str = Header(...)):
    user_id = require_user(authorization)

    user_row = getattr(supabase.table("users").select("*").eq("id", user_id).maybe_single().execute(), "data", None)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    user_row = _reset_if_new_week(user_row)
    if user_row["scoring_runs_this_week"] >= 2:
        raise HTTPException(status_code=429, detail="Weekly scoring limit reached (2 runs/week)")

    if not user_row.get("gemini_api_key_encrypted"):
        raise HTTPException(status_code=400, detail="No Gemini API key configured")
    if not user_row.get("profile_md"):
        raise HTTPException(status_code=400, detail="No profile configured")

    try:
        gemini_key = _decrypt_key(user_row["gemini_api_key_encrypted"])
    except Exception:
        raise HTTPException(status_code=400, detail="Your stored API key can't be read - please re-save it in Settings")
    profile_md = user_row["profile_md"]
    cv_text = user_row.get("cv_text") or ""

    config_row = getattr(supabase.table("score_configs").select("*").eq("user_id", user_id).maybe_single().execute(), "data", None) or {}

    # Jobs come from the shared positions catalog the pipeline syncs to
    # Supabase. new_jobs.json is gitignored and never exists on Render.
    all_jobs = fetch_positions(with_description=True)
    if not all_jobs:
        raise HTTPException(status_code=503, detail="The jobs catalog is empty right now - try again after the next collection run")

    scored_urls = _scored_urls(user_id)

    location_terms = [t.lower() for t in (config_row.get("location_terms") or [])]
    skip_title = [t.lower() for t in (config_row.get("skip_title_terms") or [])]
    keep_title = [t.lower() for t in (config_row.get("keep_title_terms") or [])]
    skip_companies = [c.lower() for c in (config_row.get("skip_companies") or [])]
    skip_industries = [i.lower() for i in (config_row.get("skip_industries") or [])]

    pending = []
    for job in all_jobs:
        url = job.get("apply_url", "")
        if url in scored_urls:
            continue
        title_lower = (job.get("title") or "").lower()
        loc_lower = (job.get("location") or "").lower()
        company_lower = (job.get("company") or "").lower()
        desc_lower = (job.get("description") or "").lower()
        if location_terms and not any(t in loc_lower for t in location_terms):
            continue
        if any(t in title_lower for t in skip_title):
            continue
        if keep_title and not any(t in title_lower for t in keep_title):
            continue
        if any(c in company_lower for c in skip_companies):
            continue
        if any(i in desc_lower or i in company_lower for i in skip_industries):
            continue
        pending.append(job)

    if not pending:
        return {"scored": 0, "message": "No new jobs to score"}

    # Ensure repo root is on the path so matcher package is importable
    repo_root = str(Path(__file__).parent.parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # score_jobs_batch signature: (jobs, profile_md, cv_md, client)
    # where client is a google.genai.Client instance
    from google import genai
    from matcher.gemini_scorer import score_jobs_batch, QuotaExhaustedError

    gemini_client = genai.Client(api_key=gemini_key)
    profile_version = user_row.get("profile_version") or 1

    # Same batch size as the CLI (score.py) - one prompt per BATCH_SIZE jobs.
    rows = []
    errors: list[str] = []
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        try:
            results = score_jobs_batch(batch, profile_md, cv_text, gemini_client)
        except QuotaExhaustedError as e:
            errors.append(str(e))
            break
        batch_ok = False
        for job, result in zip(batch, results):
            # Scorer errors come back as score-0 rows flagged "scorer-error".
            # Never persist those: they'd be deduped forever as "scored".
            if result is None or "scorer-error" in (result.get("flags") or []):
                if result:
                    errors.append(result.get("reasoning", ""))
                continue
            batch_ok = True
            rows.append({
                "user_id": user_id,
                "apply_url": job.get("apply_url", ""),
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "location": job.get("location", ""),
                "score": result.get("score"),
                "reasoning": result.get("reasoning", ""),
                "flags": result.get("flags", []),
                "profile_version": profile_version,
                "first_seen": job.get("first_seen"),
                "description": job.get("description") or "",
            })
        if not batch_ok:
            break  # the whole batch failed (bad key / model unavailable) - stop burning calls

    if rows:
        supabase.table("scored_jobs").upsert(rows, on_conflict="user_id,apply_url").execute()

    if not rows:
        # Nothing scored - don't consume one of the user's weekly runs.
        raise HTTPException(status_code=502, detail=f"Gemini scoring failed: {_safe_error(errors, gemini_key)}")

    supabase.table("users").update({
        "scoring_runs_this_week": user_row["scoring_runs_this_week"] + 1,
    }).eq("id", user_id).execute()

    result = {"scored": len(rows), "skipped": len(pending) - len(rows)}
    if errors:
        result["warning"] = f"Some jobs were not scored: {_safe_error(errors, gemini_key)}"
    return result
