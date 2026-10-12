#!/usr/bin/env python3
"""Build a CSV labelling sheet for the scorer golden set, and import it back.

  uv run python evals/make_labelling_sheet.py --n 60
      -> evals/private/labelling_sheet.csv (blank label columns)
  uv run python evals/make_labelling_sheet.py --import evals/private/labelling_sheet.csv
      -> evals/private/golden_set.jsonl

Sampling is stratified across the Gemini score bands in profiles/<p>/all_scores.jsonl
plus jobs from new_jobs.json that score.py's hard filters drop before Gemini.
Gemini's score is NOT written to the sheet so the human label stays blind.
"""

import argparse
import csv
import json
import random
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals import metrics  # noqa: E402
from score import (  # noqa: E402
    _KEEP_TITLE_TERMS,
    _SKIP_TITLE_TERMS,
    _company_filter,
    _job_key,
    _load_profile_config,
    _location_prefilter,
    _title_allowlist_filter,
    _title_prefilter,
)

PRIVATE_DIR = ROOT / "evals" / "private"
JOB_COLS = ["job_id", "company", "title", "location", "source_vc", "vc_tier", "apply_url", "description"]
LABEL_COLS = ["label_score", "label_band", "label_flags", "notes"]
BUCKETS = metrics.BANDS + ["filtered"]


def _hard_filtered(jobs: list[dict], config: dict) -> list[dict]:
    """Jobs score.py drops before Gemini (location, company, title deny/allow lists)."""
    kept, _ = _location_prefilter(jobs)
    kept, _ = _company_filter(kept, config.get("skip_companies", []))
    kept, _ = _title_prefilter(kept, config.get("skip_title_terms", _SKIP_TITLE_TERMS))
    kept, _ = _title_allowlist_filter(kept, config.get("keep_title_terms", _KEEP_TITLE_TERMS))
    kept_keys = {_job_key(j) for j in kept}
    return [j for j in jobs if _job_key(j) not in kept_keys]


def build_buckets(new_jobs: list[dict], scored: list[dict], config: dict) -> dict[str, list[dict]]:
    buckets = {b: [] for b in BUCKETS}
    seen = set()
    for row in scored:  # rows carry the full job, so they are candidates even if no longer in new_jobs
        key = _job_key(row)
        if key in seen or "scorer-error" in (row.get("flags") or []):
            continue
        seen.add(key)
        buckets[metrics.band(int(row.get("score", 0)))].append(row)
    for job in _hard_filtered(new_jobs, config):
        key = _job_key(job)
        if key not in seen:
            seen.add(key)
            buckets["filtered"].append(job)
    return buckets


def stratified_sample(buckets: dict[str, list[dict]], n: int, seed: int) -> list[dict]:
    """Round-robin across buckets so each is represented; small buckets are exhausted, others fill in."""
    rng = random.Random(seed)
    pools = {b: rng.sample(jobs, len(jobs)) for b, jobs in buckets.items()}
    picked = []
    while len(picked) < n and any(pools.values()):
        for b in BUCKETS:
            if pools[b] and len(picked) < n:
                picked.append(pools[b].pop())
    rng.shuffle(picked)  # don't let row order leak the bucket
    return picked


def write_sheet(jobs: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:  # -sig so Excel shows Hebrew correctly
        w = csv.DictWriter(f, fieldnames=JOB_COLS + LABEL_COLS)
        w.writeheader()
        for j in jobs:
            w.writerow({**{c: j.get(c, "") for c in JOB_COLS}, "job_id": _job_key(j),
                        **{c: "" for c in LABEL_COLS}})


def import_sheet(sheet: Path, out: Path, labelled_by: str) -> int:
    """Convert a filled sheet to golden_set.jsonl. Rows without label_score are skipped."""
    items, skipped = [], 0
    with open(sheet, encoding="utf-8-sig", newline="") as f:
        for lineno, row in enumerate(csv.DictReader(f), start=2):
            raw = (row.get("label_score") or "").strip()
            if not raw:
                skipped += 1
                continue
            try:
                score = int(raw)
                assert 0 <= score <= 10
            except (ValueError, AssertionError):
                raise ValueError(f"row {lineno}: label_score must be an integer 0-10, got {raw!r}")
            lb = (row.get("label_band") or "").strip() or metrics.band(score)
            if lb not in metrics.BANDS:
                raise ValueError(f"row {lineno}: label_band must be one of {metrics.BANDS}, got {lb!r}")
            flags = [x.strip() for x in (row.get("label_flags") or "").replace(";", ",").split(",") if x.strip()]
            items.append({
                **{c: row.get(c, "") for c in JOB_COLS},
                "label_score": score,
                "label_band": lb,
                "label_flags": flags,
                "labelled_by": labelled_by,
                "labelled_at": date.today().isoformat(),
                "notes": row.get("notes", ""),
            })
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    print(f"Imported {len(items)} labelled rows ({skipped} unlabelled skipped) -> {out}")
    return len(items)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Make or import the scorer golden-set labelling sheet.")
    p.add_argument("--n", type=int, default=60, help="jobs to sample (default 60)")
    p.add_argument("--seed", type=int, default=0, help="sampling seed (default 0)")
    p.add_argument("--profile", type=Path, default=ROOT / "profiles" / "omer",
                   help="profile dir for all_scores.jsonl + score_config.json (default profiles/omer)")
    p.add_argument("--jobs", type=Path, default=ROOT / "new_jobs.json", help="jobs file (default new_jobs.json)")
    p.add_argument("--out", type=Path, default=PRIVATE_DIR / "labelling_sheet.csv", help="sheet path to write")
    p.add_argument("--import", dest="import_csv", type=Path, help="filled sheet to convert to the golden set")
    p.add_argument("--golden", type=Path, default=PRIVATE_DIR / "golden_set.jsonl", help="golden set path for --import")
    p.add_argument("--labelled-by", default="omer", help="labeller name recorded on each row (default omer)")
    args = p.parse_args(argv)

    if args.import_csv:
        try:
            import_sheet(args.import_csv, args.golden, args.labelled_by)
        except (OSError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    new_jobs = json.loads(args.jobs.read_text(encoding="utf-8")) if args.jobs.exists() else []
    scores_path = args.profile / "all_scores.jsonl"
    scored = []
    if scores_path.exists():
        with open(scores_path, encoding="utf-8") as f:
            scored = [json.loads(line) for line in f if line.strip()]
    print(f"Loaded {len(new_jobs)} jobs from {args.jobs} and {len(scored)} scored rows from {scores_path}")

    buckets = build_buckets(new_jobs, scored, _load_profile_config(args.profile))
    print("Candidates per bucket: " + ", ".join(f"{b}={len(v)}" for b, v in buckets.items()))
    picked = stratified_sample(buckets, args.n, args.seed)
    if not picked:
        print("Error: no candidate jobs found.", file=sys.stderr)
        return 1
    write_sheet(picked, args.out)
    print(f"Wrote {len(picked)} rows to {args.out} - fill label_score (0-10), optional label_band/label_flags/notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
