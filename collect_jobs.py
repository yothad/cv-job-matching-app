#!/usr/bin/env python3
"""
Daily runner: read companies.json, hit ATS APIs, write new_jobs.json.
No VC knowledge, no discovery logic. Only reads cached ats/ats_params.

Run: uv run python collect_jobs.py
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ats import ATS_PULLERS

COMPANIES_FILE = Path("companies.json")
JOBS_FILE = Path("new_jobs.json")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_companies() -> list[dict]:
    if not COMPANIES_FILE.exists():
        raise FileNotFoundError(f"{COMPANIES_FILE} not found — run refresh_companies.py first")
    with COMPANIES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _write_json_atomic(path: Path, obj) -> None:
    """Write-then-rename so a crash mid-dump never leaves a truncated state file."""
    tmp = path.with_name(path.name + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def save_companies(entries: list[dict]) -> None:
    _write_json_atomic(COMPANIES_FILE, entries)


LIVE_POSITIONS_FILE = Path("live_positions.json")


def _load_first_seen_lookup() -> dict[str, str]:
    """Return {apply_url: first_seen} from the existing new_jobs.json for carry-forward."""
    if not JOBS_FILE.exists():
        return {}
    try:
        with JOBS_FILE.open(encoding="utf-8") as f:
            jobs = json.load(f)
        return {
            j["apply_url"]: j["first_seen"]
            for j in jobs
            if j.get("apply_url") and j.get("first_seen")
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def collect():
    companies = load_companies()
    first_seen_lookup = _load_first_seen_lookup()
    all_jobs = []
    companies_with_jobs = 0
    successful_companies: list[str] = []
    live_apply_urls: list[str] = []

    for entry in companies:
        name = entry["name"]
        ats = entry.get("ats", "unknown")
        ats_params = entry.get("ats_params") or {}

        if entry.get("status") == "acquired":
            print(f"  {name}: acquired, skipping")
            continue

        if ats == "unknown" or not ats_params:
            print(f"  {name}: no ATS cached, skipping")
            continue

        puller = ATS_PULLERS.get(ats)
        if not puller:
            print(f"  {name}: ATS '{ats}' has no puller in this version, skipping")
            continue

        try:
            positions = puller(ats_params)
            entry["consecutive_failures"] = 0
            entry["last_jobs_pulled_at"] = now_iso()
            # Company pulled successfully — record it regardless of position count
            successful_companies.append(name)

            if not positions:
                print(f"  {name}: 0 open positions")
                continue

            location_filter = entry.get("location_filter")
            if location_filter:
                before = len(positions)
                positions = [
                    p for p in positions
                    if location_filter.lower() in (p.get("location") or "").lower()
                ]
                filtered = before - len(positions)
                if filtered:
                    print(f"    location_filter '{location_filter}': dropped {filtered} non-matching jobs")
                if not positions:
                    print(f"  {name}: 0 positions after location filter")
                    continue

            for pos in positions:
                all_jobs.append(
                    {
                        "company": name,
                        "title": pos["title"],
                        "location": pos["location"],
                        "description": pos["description"],
                        "apply_url": pos["apply_url"],
                        "source_vc": entry.get("source_vc", ""),
                        "vc_tier": entry.get("vc_tier", ""),
                        "ats": ats,
                    }
                )
                url = (pos.get("apply_url") or "").strip()
                if url:
                    live_apply_urls.append(url)
            print(f"  {name}: {len(positions)} open positions")
            companies_with_jobs += 1

        except Exception as e:
            entry["consecutive_failures"] = entry.get("consecutive_failures", 0) + 1
            print(f"  {name}: ERROR — {e} (failures={entry['consecutive_failures']})")

    save_companies(companies)

    _write_json_atomic(
        LIVE_POSITIONS_FILE,
        {
            "generated_at": now_iso(),
            "successful_companies": successful_companies,
            "live_apply_urls": live_apply_urls,
        },
    )
    print(f"Live positions: {len(live_apply_urls)} URLs across {len(successful_companies)} successful companies")

    before = len(all_jobs)
    seen_urls: set[str] = set()
    deduped = []
    for job in all_jobs:
        url = (job.get("apply_url") or "").strip()
        if not url:
            deduped.append(job)
            continue
        if url not in seen_urls:
            seen_urls.add(url)
            deduped.append(job)
    all_jobs = deduped
    if len(all_jobs) < before:
        print(f"Dedup: {before} → {len(all_jobs)} jobs ({before - len(all_jobs)} duplicates removed)")

    today = datetime.now(timezone.utc).date().isoformat()
    for job in all_jobs:
        url = (job.get("apply_url") or "").strip()
        job["first_seen"] = first_seen_lookup.get(url, today) if url else today

    _write_json_atomic(JOBS_FILE, all_jobs)

    print(f"\nTotal: {len(all_jobs)} jobs across {companies_with_jobs} companies")
    print(f"Saved to {JOBS_FILE}")


if __name__ == "__main__":
    collect()
