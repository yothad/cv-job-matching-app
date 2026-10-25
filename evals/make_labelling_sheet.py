#!/usr/bin/env python3
"""Build a CSV labelling sheet for the scorer golden set, and import it back.

  uv run python evals/make_labelling_sheet.py --n 60
      -> evals/private/labelling_sheet.csv (blank label columns)
  uv run python evals/make_labelling_sheet.py --import evals/private/labelling_sheet.csv
      -> evals/private/golden_set.jsonl
  uv run python evals/make_labelling_sheet.py --n 60 --quick
      -> slim sheet: one L/M/H column + a role excerpt; full jobs kept in a
         sidecar (<sheet>.jobs.jsonl) that --import joins back, so the golden set is unchanged
  uv run python evals/make_labelling_sheet.py --quick --n 100 --mix H=35,M=35,L=30 \\
        --exclude evals/private/golden_set.jsonl --max-per-company 2 --out evals/private/labelling_sheet2.csv
      -> quota sample by Gemini band (H = 7-10, M = 5-6, L = 0-4); a short quota is filled
         from the other groups in their mix ratio. Import it with --import ... --append.
  uv run python evals/make_labelling_sheet.py --refresh-sections
      -> re-fill role_description / responsibilities / requirements / ats on the golden set
         from the current new_jobs.json (after a re-collect)

Default sampling is stratified across the Gemini score bands in profiles/<p>/all_scores.jsonl
plus jobs from new_jobs.json that score.py's hard filters drop before Gemini.
Gemini's score and band are NOT written to the sheet or sidecar and rows are shuffled, so the
human label stays blind.
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

from ats.utils import SECTION_CHARS, SECTION_KEYS, flatten_text, job_sections, trim_role  # noqa: E402
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
# Stored in the sidecar and golden set, not shown on the full sheet (too long for a cell).
EXTRA_COLS = list(SECTION_KEYS) + ["ats"]
LABEL_COLS = ["label_score", "label_band", "label_flags", "notes"]
BUCKETS = metrics.BANDS + ["filtered"]

# --quick: label a band, not a score. Each letter maps to a score inside one repo band
# (0-4 / 5-6 / 7-8), so the 3-band low/mid/high split stays derivable from label_score.
QUICK_SCORES = {"l": 2, "low": 2, "m": 5, "mid": 5, "h": 8, "high": 8}
QUICK_COLS = ["job_id", "quick_band", "title", "company", "location", "excerpt", "notes"]
EXCERPT_CHARS = 600

# --mix groups: Gemini's band as a loose stand-in for the human band, used only for sampling.
MIX_GROUPS = {"H": ["9-10", "7-8"], "M": ["5-6"], "L": ["0-4"]}


def _hard_filtered(jobs: list[dict], config: dict) -> list[dict]:
    """Jobs score.py drops before Gemini (location, company, title deny/allow lists)."""
    kept, _ = _location_prefilter(jobs)
    kept, _ = _company_filter(kept, config.get("skip_companies", []))
    kept, _ = _title_prefilter(kept, config.get("skip_title_terms", _SKIP_TITLE_TERMS))
    kept, _ = _title_allowlist_filter(kept, config.get("keep_title_terms", _KEEP_TITLE_TERMS))
    kept_keys = {_job_key(j) for j in kept}
    return [j for j in jobs if _job_key(j) not in kept_keys]


def build_buckets(new_jobs: list[dict], scored: list[dict], config: dict,
                  exclude: set[str] | None = None) -> dict[str, list[dict]]:
    exclude = exclude or set()
    buckets = {b: [] for b in BUCKETS}
    seen = set(exclude)
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


def _capped_pools(pools: dict[str, list[dict]], order: list[str], max_per_company: int) -> dict[str, list[dict]]:
    """Drop jobs past max_per_company per company (0 = no cap), counting across all pools.

    Pools earlier in `order` claim company slots first, so the scarce group keeps its jobs.
    """
    if max_per_company <= 0:
        return pools
    counts: dict[str, int] = {}
    out = {}
    for name in order:
        kept = []
        for j in pools.get(name, []):
            c = (j.get("company") or "").strip().lower()
            if counts.get(c, 0) < max_per_company:
                counts[c] = counts.get(c, 0) + 1
                kept.append(j)
        out[name] = kept
    return out


def stratified_sample(buckets: dict[str, list[dict]], n: int, seed: int, max_per_company: int = 0) -> list[dict]:
    """Round-robin across buckets so each is represented; small buckets are exhausted, others fill in."""
    rng = random.Random(seed)
    pools = {b: rng.sample(jobs, len(jobs)) for b, jobs in buckets.items()}
    pools = _capped_pools(pools, BUCKETS, max_per_company)
    picked = []
    while len(picked) < n and any(pools.values()):
        for b in BUCKETS:
            if pools[b] and len(picked) < n:
                picked.append(pools[b].pop())
    rng.shuffle(picked)  # don't let row order leak the bucket
    return picked


def parse_mix(raw: str) -> dict[str, float]:
    """'H=35,M=35,L=30' -> {'H': 35.0, 'M': 35.0, 'L': 30.0}."""
    mix = {}
    for part in raw.split(","):
        name, _, pct = part.partition("=")
        name = name.strip().upper()
        if name not in MIX_GROUPS:
            raise ValueError(f"--mix group must be one of {list(MIX_GROUPS)}, got {name!r}")
        try:
            mix[name] = float(pct)
        except ValueError:
            raise ValueError(f"--mix share for {name} must be a number, got {pct!r}")
    if not mix or sum(mix.values()) <= 0:
        raise ValueError("--mix needs at least one positive share")
    return mix


def allocate(n: int, mix: dict[str, float], available: dict[str, int]) -> dict[str, int]:
    """Quotas per group: n split by mix share, each capped by what is available. A short group's
    remainder goes to the groups that still have jobs, in their mix ratio, until n is reached or
    every group is exhausted."""
    quotas = {g: 0 for g in mix}
    left = n
    while left > 0:
        open_groups = {g: s for g, s in mix.items() if quotas[g] < available.get(g, 0) and s > 0}
        if not open_groups:
            break
        total = sum(open_groups.values())
        # largest-remainder rounding of this round's share
        raw = {g: left * s / total for g, s in open_groups.items()}
        give = {g: int(v) for g, v in raw.items()}
        for g in sorted(raw, key=lambda g: raw[g] - give[g], reverse=True)[: left - sum(give.values())]:
            give[g] += 1
        moved = 0
        for g, k in give.items():
            k = min(k, available[g] - quotas[g])
            quotas[g] += k
            moved += k
        if moved == 0:
            break
        left -= moved
    return quotas


def mix_sample(buckets: dict[str, list[dict]], mix: dict[str, float], n: int, seed: int,
               max_per_company: int = 0) -> tuple[list[dict], dict[str, int]]:
    """Quota sample by Gemini band group (MIX_GROUPS). Returns (picked, quotas)."""
    rng = random.Random(seed)
    pools = {g: [j for b in MIX_GROUPS[g] for j in buckets.get(b, [])] for g in mix}
    pools = {g: rng.sample(jobs, len(jobs)) for g, jobs in pools.items()}
    order = sorted(pools, key=lambda g: len(pools[g]))  # scarcest group claims company slots first
    pools = _capped_pools(pools, order, max_per_company)
    quotas = allocate(n, mix, {g: len(p) for g, p in pools.items()})
    picked = [j for g, k in quotas.items() for j in pools[g][:k]]
    rng.shuffle(picked)  # don't let row order leak the group
    return picked, quotas


def load_keys(paths: list[Path]) -> set[str]:
    """job_ids from golden-set / sidecar .jsonl files or labelling-sheet .csv files."""
    keys = set()
    for path in paths:
        if path.suffix == ".csv":
            with open(path, encoding="utf-8-sig", newline="") as f:
                keys |= {r["job_id"] for r in csv.DictReader(f) if r.get("job_id")}
        else:
            with open(path, encoding="utf-8") as f:
                for line in filter(str.strip, f):
                    item = json.loads(line)
                    keys.add(item.get("job_id") or _job_key(item))
    return keys


def fill_sections(job: dict, fresh: dict[str, dict]) -> dict:
    """job + role_description / responsibilities / requirements / ats.

    Taken from the freshest copy of the job in new_jobs.json (`fresh`, keyed by _job_key) when it
    has them; else kept from the job itself; else split from the stored description.
    """
    src = fresh.get(job.get("job_id") or _job_key(job)) or {}
    out = dict(job)
    if any(src.get(k) for k in SECTION_KEYS):
        out.update({k: src.get(k, "") for k in SECTION_KEYS})
    elif not any(job.get(k) for k in SECTION_KEYS):
        out.update(job_sections(job.get("description") or ""))
    # Re-trim: jobs collected before the role-start fixes still carry the company pitch
    # (e.g. a whole Comeet "Description" section). Idempotent on already-trimmed text.
    if out.get("role_description"):
        out["role_description"] = trim_role(flatten_text(out["role_description"]))[:SECTION_CHARS]
    out["ats"] = job.get("ats") or src.get("ats") or ""
    return out


def _row(job: dict) -> dict:
    row = {**{c: job.get(c, "") for c in JOB_COLS + EXTRA_COLS}, "job_id": job.get("job_id") or _job_key(job)}
    if job.get("recheck"):
        row["recheck"] = True  # sidecar only - the sheet never shows it
    return row


def band3(label_band: str) -> str:
    """Repo band -> the experiment's low / mid / high (L / M / H)."""
    return {"0-4": "L", "5-6": "M"}.get(label_band, "H")


def pick_recheck(golden: list[dict], k: int, seed: int) -> list[dict]:
    """k already-labelled Israeli jobs, spread evenly over the human L / M / H bands, to be
    labelled again blind - a self-consistency check. Labels are stripped; rows are marked recheck."""
    israeli, _ = _location_prefilter(golden)
    rng = random.Random(seed)
    pools = {b: [] for b in "LMH"}
    for g in israeli:
        pools[band3(metrics.label_band(g))].append(g)
    pools = {b: rng.sample(v, len(v)) for b, v in pools.items()}
    picked = []
    while len(picked) < k and any(pools.values()):
        for b in "LMH":
            if pools[b] and len(picked) < k:
                picked.append({**_row(pools[b].pop()), "recheck": True})
    return picked


def write_sheet(jobs: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:  # -sig so Excel shows Hebrew correctly
        w = csv.DictWriter(f, fieldnames=JOB_COLS + LABEL_COLS)
        w.writeheader()
        for j in jobs:
            w.writerow({**{c: j.get(c, "") for c in JOB_COLS}, "job_id": _job_key(j),
                        **{c: "" for c in LABEL_COLS}})


def _sidecar(sheet: Path) -> Path:
    return sheet.with_suffix(".jobs.jsonl")


def write_quick_sheet(jobs: list[dict], out: Path) -> None:
    """Slim sheet for fast band labelling. Full job rows go to the sidecar, keyed by job_id.

    The excerpt is the start of role_description (company pitch skipped); jobs without it
    fall back to the description.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(_sidecar(out), "w", encoding="utf-8") as f:
        for j in jobs:
            f.write(json.dumps(_row(j), ensure_ascii=False) + "\n")
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=QUICK_COLS)
        w.writeheader()
        for j in jobs:
            text = j.get("role_description") or j.get("description") or ""
            excerpt = " ".join(str(text).split())[:EXCERPT_CHARS]
            w.writerow({"job_id": _job_key(j), "quick_band": "", "title": j.get("title", ""),
                        "company": j.get("company", ""), "location": j.get("location", ""),
                        "excerpt": excerpt, "notes": ""})


def _quick_score(raw: str, where: str) -> int:
    score = QUICK_SCORES.get(raw.strip().lower())
    if score is None:
        raise ValueError(f"{where}: quick_band must be L, M or H, got {raw!r}")
    return score


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_jsonl(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def import_sheet(sheet: Path, out: Path, labelled_by: str, fresh: dict[str, dict] | None = None,
                 append: bool = False, batch: str | None = None) -> int:
    """Convert a filled sheet to golden_set.jsonl. Rows without a label are skipped.

    A --quick sheet (quick_band column) is labelled L/M/H and its full job rows come from the sidecar.
    With append, rows are added to an existing golden set; job_ids already in it are skipped.
    Re-check rows (marked in the sidecar) never touch the golden set: they go to recheck.jsonl next
    to it and are compared with the original labels. With batch, new rows get that batch and,
    when appending, existing rows without one get batch "1".
    """
    fresh = fresh or {}
    items, rechecks, skipped = [], [], 0
    with open(sheet, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        quick = "quick_band" in (reader.fieldnames or [])
        full = {}
        if quick:
            if not _sidecar(sheet).exists():
                raise ValueError(f"{_sidecar(sheet)} not found - it holds the full jobs for a --quick sheet")
            full = {j["job_id"]: j for j in _read_jsonl(_sidecar(sheet))}
        for lineno, row in enumerate(reader, start=2):
            if quick:
                raw_band = (row.get("quick_band") or "").strip()
                if not raw_band:
                    skipped += 1
                    continue
                if row.get("job_id") not in full:
                    raise ValueError(f"row {lineno}: job_id {row.get('job_id')!r} not in {_sidecar(sheet).name}")
                row = {**full[row["job_id"]], "notes": row.get("notes", ""),
                       "label_score": str(_quick_score(raw_band, f"row {lineno}"))}
            raw = (row.get("label_score") or "").strip()
            if not raw:
                skipped += 1
                continue
            score, lb = metrics.parse_label(raw, row.get("label_band"), f"row {lineno}")
            flags = [x.strip() for x in (row.get("label_flags") or "").replace(";", ",").split(",") if x.strip()]
            item = {
                **_row(fill_sections(row, fresh)),
                "label_score": score,
                "label_band": lb,
                "label_flags": flags,
                "labelled_by": labelled_by,
                "labelled_at": date.today().isoformat(),
                "notes": row.get("notes", ""),
            }
            if row.get("recheck"):
                rechecks.append(item)
                continue
            item.pop("recheck", None)
            if batch:
                item["batch"] = batch
            items.append(item)
    existing, dupes = [], 0
    if out.exists() and (append or rechecks):
        existing = _read_jsonl(out)
    if append:
        have = {e.get("job_id") for e in existing}
        dupes = sum(it["job_id"] in have for it in items)
        items = [it for it in items if it["job_id"] not in have]
        if batch:
            existing = [e if e.get("batch") else {**e, "batch": "1"} for e in existing]
        _write_jsonl(out, existing + items)
    else:
        _write_jsonl(out, items)
    extra = f", {dupes} already in the golden set skipped, {len(existing) + len(items)} total" if append else ""
    print(f"Imported {len(items)} labelled rows ({skipped} unlabelled skipped{extra}) -> {out}")
    if rechecks:
        report_recheck(rechecks, existing, out.parent / "recheck.jsonl")
    return len(items)


def report_recheck(rechecks: list[dict], golden: list[dict], path: Path) -> int:
    """Write re-check labels next to the originals and print the self-agreement. Returns matches."""
    orig = {g.get("job_id"): g for g in golden}
    rows = []
    for r in rechecks:
        o = orig.get(r["job_id"])
        if not o:
            continue
        rows.append({"job_id": r["job_id"], "company": r.get("company", ""), "title": r.get("title", ""),
                     "original": band3(metrics.label_band(o)), "recheck": band3(r["label_band"]),
                     "original_batch": o.get("batch", ""), "notes": r.get("notes", "")})
    _write_jsonl(path, rows)
    same = sum(x["original"] == x["recheck"] for x in rows)
    print(f"Re-check: you agreed with your first label on {same}/{len(rows)} jobs -> {path}")
    for x in rows:
        if x["original"] != x["recheck"]:
            print(f"  changed {x['original']} -> {x['recheck']}: {x['company']} - {x['title']}")
    return same


def refresh_sections(golden: Path, fresh: dict[str, dict]) -> int:
    """Re-fill the section fields of every golden item from `fresh`; returns how many came from it."""
    items = _read_jsonl(golden)
    from_fresh = sum(any(fresh.get(it.get("job_id"), {}).get(k) for k in SECTION_KEYS) for it in items)
    refreshed = []
    for it in items:
        if any(fresh.get(it.get("job_id"), {}).get(k) for k in SECTION_KEYS):
            it = {**it, **{k: "" for k in SECTION_KEYS}}  # let fill_sections take the fresh copy
        refreshed.append(fill_sections(it, fresh))
    _write_jsonl(golden, refreshed)
    print(f"Refreshed sections on {len(items)} golden rows ({from_fresh} from the jobs file, "
          f"{len(items) - from_fresh} split from the stored description) -> {golden}")
    return from_fresh


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Make or import the scorer golden-set labelling sheet.")
    p.add_argument("--n", type=int, default=60, help="jobs to sample (default 60)")
    p.add_argument("--seed", type=int, default=0, help="sampling seed (default 0)")
    p.add_argument("--profile", type=Path, default=ROOT / "profiles" / "yotam",
                   help="profile dir for all_scores.jsonl + score_config.json (default profiles/yotam)")
    p.add_argument("--jobs", type=Path, default=ROOT / "new_jobs.json", help="jobs file (default new_jobs.json)")
    p.add_argument("--out", type=Path, default=PRIVATE_DIR / "labelling_sheet.csv", help="sheet path to write")
    p.add_argument("--import", dest="import_csv", type=Path, help="filled sheet to convert to the golden set")
    p.add_argument("--append", action="store_true", help="with --import: add to the golden set instead of replacing it")
    p.add_argument("--refresh-sections", action="store_true",
                   help="re-fill role/requirements fields on the golden set from --jobs, then exit")
    p.add_argument("--golden", type=Path, default=PRIVATE_DIR / "golden_set.jsonl", help="golden set path for --import")
    p.add_argument("--labelled-by", default="yotam", help="labeller name recorded on each row (default yotam)")
    p.add_argument("--quick", action="store_true",
                   help="slim sheet: label L/M/H in quick_band, role excerpt instead of the full description")
    p.add_argument("--mix", help="quota sample by Gemini band group, e.g. H=35,M=35,L=30 (H=7-10, M=5-6, L=0-4)")
    p.add_argument("--exclude", type=Path, action="append", default=[],
                   help="skip job_ids in this golden set / sidecar .jsonl or sheet .csv (repeatable)")
    p.add_argument("--max-per-company", type=int, default=0, help="at most this many jobs per company (0 = no cap)")
    p.add_argument("--recheck", type=int, default=0,
                   help="also mix in this many already-labelled jobs from --golden to label again blind")
    p.add_argument("--batch", help="with --import: batch name for the new rows (existing rows get '1' when appending)")
    args = p.parse_args(argv)

    new_jobs = json.loads(args.jobs.read_text(encoding="utf-8")) if args.jobs.exists() else []
    fresh = {_job_key(j): j for j in new_jobs}

    if args.refresh_sections:
        if not args.golden.exists():
            print(f"Error: {args.golden} not found", file=sys.stderr)
            return 1
        refresh_sections(args.golden, fresh)
        return 0

    if args.import_csv:
        try:
            import_sheet(args.import_csv, args.golden, args.labelled_by, fresh, args.append, args.batch)
        except (OSError, ValueError) as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        return 0

    try:
        mix = parse_mix(args.mix) if args.mix else None
        exclude = load_keys(args.exclude)
    except (OSError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    scores_path = args.profile / "all_scores.jsonl"
    scored = _read_jsonl(scores_path) if scores_path.exists() else []
    print(f"Loaded {len(new_jobs)} jobs from {args.jobs} and {len(scored)} scored rows from {scores_path}"
          + (f"; excluding {len(exclude)} job_ids" if exclude else ""))

    buckets = build_buckets(new_jobs, scored, _load_profile_config(args.profile), exclude)
    if mix:
        picked, quotas = mix_sample(buckets, mix, args.n, args.seed, args.max_per_company)
        total = sum(quotas.values()) or 1
        print("Quotas by Gemini group: " + ", ".join(
            f"{g}={k} ({k * 100 // total}%)" for g, k in quotas.items()))
        if len(picked) < args.n:
            print(f"Only {len(picked)} candidates available for --n {args.n}")
    else:
        print("Candidates per bucket: " + ", ".join(f"{b}={len(v)}" for b, v in buckets.items()))
        picked = stratified_sample(buckets, args.n, args.seed, args.max_per_company)
    if not picked:
        print("Error: no candidate jobs found.", file=sys.stderr)
        return 1
    picked = [fill_sections(j, fresh) for j in picked]
    if args.recheck:
        if not args.golden.exists():
            print(f"Error: --recheck needs {args.golden}", file=sys.stderr)
            return 1
        rechecks = [fill_sections(j, fresh) for j in pick_recheck(_read_jsonl(args.golden), args.recheck, args.seed)]
        picked = picked + rechecks
        random.Random(args.seed).shuffle(picked)  # re-check rows must not cluster at the end
        print(f"Mixed in {len(rechecks)} already-labelled jobs to re-check blind")
    if args.quick:
        write_quick_sheet(picked, args.out)
        print(f"Wrote {len(picked)} rows to {args.out} (+ {_sidecar(args.out).name}) - fill quick_band with L/M/H")
    else:
        write_sheet(picked, args.out)
        print(f"Wrote {len(picked)} rows to {args.out} - fill label_score (0-10), optional label_band/label_flags/notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
