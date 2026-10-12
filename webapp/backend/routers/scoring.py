from fastapi import APIRouter, HTTPException, Header
from pathlib import Path
import json
import os
import sys
from datetime import date
from cryptography.fernet import Fernet
from db.supabase_client import supabase

router = APIRouter(prefix="/score", tags=["scoring"])

FERNET_KEY = os.environ.get("FERNET_KEY", "")


def _decrypt_key(encrypted: str) -> str:
    f = Fernet(FERNET_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()


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
    token = authorization.removeprefix("Bearer ")
    auth_resp = supabase.auth.get_user(token)
    if not auth_resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = auth_resp.user.id

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

    gemini_key = _decrypt_key(user_row["gemini_api_key_encrypted"])
    profile_md = user_row["profile_md"]
    cv_text = user_row.get("cv_text") or ""

    config_row = getattr(supabase.table("score_configs").select("*").eq("user_id", user_id).maybe_single().execute(), "data", None) or {}

    # Determine jobs path - allow override via env for deploy
    jobs_path_env = os.environ.get("JOBS_PATH")
    if jobs_path_env:
        jobs_path = Path(jobs_path_env)
    else:
        jobs_path = Path(__file__).parent.parent.parent.parent / "new_jobs.json"

    if not jobs_path.exists():
        raise HTTPException(status_code=503, detail="new_jobs.json not found")

    all_jobs = json.loads(jobs_path.read_text(encoding="utf-8"))

    scored = supabase.table("scored_jobs").select("apply_url").eq("user_id", user_id).execute().data
    scored_urls = {r["apply_url"] for r in scored}

    location_terms = [t.lower() for t in config_row.get("location_terms", [])]
    skip_title = [t.lower() for t in config_row.get("skip_title_terms", [])]
    keep_title = [t.lower() for t in config_row.get("keep_title_terms", [])]
    skip_companies = [c.lower() for c in config_row.get("skip_companies", [])]
    skip_industries = [i.lower() for i in config_row.get("skip_industries", [])]

    pending = []
    for job in all_jobs:
        url = job.get("apply_url", "")
        if url in scored_urls:
            continue
        title_lower = job.get("title", "").lower()
        loc_lower = job.get("location", "").lower()
        company_lower = job.get("company", "").lower()
        desc_lower = job.get("description", "").lower()
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
    from matcher.gemini_scorer import score_jobs_batch

    gemini_client = genai.Client(api_key=gemini_key)
    results = score_jobs_batch(pending, profile_md, cv_text, gemini_client)

    profile_version = user_row.get("profile_version") or 1

    rows = []
    for job, result in zip(pending, results):
        if result is None:
            continue
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
            "description": job.get("description", ""),
        })

    if rows:
        supabase.table("scored_jobs").upsert(rows, on_conflict="user_id,apply_url").execute()

    supabase.table("users").update({
        "scoring_runs_this_week": user_row["scoring_runs_this_week"] + 1,
    }).eq("id", user_id).execute()

    return {"scored": len(rows), "skipped": len(pending) - len(rows)}
