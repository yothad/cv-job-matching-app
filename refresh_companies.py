#!/usr/bin/env python3
"""
Weekly runner: scrape VC portfolios, discover careers/ATS for new companies,
re-verify stale or failing ones. Also merges big_companies.yml (manual list).
Writes/merges companies.json.

Run: uv run python refresh_companies.py
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from ats.detect import detect_ats, find_careers_url
from collect_jobs import _write_json_atomic
from vcs.registry import VC_REGISTRY

COMPANIES_FILE = Path("companies.json")
BIG_COMPANIES_FILE = Path("big_companies.yml")
REVERIFY_DAYS = 30
REVERIFY_FAILURES = 3


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_companies() -> dict[str, dict]:
    """Load existing companies.json keyed by company name. Returns {} if file absent."""
    if not COMPANIES_FILE.exists():
        return {}
    with COMPANIES_FILE.open(encoding="utf-8") as f:
        entries = json.load(f)
    return {e["name"]: e for e in entries}


def save_companies(companies: dict[str, dict]) -> None:
    _write_json_atomic(COMPANIES_FILE, list(companies.values()))


def needs_reverify(entry: dict, reverify_unknown: bool = False) -> bool:
    # Escape hatch: force a re-check of unknown-ATS entries even if skipped.
    if reverify_unknown and entry.get("ats") == "unknown":
        return True
    # Dead-end companies (unknown ATS, no website, no careers page, acquired)
    # are flagged skip_discovery so we stop wasting Playwright discovery on them
    # every cycle. Re-run scripts/mark_skips.py to refresh the set, or pass
    # --reverify-unknown to override for the unknown-ATS ones.
    if entry.get("skip_discovery"):
        return False
    if entry.get("consecutive_failures", 0) >= REVERIFY_FAILURES:
        return True
    lv = entry.get("last_verified_at")
    if not lv:
        return True
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(lv)).days
    return age >= REVERIFY_DAYS


def discover(name: str, website: str) -> dict:
    """Run careers URL discovery + ATS detection. Returns partial entry dict."""
    careers_url = find_careers_url(website)
    if not careers_url:
        print(f"  {name}: no careers page found")
        return {"careers_url": None, "ats": "unknown", "ats_params": {}}

    ats_name, ats_params = detect_ats(careers_url)
    if ats_name == "unknown":
        print(f"  {name}: ATS unknown")
    else:
        print(f"  {name}: detected {ats_name}")
    return {"careers_url": careers_url, "ats": ats_name, "ats_params": ats_params}


def apply_reverify(entry: dict, discovery: dict) -> None:
    """Record a re-verification result on an existing entry.

    A discovery that finds no usable ATS never overwrites a working cached
    config: discovery flakes (timeouts, bot walls, careers page redesigns) used
    to wipe live companies to ats=unknown, which collect_jobs then skips.
    consecutive_failures is left as-is so a still-failing entry retries next run.
    """
    entry["last_verified_at"] = now_iso()
    if not discovery["ats_params"] and entry.get("ats", "unknown") != "unknown" and entry.get("ats_params"):
        print(f"  {entry['name']}: re-discovery found no ATS, keeping cached {entry['ats']}")
        return
    entry["careers_url"] = discovery["careers_url"]
    entry["ats"] = discovery["ats"]
    entry["ats_params"] = discovery["ats_params"]
    entry["consecutive_failures"] = 0


def merge_big_companies(companies: dict[str, dict]) -> tuple[int, int]:
    """
    Merge big_companies.yml into companies dict.
    Returns (new_count, updated_count).
    Never runs discovery - trusts the YAML's manually-verified fields.
    """
    if not BIG_COMPANIES_FILE.exists():
        print(f"  {BIG_COMPANIES_FILE} not found, skipping")
        return 0, 0

    with BIG_COMPANIES_FILE.open(encoding="utf-8") as f:
        raw_entries = yaml.safe_load(f) or []

    now = now_iso()
    new_count = 0
    updated_count = 0

    for raw in raw_entries:
        name = raw["name"]

        if name not in companies:
            companies[name] = {
                "name": name,
                "website": raw["website"],
                "source": "big_companies_list",
                "source_vc": None,
                "vc_tier": None,
                "careers_url": raw.get("careers_url"),
                "ats": raw.get("ats", "unknown"),
                "ats_params": raw.get("ats_params") or {},
                "category": raw.get("category"),
                "location_filter": raw.get("location_filter"),
                "discovered_at": now,
                "last_verified_at": now,
                "last_jobs_pulled_at": None,
                "consecutive_failures": 0,
            }
            print(f"  {name}: added from big_companies.yml ({raw.get('ats', 'unknown')})")
            new_count += 1

        else:
            entry = companies[name]
            changed = False
            for field in ("website", "careers_url", "ats", "ats_params", "category", "location_filter"):
                if field in raw and entry.get(field) != raw[field]:
                    entry[field] = raw[field]
                    changed = True
            # Always stamp source; preserve vc metadata if this company also appears in a VC portfolio
            entry["source"] = "big_companies_list"
            if changed:
                entry["last_verified_at"] = now
                print(f"  {name}: updated from big_companies.yml")
                updated_count += 1
            else:
                print(f"  {name}: unchanged")

    return new_count, updated_count


def refresh(reverify_unknown: bool = False):
    companies = load_companies()
    print(f"Loaded {len(companies)} existing companies from {COMPANIES_FILE}\n")

    new_count = 0
    reverified_count = 0
    seen_in_vc: set[str] = set()

    for vc_name, vc_meta in VC_REGISTRY.items():
        print(f"=== {vc_name} ===")
        try:
            portfolio = vc_meta["fetch"]()
        except Exception as e:
            print(f"FATAL: failed to fetch {vc_name} portfolio: {e}", file=sys.stderr)
            continue

        for raw in portfolio:
            name = raw["company_name"]
            website = raw["company_website"]
            seen_in_vc.add(name)

            if name not in companies:
                print(f"  {name}: new company, running discovery")
                discovery = discover(name, website)
                companies[name] = {
                    "name": name,
                    "website": website,
                    "source_vc": vc_name,
                    "vc_tier": vc_meta["tier"],
                    "careers_url": discovery["careers_url"],
                    "ats": discovery["ats"],
                    "ats_params": discovery["ats_params"],
                    "discovered_at": now_iso(),
                    "last_verified_at": now_iso(),
                    "last_jobs_pulled_at": None,
                    "consecutive_failures": 0,
                }
                new_count += 1

            else:
                entry = companies[name]
                entry["source_vc"] = vc_name
                entry["vc_tier"] = vc_meta["tier"]
                entry["website"] = website

                if entry.get("status") == "acquired":
                    print(f"  {name}: acquired, skipping")
                    continue

                if needs_reverify(entry, reverify_unknown):
                    reason = (
                        f"consecutive_failures={entry.get('consecutive_failures', 0)}"
                        if entry.get("consecutive_failures", 0) >= REVERIFY_FAILURES
                        else f"last_verified {entry.get('last_verified_at', 'never')}"
                    )
                    print(f"  {name}: re-verifying ({reason})")
                    apply_reverify(entry, discover(name, website))
                    reverified_count += 1
                else:
                    print(f"  {name}: cached, skipping discovery")

        print()

    # Second pass: VC-discovered entries not in current portfolio scrape
    # (manually-added acquirers, etc.) - but skip big_companies_list entries
    manual_entries = [
        e for name, e in companies.items()
        if name not in seen_in_vc and e.get("source") != "big_companies_list"
    ]
    if manual_entries:
        print("=== Manually-added entries (non-VC, non-big-companies) ===")
        for entry in manual_entries:
            name = entry["name"]
            if entry.get("status") == "acquired":
                continue
            if needs_reverify(entry, reverify_unknown):
                print(f"  {name}: running discovery")
                try:
                    apply_reverify(entry, discover(name, entry["website"]))
                    reverified_count += 1
                except Exception as e:
                    print(f"  {name}: ERROR - {e}")
            else:
                print(f"  {name}: cached, skipping discovery")
        print()

    # Merge big_companies.yml (never auto-discovered, always manual)
    print("=== big_companies.yml ===")
    bc_new, bc_updated = merge_big_companies(companies)
    print()

    save_companies(companies)

    print(
        f"Done. VC new: {new_count}, VC re-verified: {reverified_count}, "
        f"big-companies new: {bc_new}, big-companies updated: {bc_updated}, "
        f"total: {len(companies)}"
    )
    print(f"Saved to {COMPANIES_FILE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--reverify-unknown",
        action="store_true",
        help="Force re-verification of all entries where ats == 'unknown'",
    )
    args = parser.parse_args()
    refresh(reverify_unknown=args.reverify_unknown)
