from fastapi import APIRouter, HTTPException, Header
import os
import sys
from pathlib import Path
from cryptography.fernet import Fernet
from db.supabase_client import supabase

router = APIRouter(prefix="/gaps", tags=["gaps"])

FERNET_KEY = os.environ.get("FERNET_KEY", "")

# In-memory cache: user_id -> {profile_version, cv_hash, result}
_profile_cv_cache: dict = {}
# In-memory cache for positions: user_id -> {cache_key, result}
_positions_cache: dict = {}


def _get_user_and_data(authorization: str):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = resp.user.id
    row = getattr(supabase.table("users").select(
        "profile_md,cv_text,profile_version,gemini_api_key_encrypted"
    ).eq("id", user_id).maybe_single().execute(), "data", None)
    return user_id, row or {}


def _decrypt_key(encrypted: str) -> str:
    f = Fernet(FERNET_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()


def _gemini_client(row: dict):
    enc = row.get("gemini_api_key_encrypted")
    if not enc:
        raise HTTPException(status_code=400, detail="No Gemini API key configured")
    key = _decrypt_key(enc)
    repo_root = str(Path(__file__).parent.parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from google import genai
    return genai.Client(api_key=key)


@router.get("/profile-cv")
def get_profile_cv_gap(authorization: str = Header(...)):
    user_id, row = _get_user_and_data(authorization)
    profile_md = row.get("profile_md") or ""
    cv_md = row.get("cv_text") or ""

    if not profile_md and not cv_md:
        return {"empty": True, "reason": "No profile or CV on file"}
    if not profile_md:
        return {"empty": True, "reason": "No profile on file - add one in Settings"}
    if not cv_md:
        return {"empty": True, "reason": "No CV on file - add one in Settings"}

    profile_version = row.get("profile_version") or 1
    cv_hash = str(hash(cv_md))
    cache_key = (profile_version, cv_hash)

    cached = _profile_cv_cache.get(user_id)
    if cached and cached.get("cache_key") == cache_key:
        return cached["result"]

    client = _gemini_client(row)
    repo_root = str(Path(__file__).parent.parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from matcher.gap_analyzer import analyze_profile_cv_gap
    result = analyze_profile_cv_gap(profile_md, cv_md, client)
    _profile_cv_cache[user_id] = {"cache_key": cache_key, "result": result}
    return result


@router.get("/positions")
def get_position_gaps(authorization: str = Header(...), min_score: int = 6):
    user_id, row = _get_user_and_data(authorization)
    profile_md = row.get("profile_md") or ""
    cv_md = row.get("cv_text") or ""
    profile_version = row.get("profile_version") or 1

    jobs_rows = (
        supabase.table("scored_jobs")
        .select("apply_url,company,title,location,score,description,reasoning,flags")
        .eq("user_id", user_id)
        .gte("score", min_score)
        .order("score", desc=True)
        .execute()
        .data
    )

    if not jobs_rows:
        return []

    cv_hash = str(hash(cv_md))
    # Cache key includes profile version, cv hash, and set of apply_urls
    job_urls = tuple(sorted(j["apply_url"] for j in jobs_rows))
    cache_key = (profile_version, cv_hash, job_urls)

    cached = _positions_cache.get(user_id)
    if cached and cached.get("cache_key") == cache_key:
        return cached["result"]

    client = _gemini_client(row)
    repo_root = str(Path(__file__).parent.parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from matcher.gap_analyzer import analyze_position_cv_gap, analyze_position_profile_gap

    results = []
    for job in jobs_rows:
        try:
            cv_gap = analyze_position_cv_gap(job, cv_md, client) if cv_md else {
                "match_strength": "unknown", "strengths": [], "gaps": [],
                "job_id": job.get("apply_url", ""), "company": job.get("company", ""),
                "title": job.get("title", ""), "score": job.get("score", 0),
            }
            profile_gap = analyze_position_profile_gap(job, profile_md, client) if profile_md else {
                "job_id": job.get("apply_url", ""), "alignment": "unknown", "divergences": [],
            }
            results.append({
                "job_id": job.get("apply_url", ""),
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "location": job.get("location", ""),
                "score": job.get("score", 0),
                "cv_gap": cv_gap,
                "profile_gap": profile_gap,
            })
        except Exception as e:
            results.append({
                "job_id": job.get("apply_url", ""),
                "company": job.get("company", ""),
                "title": job.get("title", ""),
                "location": job.get("location", ""),
                "score": job.get("score", 0),
                "error": str(e),
            })

    results.sort(key=lambda x: (
        {"strong": 0, "partial": 1, "weak": 2, "unknown": 3}.get(x.get("cv_gap", {}).get("match_strength", "unknown"), 3),
        -(x.get("score") or 0),
    ))

    _positions_cache[user_id] = {"cache_key": cache_key, "result": results}
    return results
