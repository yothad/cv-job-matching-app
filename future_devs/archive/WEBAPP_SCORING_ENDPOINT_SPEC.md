# Spec: webapp_scoring_endpoint

**Slug:** webapp_scoring_endpoint  
**Epic:** Web App v1  
**Effort:** M  
**Depends on:** webapp_scaffold ✅

---

## Goal

Add a FastAPI endpoint that triggers scoring for an authenticated user. It reads the user's profile, CV, Gemini API key, and filters from Supabase; loads `new_jobs.json`; filters out already-scored jobs; calls the existing scoring logic; and writes results to the `scored_jobs` table. Rate-limited to 2 runs per user per week.

---

## Key design decisions

- **Reuse existing scoring code**: import from `matcher/gemini_scorer.py` directly. Do not duplicate logic.
- **Synchronous for now**: scoring runs inline (FastAPI background task is acceptable but not required for v1 — keep it simple).
- **Gemini key**: stored encrypted with Fernet. Decrypt on the fly, never log it.
- **Rate limit**: enforced in Supabase `users` table via `scoring_runs_this_week` + `last_week_reset`.
- **Deduplication**: skip any `apply_url` already in `scored_jobs` for this user.

---

## Files to create / modify

### `webapp/backend/routers/scoring.py`

```python
from fastapi import APIRouter, HTTPException, Header
from pathlib import Path
import json
import os
from datetime import date, timedelta
from cryptography.fernet import Fernet
from db.supabase_client import supabase

router = APIRouter(prefix="/score", tags=["scoring"])

JOBS_PATH = Path(__file__).parent.parent.parent.parent / "new_jobs.json"
FERNET_KEY = os.environ["FERNET_KEY"]

MAX_RUNS_PER_WEEK = 2


def _decrypt_key(encrypted: str) -> str:
    f = Fernet(FERNET_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()


def _reset_if_new_week(user: dict) -> dict:
    last_reset = date.fromisoformat(user["last_week_reset"])
    today = date.today()
    # reset counter if we've crossed into a new Monday-anchored week
    if (today - last_reset).days >= 7 or today.isocalendar()[1] != last_reset.isocalendar()[1]:
        supabase.table("users").update({
            "scoring_runs_this_week": 0,
            "last_week_reset": today.isoformat(),
        }).eq("id", user["id"]).execute()
        user["scoring_runs_this_week"] = 0
    return user


@router.post("/")
def trigger_score(authorization: str = Header(...)):
    # Validate JWT and get user_id
    token = authorization.removeprefix("Bearer ")
    auth_resp = supabase.auth.get_user(token)
    if not auth_resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = auth_resp.user.id

    # Fetch user row
    user_row = supabase.table("users").select("*").eq("id", user_id).single().execute().data
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    # Rate limit check
    user_row = _reset_if_new_week(user_row)
    if user_row["scoring_runs_this_week"] >= MAX_RUNS_PER_WEEK:
        raise HTTPException(status_code=429, detail="Weekly scoring limit reached (2 runs/week)")

    if not user_row.get("gemini_api_key_encrypted"):
        raise HTTPException(status_code=400, detail="No Gemini API key configured")
    if not user_row.get("profile_md"):
        raise HTTPException(status_code=400, detail="No profile configured")

    gemini_key = _decrypt_key(user_row["gemini_api_key_encrypted"])
    profile_md = user_row["profile_md"]
    cv_text = user_row.get("cv_text", "")

    # Load filters
    config_row = supabase.table("score_configs").select("*").eq("user_id", user_id).maybe_single().execute().data or {}

    # Load new_jobs.json
    if not JOBS_PATH.exists():
        raise HTTPException(status_code=503, detail="new_jobs.json not found — collection hasn't run yet")
    all_jobs = json.loads(JOBS_PATH.read_text(encoding="utf-8"))

    # Get already-scored apply_urls for this user
    scored = supabase.table("scored_jobs").select("apply_url").eq("user_id", user_id).execute().data
    scored_urls = {r["apply_url"] for r in scored}

    # Filter jobs
    location_terms = [t.lower() for t in config_row.get("location_terms", [])]
    skip_title = [t.lower() for t in config_row.get("skip_title_terms", [])]
    keep_title = [t.lower() for t in config_row.get("keep_title_terms", [])]
    skip_companies = [c.lower() for c in config_row.get("skip_companies", [])]
    skip_industries = [i.lower() for i in config_row.get("skip_industries", [])]

    pending = []
    for job in all_jobs:
        if job.get("apply_url") in scored_urls:
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

    # Import and run scoring
    import sys
    repo_root = str(Path(__file__).parent.parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from matcher.gemini_scorer import score_jobs_batch

    results = score_jobs_batch(pending, profile_md, cv_text, gemini_key)

    # Write to scored_jobs table
    rows = []
    for job, result in zip(pending, results):
        if result is None:
            continue
        rows.append({
            "user_id": user_id,
            "apply_url": job["apply_url"],
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "location": job.get("location", ""),
            "score": result.get("score"),
            "reasoning": result.get("reasoning", ""),
            "flags": result.get("flags", []),
        })

    if rows:
        supabase.table("scored_jobs").upsert(rows, on_conflict="user_id,apply_url").execute()

    # Increment run counter
    supabase.table("users").update({
        "scoring_runs_this_week": user_row["scoring_runs_this_week"] + 1,
    }).eq("id", user_id).execute()

    return {"scored": len(rows), "skipped": len(pending) - len(rows)}
```

### `webapp/backend/main.py`

Add the scoring router:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers.scoring import router as scoring_router

app = FastAPI(title="CareerWatch API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scoring_router)

@app.get("/health")
def health():
    return {"status": "ok"}
```

### Check `matcher/gemini_scorer.py`

Read the existing file and verify there is a `score_jobs_batch` function (or equivalent). If the function name is different, adjust the import in `routers/scoring.py` to match what exists. Do not modify `matcher/gemini_scorer.py`.

---

## Touches

- `webapp/backend/routers/scoring.py` (new)
- `webapp/backend/main.py` (add router import)

---

## Exit gate

```bash
# Check files exist
ls C:/repos/cv-job-matching-app/webapp/backend/routers/scoring.py

# Backend imports without errors (requires SUPABASE_URL etc but at least checks syntax)
cd C:/repos/cv-job-matching-app/webapp/backend && python -c "import ast; ast.parse(open('routers/scoring.py').read()); print('syntax OK')"
cd C:/repos/cv-job-matching-app/webapp/backend && python -c "import ast; ast.parse(open('main.py').read()); print('syntax OK')"

# Verify scoring router is registered in main.py
grep "scoring_router" C:/repos/cv-job-matching-app/webapp/backend/main.py

# Python pipeline unaffected
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
