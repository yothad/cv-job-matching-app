from fastapi import APIRouter, BackgroundTasks, HTTPException, Header
from pydantic import BaseModel
from pathlib import Path
import os
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal
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
# Max jobs per run. Scoring runs in the background at roughly 80 jobs/min;
# anything over the cap stays pending for the next run.
RUN_CAP = int(os.environ.get("SCORE_RUN_CAP", "200"))
# A "running" run that hasn't written progress for this long died with its
# process (e.g. a Render restart) - treat it as interrupted, never as busy.
STALE_AFTER = timedelta(minutes=10)
IN_CHUNK = 100  # urls per PostgREST in.() filter


class ScoreRequest(BaseModel):
    # "new": score newly collected jobs. "rescore": re-score jobs that were
    # saved without a description now that the catalog has one.
    mode: Literal["new", "rescore"] = "new"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _effective_run(run: dict | None) -> dict | None:
    """The stored run, with a stale "running" one reported as interrupted."""
    if not run or run.get("status") != "running":
        return run
    try:
        updated = datetime.fromisoformat(run["updated_at"])
    except (KeyError, TypeError, ValueError):
        updated = None
    if updated is None or datetime.now(timezone.utc) - updated > STALE_AFTER:
        return {**run, "status": "failed", "error": "The scoring run was interrupted - start it again to continue"}
    return run


def _save_run(user_id: str, run: dict) -> None:
    """Persist progress. Never let a progress write kill the scoring itself
    (e.g. migration 010 not applied yet)."""
    try:
        supabase.table("users").update({"score_run": run}).eq("id", user_id).execute()
    except Exception as e:
        print(f"score_run progress write failed: {e}")


def _rescore_candidates(user_id: str) -> list[dict]:
    """Catalog rows (with description) for this user's jobs that were scored
    without one - e.g. scored before migration 008 / the first description sync."""
    urls: list[str] = []
    start, page = 0, 1000
    while True:
        chunk = (
            supabase.table("scored_jobs").select("apply_url").eq("user_id", user_id)
            .or_("description.is.null,description.eq.")
            .order("apply_url").range(start, start + page - 1).execute().data
        ) or []
        urls.extend(r["apply_url"] for r in chunk)
        if len(chunk) < page:
            break
        start += page
    jobs: list[dict] = []
    for i in range(0, len(urls), IN_CHUNK):
        jobs.extend(
            supabase.table("positions")
            .select("apply_url,company,title,location,first_seen,description")
            .in_("apply_url", urls[i:i + IN_CHUNK]).neq("description", "")
            .execute().data or []
        )
    return jobs


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


@router.get("/status")
def score_status(authorization: str = Header(...)):
    """Latest run's progress (polled by the digest) plus how many jobs can be
    re-scored with a description."""
    user_id = require_user(authorization)
    try:
        row = getattr(supabase.table("users").select("score_run").eq("id", user_id).maybe_single().execute(), "data", None) or {}
    except Exception:
        row = {}  # migration 010 not applied yet
    run = _effective_run(row.get("score_run"))
    rescore_available = 0
    if not run or run.get("status") != "running":
        try:
            rescore_available = len(_rescore_candidates(user_id))
        except Exception as e:
            print(f"rescore candidate count failed: {e}")
    return {"run": run, "rescore_available": rescore_available}


@router.post("/")
def trigger_score(
    background_tasks: BackgroundTasks,
    body: ScoreRequest | None = None,
    authorization: str = Header(...),
):
    user_id = require_user(authorization)
    mode = body.mode if body else "new"

    user_row = getattr(supabase.table("users").select("*").eq("id", user_id).maybe_single().execute(), "data", None)
    if not user_row:
        raise HTTPException(status_code=404, detail="User not found")

    current = _effective_run(user_row.get("score_run"))
    if current and current.get("status") == "running":
        raise HTTPException(status_code=409, detail="A scoring run is already in progress")

    user_row = _reset_if_new_week(user_row)
    # Re-scoring fixes rows we saved without a description - it's on us, so free.
    if mode == "new" and user_row["scoring_runs_this_week"] >= 2:
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

    if mode == "rescore":
        pending = _rescore_candidates(user_id)
        if not pending:
            return {"started": False, "message": "No jobs need re-scoring"}
    else:
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
            return {"started": False, "message": "No new jobs to score"}

    remaining = max(0, len(pending) - RUN_CAP)
    pending = pending[:RUN_CAP]
    run = {
        "id": str(uuid.uuid4()), "mode": mode, "status": "running",
        "total": len(pending), "scored": 0, "failed": 0, "remaining": remaining,
        "error": None, "warning": None,
        "started_at": _now(), "updated_at": _now(), "finished_at": None,
    }
    _save_run(user_id, run)
    background_tasks.add_task(
        _run_scoring, user_id, run, pending, profile_md, cv_text,
        gemini_key, user_row.get("profile_version") or 1, user_row["scoring_runs_this_week"],
    )
    return {"started": True, "run": run}


def _scorer(gemini_key: str):
    """(score_jobs_batch, QuotaExhaustedError, client) - a seam for tests."""
    # Ensure repo root is on the path so matcher package is importable
    repo_root = str(Path(__file__).parent.parent.parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    # score_jobs_batch signature: (jobs, profile_md, cv_md, client)
    # where client is a google.genai.Client instance
    from google import genai
    from matcher.gemini_scorer import score_jobs_batch, QuotaExhaustedError

    return score_jobs_batch, QuotaExhaustedError, genai.Client(api_key=gemini_key)


def _run_scoring(
    user_id: str, run: dict, pending: list[dict], profile_md: str, cv_text: str,
    gemini_key: str, profile_version: int, runs_used: int,
) -> None:
    """Background worker: score `pending`, saving each batch as it lands so the
    digest fills in while it runs and a crash keeps what was done."""
    try:
        _score_pending(user_id, run, pending, profile_md, cv_text, gemini_key, profile_version, runs_used)
    except Exception as e:
        run.update(status="failed", error=_safe_error([str(e)], gemini_key), finished_at=_now(), updated_at=_now())
        _save_run(user_id, run)


def _score_pending(
    user_id: str, run: dict, pending: list[dict], profile_md: str, cv_text: str,
    gemini_key: str, profile_version: int, runs_used: int,
) -> None:
    score_jobs_batch, QuotaExhaustedError, gemini_client = _scorer(gemini_key)
    rescore = run["mode"] == "rescore"

    # Same batch size as the CLI (score.py) - one prompt per BATCH_SIZE jobs.
    scored = 0
    errors: list[str] = []
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i:i + BATCH_SIZE]
        try:
            results = score_jobs_batch(batch, profile_md, cv_text, gemini_client)
        except QuotaExhaustedError as e:
            errors.append(str(e))
            break
        rows = []
        for job, result in zip(batch, results):
            # Scorer errors come back as score-0 rows flagged "scorer-error".
            # Never persist those: they'd be deduped forever as "scored".
            if result is None or "scorer-error" in (result.get("flags") or []):
                if result:
                    errors.append(result.get("reasoning", ""))
                continue
            row = {
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
            }
            if rescore:
                row["scored_at"] = _now()  # upsert keeps the old stamp otherwise
            rows.append(row)
        if rows:
            # Upsert only touches these columns, so `applied` survives a re-score.
            supabase.table("scored_jobs").upsert(rows, on_conflict="user_id,apply_url").execute()
        scored += len(rows)
        run.update(scored=scored, failed=i + len(batch) - scored, updated_at=_now())
        _save_run(user_id, run)
        if not rows:
            break  # the whole batch failed (bad key / model unavailable) - stop burning calls

    stopped_early = scored + run["failed"] < len(pending)
    if stopped_early:
        run["failed"] = len(pending) - scored
    run.update(finished_at=_now(), updated_at=_now())
    if not scored:
        run.update(status="failed", error=f"Gemini scoring failed: {_safe_error(errors, gemini_key)}")
        _save_run(user_id, run)
        return  # nothing scored - don't consume a weekly run

    # A weekly run is used when a "new" run clears the backlog; capped runs
    # (remaining > 0) can be continued for free.
    if not rescore and run["remaining"] == 0:
        supabase.table("users").update({"scoring_runs_this_week": runs_used + 1}).eq("id", user_id).execute()
    run["status"] = "done"
    if errors:
        run["warning"] = f"Some jobs were not scored: {_safe_error(errors, gemini_key)}"
    _save_run(user_id, run)
