"""
Sync the shared `positions` catalog in Supabase from local new_jobs.json.

The webapp's Positions page shows the full market of open roles to EVERY user
(one shared copy), unlike the per-user scored_jobs table. This script pushes the
current new_jobs.json snapshot (incl. `description`, migration 008 - skipped
with a warning if the column isn't there yet) into the global `positions` table:

  1. Upsert every current role, stamping this run's `synced_at`.
  2. Delete any row left with an older `synced_at` (i.e. no longer in the
     snapshot), so the table always mirrors the latest live set.

Runs automatically after collect_jobs.py in CI; safe to run locally too.

Uses httpx against Supabase's PostgREST API (httpx is already a pipeline
dependency) so the core pipeline env needs no new packages. No-op with a clean
exit if the SUPABASE creds are absent, keeping collect/score independently
runnable.

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  - required to do anything (else skip)
  NEW_JOBS_PATH                            - optional override for new_jobs.json
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).parent.parent
NEW_JOBS_PATH = Path(os.environ.get("NEW_JOBS_PATH") or REPO_ROOT / "new_jobs.json")
BATCH_SIZE = 250  # rows now carry multi-KB descriptions
TIMEOUT = 60.0


def _upsert(client: httpx.Client, base: str, auth_headers: dict, batch: list[dict]) -> httpx.Response:
    return client.post(
        base,
        params={"on_conflict": "apply_url"},
        headers={**auth_headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
        content=json.dumps(batch),
    )


def _missing_description_column(resp: httpx.Response) -> bool:
    """PostgREST answers 400 (PGRST204 "Could not find the 'description'
    column") when the payload has a column the table lacks."""
    return resp.status_code == 400 and "description" in resp.text


def main() -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not set - skipping positions sync")
        return

    if not NEW_JOBS_PATH.exists():
        sys.exit(f"{NEW_JOBS_PATH} not found - run collect_jobs.py first")

    jobs = json.loads(NEW_JOBS_PATH.read_text(encoding="utf-8"))
    run_ts = datetime.now(timezone.utc).isoformat()

    # Key rows by apply_url (the natural unique key / PK). Positions without an
    # apply URL can't be applied to and would collide on the PK, so skip them.
    rows_by_url: dict[str, dict] = {}
    for j in jobs:
        u = (j.get("apply_url") or "").strip()
        if not u:
            continue
        rows_by_url[u] = {
            "apply_url": u,
            "company": j.get("company") or "",
            "title": j.get("title") or "",
            "location": j.get("location") or "",
            "description": j.get("description") or "",
            "first_seen": j.get("first_seen"),
            "synced_at": run_ts,
        }
    rows = list(rows_by_url.values())
    skipped = len(jobs) - len(rows)
    print(f"Syncing {len(rows)} positions ({skipped} skipped for empty apply_url)...")

    base = f"{url.rstrip('/')}/rest/v1/positions"
    auth_headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=TIMEOUT) as client:
        # Upsert current snapshot in batches. merge-duplicates on the apply_url
        # PK refreshes existing rows (incl. synced_at) and inserts new ones.
        with_description = True
        for i in range(0, len(rows), BATCH_SIZE):
            batch = rows[i:i + BATCH_SIZE]
            if not with_description:
                batch = [{k: v for k, v in r.items() if k != "description"} for r in batch]
            resp = _upsert(client, base, auth_headers, batch)
            if with_description and _missing_description_column(resp):
                # Migration 008 not applied yet - keep syncing without the JD
                # rather than failing the whole catalog refresh.
                print("  WARNING: positions.description column missing - apply "
                      "webapp/supabase/migrations/008_positions_description.sql. "
                      "Syncing without descriptions.")
                with_description = False
                batch = [{k: v for k, v in r.items() if k != "description"} for r in batch]
                resp = _upsert(client, base, auth_headers, batch)
            resp.raise_for_status()
            print(f"  {min(i + BATCH_SIZE, len(rows))}/{len(rows)} upserted")

        # Prune positions no longer in the live snapshot (older synced_at).
        resp = client.delete(
            base,
            params={"synced_at": f"lt.{run_ts}"},
            headers={**auth_headers, "Prefer": "return=representation"},
        )
        resp.raise_for_status()
        pruned = len(resp.json()) if resp.content else 0

    print(f"Pruned {pruned} stale positions. Catalog now reflects {len(rows)} live roles.")


if __name__ == "__main__":
    main()
