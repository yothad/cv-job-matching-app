"""
Careers recovery queue: rank the recoverable "no careers page" companies and
print the next N that are not yet wired - so we can work them in batches.

Reads the probe snapshot (careers_recovery.json, produced by
scripts/probe_no_careers.py --> re-run it to refresh) and the live companies.json.
Companies already wired (skip_reason=manual_verified, or a resolved ATS) drop out
automatically, so "next N" always returns fresh targets.

Buckets (by probe confidence):
  A  conf 4-5  careers URL / ATS embed found -> directly wireable
  B  conf 2-3  site live, careers exists but needs a manual click for the URL
  C  conf 1    redirects / parked -> low confidence, long tail
(conf 0 = dead/defunct, excluded.)

By default shows Israel-relevant, non-acquired companies ranked A -> B -> C.

Run: uv run python3 scripts/careers_queue.py [--n 50] [--bucket A|B|C] [--all] [--json]
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

SNAP = Path("careers_recovery.json")
COMPANIES = Path("companies.json")
# US-centric VCs whose companies rarely have an Israel office relevant to Yotam
US_VC = {"a16z", "Abstract Ventures", "Accel", "Bain Capital Ventures",
         "Boldstart", "Greylock", "Bessemer"}
RANK = {"A": 0, "B": 1, "C": 2}


def bucket_of(conf: int) -> str | None:
    if conf >= 4:
        return "A"
    if conf >= 2:
        return "B"
    if conf == 1:
        return "C"
    return None  # conf 0 = dead


def _base(u: str) -> str:
    if not u:
        return ""
    h = urlparse(u if u.startswith("http") else "http://" + u).netloc.replace("www.", "")
    p = h.split(".")
    return ".".join(p[-2:]) if len(p) >= 2 else h


def wired_names() -> set[str]:
    rows = json.loads(COMPANIES.read_text(encoding="utf-8"))
    out = set()
    for e in rows:
        if e.get("skip_reason") == "manual_verified":
            out.add(e["name"])
        elif (e.get("ats") or "").lower() not in ("", "unknown"):
            out.add(e["name"])
    return out


def select(args) -> list[dict]:
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    wired = wired_names()
    rows = []
    for r in snap:
        bucket = bucket_of(r.get("conf", 0))
        if not bucket or r["name"] in wired:
            continue
        acquired = bool(r.get("careers_url") and r.get("website")
                        and _base(r["careers_url"]) != _base(r["website"]))
        il = r.get("vc") not in US_VC
        if not args.all and (not il or acquired):
            continue
        if args.bucket and bucket != args.bucket:
            continue
        rows.append({**r, "bucket": bucket, "acquired": acquired, "il_relevant": il})
    rows.sort(key=lambda r: (RANK[r["bucket"]], -r["conf"], r.get("tier") or 9, r["name"]))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=50, help="how many to show (default 50)")
    ap.add_argument("--bucket", choices=["A", "B", "C"], help="filter to one bucket")
    ap.add_argument("--all", action="store_true", help="include US-VC + acquired-redirect companies")
    ap.add_argument("--json", action="store_true", help="emit JSON")
    args = ap.parse_args()

    rows = select(args)
    from collections import Counter
    remaining = Counter(r["bucket"] for r in rows)
    shown = rows[:args.n]

    if args.json:
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        return

    print(f"Not-yet-wired remaining: A={remaining['A']} B={remaining['B']} "
          f"C={remaining['C']}  (showing {len(shown)} of {len(rows)})\n")
    print(f"{'#':>3} {'B':>1} {'cf':>2} {'vc_t':>4}  {'company':26} {'VC':16} URL/website")
    for i, r in enumerate(shown, 1):
        url = r.get("careers_url") or r.get("website") or ""
        print(f"{i:>3} {r['bucket']:>1} {r['conf']:>2} {str(r.get('tier') or '?'):>4}  "
              f"{r['name'][:26]:26} {str(r.get('vc'))[:16]:16} {url[:46]}")


if __name__ == "__main__":
    main()
