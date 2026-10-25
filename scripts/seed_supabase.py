"""
One-off script: seed Supabase users + scored_jobs from local profiles/yotam/scored_jobs.json.
Run once to populate the webapp after a local scoring session.
"""
import json
import os
import sys
from pathlib import Path
from supabase import create_client

SUPABASE_URL = "https://aeaydmcgczwyhvnttmsu.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

USER_ID = "dae764b3-e842-496c-8825-8bc97321c57c"
USER_EMAIL = "yothad@gmail.com"

REPO_ROOT = Path(__file__).parent.parent
SCORED_JOBS_PATH = REPO_ROOT / "profiles" / "yotam" / "scored_jobs.json"


def main():
    if not SUPABASE_KEY:
        sys.exit("Set SUPABASE_SERVICE_ROLE_KEY in env")

    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Upsert user row (id must match auth.uid)
    print(f"Upserting user {USER_EMAIL} ({USER_ID})...")
    sb.table("users").upsert({
        "id": USER_ID,
        "email": USER_EMAIL,
        "scoring_runs_this_week": 0,
    }, on_conflict="id").execute()
    print("  done")

    # Load local scored jobs
    jobs = json.loads(SCORED_JOBS_PATH.read_text(encoding="utf-8"))
    print(f"Importing {len(jobs)} scored jobs...")

    rows = []
    for j in jobs:
        rows.append({
            "user_id": USER_ID,
            "apply_url": j.get("apply_url", ""),
            "company": j.get("company", ""),
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "score": j.get("score"),
            "reasoning": j.get("reasoning", ""),
            "flags": j.get("flags", []),
            "scored_at": j.get("scored_at"),
            "status": j.get("status") or "open",
        })

    # Upsert in batches of 100
    batch_size = 100
    inserted = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        sb.table("scored_jobs").upsert(batch, on_conflict="user_id,apply_url").execute()
        inserted += len(batch)
        print(f"  {inserted}/{len(rows)} upserted")

    print("Done.")


if __name__ == "__main__":
    main()
