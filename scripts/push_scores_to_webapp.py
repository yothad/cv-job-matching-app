"""
Copy the pipeline's scores into a webapp user's digest (Supabase scored_jobs).

score.py scores every new job for each profile under profiles/ with the repo's
own key; the webapp keeps a separate per-user scored_jobs table that is
otherwise filled only by that user's own scoring runs. For profiles mapped to a
webapp account, this pushes the pipeline's scores across so they don't have to
be scored (and paid for) twice. Runs in CI after score.py and before the
webapp's auto-score, which then skips everything pushed here.

What gets pushed, per mapped profile:
  - the latest non-error score per apply_url from profiles/<name>/all_scores.jsonl
  - only for jobs still in the live `positions` catalog
  - only where the user has no row yet, or has one scored without a description
    (the pipeline's score did read the description, so it's the better one)
Upserts write only the scoring columns, so `applied` and `status` survive.
The pipeline applies its own filters (profiles/<name>/score_config.json), not
the user's webapp filters.

Env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  - required (else skip)
  WEBAPP_PROFILE_USERS  - "profile=email[,profile=email]"; unset -> skip.
                          A secret, so no account email lives in the repo.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).parent.parent
PROFILES_DIR = REPO_ROOT / "profiles"
PAGE = 1000
BATCH_SIZE = 250
TIMEOUT = 60.0


def parse_mapping(raw: str) -> dict[str, str]:
    out = {}
    for part in raw.split(","):
        name, _, email = part.strip().partition("=")
        if name.strip() and email.strip():
            out[name.strip()] = email.strip().lower()
    return out


def latest_scores(jsonl_path: Path) -> dict[str, dict]:
    """apply_url -> last successful score record (later lines win)."""
    best: dict[str, dict] = {}
    if not jsonl_path.exists():
        return best
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        url = (rec.get("apply_url") or "").strip()
        if url and "scorer-error" not in (rec.get("flags") or []) and rec.get("score") is not None:
            best[url] = rec
    return best


def _get_all(client: httpx.Client, url: str, headers: dict, params: dict) -> list[dict]:
    rows, offset = [], 0
    while True:
        resp = client.get(url, params={**params, "limit": PAGE, "offset": offset}, headers=headers)
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < PAGE:
            return rows
        offset += PAGE


def build_rows(user: dict, scores: dict[str, dict], live: set[str], existing: dict[str, str], now: str) -> list[dict]:
    """existing: apply_url -> current description ('' when scored without one)."""
    rows = []
    for url, rec in scores.items():
        if url not in live:
            continue
        if url in existing and existing[url]:
            continue  # already scored with a description - leave the user's score alone
        rows.append({
            "user_id": user["id"],
            "apply_url": url,
            "company": rec.get("company") or "",
            "title": rec.get("title") or "",
            "location": rec.get("location") or "",
            "score": int(rec["score"]),
            "reasoning": rec.get("reasoning") or "",
            "flags": rec.get("flags") or [],
            "profile_version": user.get("profile_version") or 1,
            "first_seen": rec.get("first_seen"),
            "description": rec.get("description") or "",
            "scored_at": now,
        })
    return rows


def main() -> None:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    mapping = parse_mapping(os.environ.get("WEBAPP_PROFILE_USERS", ""))
    if not url or not key or not mapping:
        print("SUPABASE creds or WEBAPP_PROFILE_USERS not set - skipping score push")
        return
    base = f"{url.rstrip('/')}/rest/v1"
    headers = {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    now = datetime.now(timezone.utc).isoformat()

    with httpx.Client(timeout=TIMEOUT) as client:
        live = {r["apply_url"] for r in _get_all(client, f"{base}/positions", headers, {"select": "apply_url", "order": "apply_url"})}
        for name, email in mapping.items():
            scores = latest_scores(PROFILES_DIR / name / "all_scores.jsonl")
            resp = client.get(f"{base}/users", params={"select": "id,profile_version", "email": f"eq.{email}"}, headers=headers)
            resp.raise_for_status()
            if not resp.json():
                print(f"[{name}] no webapp account for the mapped email - skipping")
                continue
            user = resp.json()[0]
            existing = {
                r["apply_url"]: (r.get("description") or "")
                for r in _get_all(client, f"{base}/scored_jobs", headers,
                                  {"select": "apply_url,description", "user_id": f"eq.{user['id']}", "order": "apply_url"})
            }
            rows = build_rows(user, scores, live, existing, now)
            for i in range(0, len(rows), BATCH_SIZE):
                r = client.post(
                    f"{base}/scored_jobs", params={"on_conflict": "user_id,apply_url"},
                    headers={**headers, "Prefer": "resolution=merge-duplicates,return=minimal"},
                    content=json.dumps(rows[i:i + BATCH_SIZE]),
                )
                r.raise_for_status()
            upgraded = sum(1 for r in rows if r["apply_url"] in existing)
            print(f"[{name}] pushed {len(rows)} scores to the webapp ({len(rows) - upgraded} new, {upgraded} replaced description-less)")


if __name__ == "__main__":
    main()
