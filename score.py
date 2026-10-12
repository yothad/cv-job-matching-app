#!/usr/bin/env python3
"""Orchestrator: new_jobs.json + profiles/ → per-profile digest.md via Gemini.

Digest is cumulative: each run merges newly relevant jobs into scored_jobs.json
(deduped by apply_url), then regenerates digest.md sorted newest-first.

Single-profile fallback: if profiles/ has no valid subdirectories, reads
profile.md + cv.md + .env from the repo root and writes to the root.
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from matcher.gemini_scorer import build_prompt, score_jobs_batch, QuotaExhaustedError

# Jobs below this score are not persisted in the digest.
RELEVANCE_THRESHOLD = 5

_BATCH_SIZE = int(os.environ.get("GEMINI_BATCH_SIZE", "10"))

# Substrings that indicate an Israel-area location (case-insensitive).
_ISRAEL_TERMS = [
    "israel", "tel aviv", "herzliya", "ra'anana", "raanana",
    "petach", "petah", "ramat gan", "netanya", "holon", "bat yam",
    "bnei brak", "givat", "rehovot", "yokneam", "jerusalem", "haifa",
    "airport city", "kfar saba", "hod hasharon", "rishon", "rosh haayin",
]

# "Remote" jobs that are explicitly NOT Israel-compatible.

# Title keywords that clearly indicate a non-DS/ML role.
# Denylist only - when in doubt, let Gemini decide.
_SKIP_TITLE_TERMS = [
    "sales engineer", "solutions engineer", "sales development",
    "account executive", "account manager", "business development",
    "marketing manager", "marketing director", "content marketing",
    "brand designer", "graphic designer", "ux designer", "ui designer",
    "product designer", "web designer",
    "talent acquisition", "recruiter", "hr business", "human resources",
    "legal counsel", "general counsel", "corporate counsel",
    "finance manager", "financial analyst", "controller", "accountant",
    "customer success", "customer support", "technical support",
    "office manager", "executive assistant", "administrative",
    "copywriter", "content writer", "technical writer",
    "devops engineer", "site reliability", " sre ", "platform engineer",
    "it manager", "it support", "network engineer",
    "partnerships manager", "channel partner",
]


def _location_prefilter(jobs: list[dict]) -> tuple[list[dict], int]:
    """Keep jobs in Israel or with no location. Drop everything else including remote."""
    kept, empty_loc = [], 0
    for job in jobs:
        loc = (job.get("location") or "").strip()
        if not loc:
            kept.append(job)
            empty_loc += 1
            continue
        if any(term in loc.lower() for term in _ISRAEL_TERMS):
            kept.append(job)
    return kept, empty_loc


# At least one of these must appear in the title to pass to Gemini.
_KEEP_TITLE_TERMS = [
    # Data / ML / AI
    "data scientist", "data science", "data engineer", "data analyst",
    "machine learning", "ml engineer", "mlops",
    "ai engineer", "ai researcher", "ai research", "artificial intelligence",
    "applied scientist", "applied ml",
    # Security / Fraud / Risk
    "security researcher", "security research", "security engineer",
    "threat", "detection", "fraud", "risk",
    "anomaly", "offensive security", "application security",
    # Research
    "research scientist", "research engineer",
    # Leadership / IC tracks in relevant domains
    "r&d", "team lead", "team leader",
    # Broad positive signals - let Gemini decide the rest
    "analyst", "scientist",
]


def _read_cv(path: Path) -> str:
    """Read a CV file — supports .md/.txt and .docx."""
    if path.suffix.lower() == ".docx":
        import zipfile
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(path) as z:
            with z.open("word/document.xml") as f:
                tree = ET.parse(f)
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        parts = []
        for elem in tree.iter(f"{ns}t"):
            if elem.text:
                parts.append(elem.text)
        return " ".join(parts)
    return path.read_text(encoding="utf-8")


def _resolve_cvs(profile_dir: Path, config: dict, name: str) -> tuple[str, str]:
    """Return (cv_default, cv_lead) text for a profile.

    score_config.json may point cv_default / cv_lead at local files (e.g. a .docx
    outside the repo). Those don't exist in CI, so a missing configured path
    falls back with a warning instead of crashing the run:
      cv_default -> profile_dir/cv.md (or "" if that is absent too)
      cv_lead    -> cv_default (same as when cv_lead is unset)
    """
    fallback = profile_dir / "cv.md"
    cv_default_path = config.get("cv_default")
    default_label = "cv.md"
    if cv_default_path and Path(cv_default_path).exists():
        cv_default = _read_cv(Path(cv_default_path))
        default_label = Path(cv_default_path).name
    else:
        if cv_default_path:
            print(f"[{name}] Warning: cv_default not found ({Path(cv_default_path).name}) - falling back to cv.md")
        cv_default = _read_cv(fallback) if fallback.exists() else ""

    cv_lead_path = config.get("cv_lead")
    if cv_lead_path and Path(cv_lead_path).exists():
        cv_lead = _read_cv(Path(cv_lead_path))
        print(f"[{name}] CV routing: lead CV - {Path(cv_lead_path).name}, default CV - {default_label}")
    else:
        if cv_lead_path:
            print(f"[{name}] Warning: cv_lead not found ({Path(cv_lead_path).name}) - using the default CV for lead roles")
        cv_lead = cv_default
    return cv_default, cv_lead


def _sync_applied_from_digest(digest_path: Path, jobs_by_key: dict) -> int:
    """Read digest.md, find Applied: 1 entries, mark them in jobs_by_key. Returns count updated."""
    if not digest_path.exists():
        return 0
    import re
    text = digest_path.read_text(encoding="utf-8")
    # Find all (url, applied_value) pairs from the digest
    # Format: ### **Company** - [Title](url) ... **Applied:** 0|1
    blocks = re.split(r'\n(?=### )', text)
    updated = 0
    for block in blocks:
        url_match = re.search(r'\]\((https?://[^\)]+)\)', block)
        applied_match = re.search(r'\*\*Applied:\*\* (\d)', block)
        if url_match and applied_match and applied_match.group(1) == "1":
            url = url_match.group(1)
            if url in jobs_by_key and not jobs_by_key[url].get("applied"):
                jobs_by_key[url]["applied"] = True
                updated += 1
    return updated


def _load_profile_config(profile_dir: Path) -> dict:
    """Load score_config.json from a profile dir; returns {} if absent."""
    config_path = profile_dir / "score_config.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def _title_prefilter(jobs: list[dict], skip_terms: list[str] | None = None) -> tuple[list[dict], int]:
    """Drop jobs whose title matches any skip term."""
    terms = skip_terms if skip_terms is not None else _SKIP_TITLE_TERMS
    kept, dropped = [], 0
    for job in jobs:
        title_lower = (job.get("title") or "").lower()
        if any(term in title_lower for term in terms):
            dropped += 1
        else:
            kept.append(job)
    return kept, dropped


def _company_filter(jobs: list[dict], skip_companies: list[str]) -> tuple[list[dict], int]:
    """Drop jobs whose company exactly matches any entry in skip_companies (case-insensitive)."""
    if not skip_companies:
        return jobs, 0
    skip_lower = {c.lower() for c in skip_companies}
    kept, dropped = [], 0
    for job in jobs:
        if (job.get("company") or "").lower() in skip_lower:
            dropped += 1
        else:
            kept.append(job)
    return kept, dropped


def _title_allowlist_filter(jobs: list[dict], keep_terms: list[str] | None = None) -> tuple[list[dict], int]:
    """Keep only jobs whose title matches at least one keep term. Pass keep_terms=[] to disable."""
    if keep_terms is not None and len(keep_terms) == 0:
        return jobs, 0
    terms = keep_terms if keep_terms is not None else _KEEP_TITLE_TERMS
    kept, dropped = [], 0
    for job in jobs:
        title_lower = (job.get("title") or "").lower()
        if any(term in title_lower for term in terms):
            kept.append(job)
        else:
            dropped += 1
    return kept, dropped


def _score_jobs_batched(
    filtered_jobs: list[dict],
    profile_md: str,
    cv_md: str,
    client,
    name: str,
    all_scores_fp=None,
) -> list[dict]:
    N = len(filtered_jobs)
    scored: list[dict] = []

    for batch_start in range(0, N, _BATCH_SIZE):
        batch = filtered_jobs[batch_start:batch_start + _BATCH_SIZE]
        try:
            results = score_jobs_batch(batch, profile_md, cv_md, client)
        except QuotaExhaustedError:
            print(f"[{name}] QUOTA EXHAUSTED. Scored {len(scored)}/{N}. Persisting partial results.")
            break

        for j, (job, result) in enumerate(zip(batch, results)):
            merged = {**job, **result}
            scored.append(merged)
            i = batch_start + j + 1
            label = f"{job.get('company', '?')} - {job.get('title', '?')}"
            print(f"[{name}] [{i}/{N}] {label}: score={result['score']}")
            # scorer errors (503s, malformed output) are not logged as seen, so the next run retries them
            if all_scores_fp and "scorer-error" not in result["flags"]:
                all_scores_fp.write(json.dumps(merged, ensure_ascii=False) + "\n")
                all_scores_fp.flush()

    return scored


def _discover_profiles(profiles_dir: Path) -> list[Path]:
    if not profiles_dir.is_dir():
        return []
    return sorted(
        d for d in profiles_dir.iterdir()
        if d.is_dir() and (d / "profile.md").exists() and (d / "cv.md").exists()
    )


def _job_key(job: dict) -> str:
    url = (job.get("apply_url") or "").strip()
    if url:
        return url
    return f"{job.get('company', '')}::{job.get('title', '')}".lower()


def _load_scored_jobs(store_path: Path) -> dict:
    """Returns {key: job_dict} for all previously persisted jobs."""
    if not store_path.exists():
        return {}
    with open(store_path, encoding="utf-8") as f:
        jobs = json.load(f)
    return {_job_key(j): j for j in jobs}


def _load_seen_keys(profile_dir: Path) -> set[str]:
    """Return the set of job keys already scored (any score, including sub-threshold)."""
    seen: set[str] = set()
    jsonl_path = profile_dir / "all_scores.jsonl"
    if jsonl_path.exists():
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    seen.add(_job_key(json.loads(line)))
                except (json.JSONDecodeError, KeyError):
                    continue
    seen |= _load_scored_jobs(profile_dir / "scored_jobs.json").keys()
    return seen


def _save_scored_jobs(store_path: Path, jobs_by_key: dict) -> None:
    store_path.write_text(
        json.dumps(list(jobs_by_key.values()), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _merge_new_results(existing: dict, new_scored: list[dict], today: str) -> tuple[dict, int]:
    """Add newly relevant jobs not already in the store. Returns (merged, added_count)."""
    merged = dict(existing)
    added = 0
    for job in new_scored:
        if job.get("score", 0) < RELEVANCE_THRESHOLD:
            continue
        key = _job_key(job)
        if key in merged:
            continue
        merged[key] = {
            "company": job.get("company", ""),
            "title": job.get("title", ""),
            "location": job.get("location", ""),
            "apply_url": job.get("apply_url", ""),
            "source_vc": job.get("source_vc", ""),
            "score": job["score"],
            "reasoning": job.get("reasoning", ""),
            "flags": job.get("flags", []),
            "scored_at": today,
            "first_seen": job.get("first_seen"),
        }
        added += 1
    return merged, added


def _load_live_positions(root: Path = Path(".")) -> tuple[set[str], set[str]]:
    """Load live_positions.json → (live_urls, successful_companies). Returns empty sets if missing."""
    path = root / "live_positions.json"
    if not path.exists():
        return set(), set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        live = {u.strip() for u in data.get("live_apply_urls", []) if u.strip()}
        successful = {c.lower() for c in data.get("successful_companies", [])}
        return live, successful
    except (json.JSONDecodeError, KeyError):
        return set(), set()


def _reconcile_status(jobs_by_key: dict, live: set[str], successful: set[str], today: str) -> None:
    """Stamp status=open/closed on each job in-place. Skips reconciliation if live/successful are empty."""
    if not live and not successful:
        return
    for key, job in jobs_by_key.items():
        url = (job.get("apply_url") or "").strip()
        company_lower = (job.get("company") or "").lower()
        if url in live:
            job["status"] = "open"
            job.pop("closed_at", None)
        elif company_lower in successful:
            job["status"] = "closed"
            if "closed_at" not in job:
                job["closed_at"] = today
        else:
            if "status" not in job:
                job["status"] = "open"


_CLOSED_CAP = 30


def _write_digest(jobs_by_key: dict, out_path: Path) -> None:
    """Write digest.md grouped by date (newest first), score desc within each date.
    Applied jobs (applied=True in scored_jobs.json) are hidden with a count shown.
    Closed jobs (status=closed) are collected in a trailing section."""
    all_jobs = list(jobs_by_key.values())
    visible = [j for j in all_jobs if not j.get("applied")]
    hidden = len(all_jobs) - len(visible)

    open_jobs = [j for j in visible if j.get("status", "open") != "closed"]
    closed_jobs = [j for j in visible if j.get("status") == "closed"]

    open_jobs.sort(key=lambda j: (j.get("scored_at", ""), j.get("score", 0)), reverse=True)
    closed_jobs.sort(key=lambda j: (j.get("closed_at", ""), j.get("score", 0)), reverse=True)

    dates: dict[str, list[dict]] = {}
    for job in open_jobs:
        d = job.get("scored_at", "unknown")
        dates.setdefault(d, []).append(job)

    lines = ["# Job Digest\n"]
    if hidden:
        lines.append(f"*{hidden} applied position{'s' if hidden != 1 else ''} hidden.*\n")

    for day in sorted(dates.keys(), reverse=True):
        lines.append(f"## {day}\n")
        for job in dates[day]:
            title = job.get("title", "")
            company = job.get("company", "")
            apply_url = job.get("apply_url", "")
            location = job.get("location", "unknown location")
            score = job.get("score", 0)
            reasoning = job.get("reasoning", "")
            flags = job.get("flags", [])

            title_link = f"[{title}]({apply_url})" if apply_url else title
            flag_str = f" `{'` `'.join(flags)}`" if flags else ""
            first_seen = job.get("first_seen")
            first_seen_str = f" | **First seen:** {first_seen}" if first_seen else ""

            lines.append(f"### **{company}** - {title_link}")
            lines.append(f"**Score:** {score}/10 | **Location:** {location} | **Applied:** 0{first_seen_str}")
            lines.append(f"**Reasoning:** {reasoning}{flag_str}")
            lines.append("")

    if closed_jobs:
        shown = closed_jobs[:_CLOSED_CAP]
        dropped = len(closed_jobs) - len(shown)
        lines.append(f"## Recently closed ({len(closed_jobs)})\n")
        if dropped:
            print(f"Closed section: showing {len(shown)}, hiding {dropped} older entries")
        for job in shown:
            title = job.get("title", "")
            company = job.get("company", "")
            apply_url = job.get("apply_url", "")
            location = job.get("location", "unknown location")
            score = job.get("score", 0)
            closed_at = job.get("closed_at", "")
            flags = job.get("flags", [])

            title_link = f"[~~{title}~~]({apply_url})" if apply_url else f"~~{title}~~"
            flag_str = f" `{'` `'.join(flags)}`" if flags else ""
            closed_label = f" (closed {closed_at})" if closed_at else ""

            lines.append(f"### **{company}** - {title_link}{closed_label}")
            lines.append(f"**Score:** {score}/10 | **Location:** {location}")
            lines.append(f"**Reasoning:** {job.get('reasoning', '')}{flag_str}")
            lines.append("")
        if dropped:
            lines.append(f"*(+{dropped} older closed hidden)*\n")

    out_path.write_text("\n".join(lines), encoding="utf-8")


class MissingApiKeyError(RuntimeError):
    """GEMINI_API_KEY is unset for a profile. Must fail the run (non-zero exit) -
    a silent return kept CI green for ~2 months while nothing was scored."""


def _score_one_profile(profile_dir: Path, jobs: list, args) -> None:
    name = profile_dir.name

    env_file = profile_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"[{name}] Error: GEMINI_API_KEY not set.", file=sys.stderr)
        raise MissingApiKeyError(name)

    profile_md = (profile_dir / "profile.md").read_text(encoding="utf-8")

    from google import genai
    client = genai.Client(api_key=api_key)

    seen = _load_seen_keys(profile_dir)
    total_in = len(jobs)
    jobs = [j for j in jobs if _job_key(j) not in seen]
    print(f"[{name}] Pre-filter: {total_in} → {len(jobs)} after dedup ({total_in - len(jobs)} already scored)")
    if not jobs:
        print(f"[{name}] Nothing new to score.")
        return

    config = _load_profile_config(profile_dir)
    skip_companies = config.get("skip_companies", [])
    skip_terms = config.get("skip_title_terms", _SKIP_TITLE_TERMS)
    keep_terms = config.get("keep_title_terms", _KEEP_TITLE_TERMS)

    # CV routing: lead CV vs default CV
    lead_terms = [t.lower() for t in config.get("lead_title_terms", [])]
    cv_default, cv_lead = _resolve_cvs(profile_dir, config, name)

    total = len(jobs)
    loc_filtered, empty_loc = _location_prefilter(jobs)
    co_filtered, co_dropped = _company_filter(loc_filtered, skip_companies)
    title_filtered, title_dropped = _title_prefilter(co_filtered, skip_terms)
    allowlisted, allowlist_dropped = _title_allowlist_filter(title_filtered, keep_terms)
    filtered_jobs = allowlisted
    print(
        f"[{name}] Funnel: {total} total"
        f" → {len(loc_filtered)} after location ({total - len(loc_filtered)} dropped, {empty_loc} empty-loc kept)"
        + (f" → {len(co_filtered)} after company filter ({co_dropped} dropped)" if co_dropped else "")
        + f" → {len(title_filtered)} after title denylist ({title_dropped} dropped)"
        f" → {len(filtered_jobs)} after title allowlist ({allowlist_dropped} dropped)"
        f" → sending {len(filtered_jobs)} to Gemini"
    )

    all_scores_path = profile_dir / "all_scores.jsonl"
    all_scores_fp = open(all_scores_path, "a", encoding="utf-8")
    try:
        if lead_terms and cv_lead != cv_default:
            lead_jobs = [j for j in filtered_jobs if any(t in (j.get("title") or "").lower() for t in lead_terms)]
            other_jobs = [j for j in filtered_jobs if j not in lead_jobs]
            print(f"[{name}] CV split: {len(lead_jobs)} lead jobs, {len(other_jobs)} other jobs")
            scored = []
            if lead_jobs:
                scored += _score_jobs_batched(lead_jobs, profile_md, cv_lead, client, name, all_scores_fp)
            if other_jobs:
                scored += _score_jobs_batched(other_jobs, profile_md, cv_default, client, name, all_scores_fp)
        else:
            scored = _score_jobs_batched(filtered_jobs, profile_md, cv_default, client, name, all_scores_fp)
    finally:
        all_scores_fp.close()

    store_path = profile_dir / "scored_jobs.json"
    existing = _load_scored_jobs(store_path)
    merged, added = _merge_new_results(existing, scored, date.today().isoformat())

    if not args.dry_run:
        live, successful = _load_live_positions()
        _reconcile_status(merged, live, successful, date.today().isoformat())
        closed_count = sum(1 for j in merged.values() if j.get("status") == "closed")
        if live or successful:
            print(f"[{name}] Status reconciled: {closed_count} closed / {len(merged)} total")

    # Sync applied status from digest before saving
    out_path = profile_dir / "digest.md"
    synced = _sync_applied_from_digest(out_path, merged)
    if synced:
        print(f"[{name}] Synced {synced} applied position{'s' if synced != 1 else ''} from digest")

    _save_scored_jobs(store_path, merged)
    _write_digest(merged, out_path)
    print(f"[{name}] +{added} new positions | total {len(merged)} | wrote {out_path}")


def _rescore_profile(profile_dir: Path) -> None:
    name = profile_dir.name
    store_path = profile_dir / "scored_jobs.json"
    if not store_path.exists():
        print(f"[{name}] No scored_jobs.json, nothing to rescore.")
        return

    existing = _load_scored_jobs(store_path)
    if not existing:
        print(f"[{name}] scored_jobs.json is empty.")
        return

    env_file = profile_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file, override=True)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print(f"[{name}] Error: GEMINI_API_KEY not set.", file=sys.stderr)
        raise MissingApiKeyError(name)

    profile_md = (profile_dir / "profile.md").read_text(encoding="utf-8")
    config = _load_profile_config(profile_dir)
    cv_default, _ = _resolve_cvs(profile_dir, config, name)

    from google import genai
    client = genai.Client(api_key=api_key)

    jobs_to_rescore = list(existing.values())
    print(f"[{name}] Rescoring {len(jobs_to_rescore)} jobs...")

    rescored = _score_jobs_batched(jobs_to_rescore, profile_md, cv_default, client, name, all_scores_fp=None)

    for job in rescored:
        key = _job_key(job)
        if key in existing and "scorer-error" not in job.get("flags", []):
            existing[key]["score"] = job["score"]
            existing[key]["reasoning"] = job.get("reasoning", "")
            existing[key]["flags"] = job.get("flags", [])

    out_path = profile_dir / "digest.md"
    _save_scored_jobs(store_path, existing)
    _write_digest(existing, out_path)
    print(f"[{name}] Rescored {len(rescored)} jobs | wrote {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Score jobs and write per-profile digest.md")
    parser.add_argument("--dry-run", action="store_true", help="Print prompt for first job and exit")
    parser.add_argument("--rescore", action="store_true", help="Re-score all jobs in scored_jobs.json with current profile")
    parser.add_argument("--input", default="new_jobs.json", help="Input jobs JSON file")
    parser.add_argument("--sample", action="store_true", help="Use tests/sample_jobs.json instead")
    parser.add_argument("--profiles-dir", default="profiles", help="Directory containing profile subdirectories")
    parser.add_argument("--profile", help="Run only this profile name (subdirectory under --profiles-dir)")
    args = parser.parse_args()

    profiles_dir = Path(args.profiles_dir)
    profiles = _discover_profiles(profiles_dir)

    if args.profile:
        profiles = [p for p in profiles if p.name == args.profile]
        if not profiles:
            print(f"Error: profile '{args.profile}' not found under {profiles_dir}", file=sys.stderr)
            sys.exit(1)

    if args.rescore and not args.dry_run:
        if not profiles:
            print("Error: no profiles found for rescore.", file=sys.stderr)
            sys.exit(1)
        failed = []
        for profile in profiles:
            try:
                _rescore_profile(profile)
            except MissingApiKeyError:
                failed.append(profile.name)
        if failed:
            sys.exit(1)
        return

    input_file = "tests/sample_jobs.json" if args.sample else args.input
    if not Path(input_file).exists():
        print(f"Error: {input_file} not found. Run collect_jobs.py first.", file=sys.stderr)
        sys.exit(1)

    with open(input_file, encoding="utf-8") as f:
        jobs = json.load(f)

    if not jobs:
        print("No jobs to score.")
        return

    if not profiles:
        _run_root_profile(jobs, args)
        return

    if args.dry_run:
        first_profile = profiles[0]
        profile_md = (first_profile / "profile.md").read_text(encoding="utf-8")
        cv_md = (first_profile / "cv.md").read_text(encoding="utf-8")
        print(f"=== DRY RUN - profile: {first_profile.name} - prompt for first job ===\n")
        print(build_prompt(jobs[0], profile_md, cv_md))
        return

    failed: list[str] = []
    if len(profiles) == 1:
        try:
            _score_one_profile(profiles[0], jobs, args)
        except MissingApiKeyError:
            failed.append(profiles[0].name)
    else:
        with ThreadPoolExecutor(max_workers=len(profiles)) as pool:
            futures = {pool.submit(_score_one_profile, p, jobs, args): p.name for p in profiles}
            for fut in as_completed(futures):
                exc = fut.exception()
                if exc:
                    failed.append(futures[fut])
                    if not isinstance(exc, MissingApiKeyError):
                        print(f"[{futures[fut]}] Error: {exc}", file=sys.stderr)
    if failed:
        print(f"Error: scoring failed for profile(s): {', '.join(sorted(failed))}", file=sys.stderr)
        sys.exit(1)


def _run_root_profile(jobs: list, args) -> None:
    """Single-profile fallback using root profile.md + cv.md + .env."""
    load_dotenv()

    profile_path = Path("profile.md")
    cv_path = Path("cv.md")

    if not profile_path.exists() or not cv_path.exists():
        print("Error: no profiles found and root profile.md/cv.md missing.", file=sys.stderr)
        sys.exit(1)

    profile_md = profile_path.read_text(encoding="utf-8")
    cv_md = cv_path.read_text(encoding="utf-8")

    if args.dry_run:
        print("=== DRY RUN - prompt for first job ===\n")
        print(build_prompt(jobs[0], profile_md, cv_md))
        return

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=api_key)

    root_dir = Path(".")
    seen = _load_seen_keys(root_dir)
    total_in = len(jobs)
    jobs = [j for j in jobs if _job_key(j) not in seen]
    print(f"[root] Pre-filter: {total_in} → {len(jobs)} after dedup ({total_in - len(jobs)} already scored)")
    if not jobs:
        print("[root] Nothing new to score.")
        return

    total = len(jobs)
    loc_filtered, empty_loc = _location_prefilter(jobs)
    title_filtered, title_dropped = _title_prefilter(loc_filtered)
    allowlisted, allowlist_dropped = _title_allowlist_filter(title_filtered)
    filtered_jobs = allowlisted
    print(
        f"[root] Funnel: {total} total"
        f" → {len(loc_filtered)} after location ({total - len(loc_filtered)} dropped, {empty_loc} empty-loc kept)"
        f" → {len(title_filtered)} after title denylist ({title_dropped} dropped)"
        f" → {len(filtered_jobs)} after title allowlist ({allowlist_dropped} dropped)"
        f" → sending {len(filtered_jobs)} to Gemini"
    )

    all_scores_fp = open(root_dir / "all_scores.jsonl", "a", encoding="utf-8")
    try:
        scored = _score_jobs_batched(filtered_jobs, profile_md, cv_md, client, "root", all_scores_fp)
    finally:
        all_scores_fp.close()

    store_path = Path("scored_jobs.json")
    existing = _load_scored_jobs(store_path)
    merged, added = _merge_new_results(existing, scored, date.today().isoformat())

    if not args.dry_run:
        live, successful = _load_live_positions()
        _reconcile_status(merged, live, successful, date.today().isoformat())
        closed_count = sum(1 for j in merged.values() if j.get("status") == "closed")
        if live or successful:
            print(f"[root] Status reconciled: {closed_count} closed / {len(merged)} total")

    out_path = Path("digest.md")
    synced = _sync_applied_from_digest(out_path, merged)
    if synced:
        print(f"[root] Synced {synced} applied position{'s' if synced != 1 else ''} from digest")

    _save_scored_jobs(store_path, merged)
    _write_digest(merged, out_path)
    print(f"\n+{added} new positions | total {len(merged)} | wrote {out_path}")


if __name__ == "__main__":
    main()
