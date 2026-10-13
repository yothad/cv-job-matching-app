#!/usr/bin/env python3
"""Scorer eval: re-score the human-labelled golden set through the production
scoring path and report band accuracy, MAE, hard-filter recall and a confusion
table. See evals/README.md for the workflow.

Usage:
  uv run python evals/run_eval.py                         # score + print metrics
  uv run python evals/run_eval.py --runs 3                # pass@1 vs pass@3
  uv run python evals/run_eval.py --baseline              # compare, exit 1 on regression
  uv run python evals/run_eval.py --write-baseline        # record a new baseline
"""

import argparse
import hashlib
import inspect
import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from evals import metrics  # noqa: E402
from matcher.gemini_scorer import MODELS, build_batch_prompt  # noqa: E402
from score import _load_profile_config, _resolve_cvs, _score_jobs_batched  # noqa: E402

PRIVATE_DIR = ROOT / "evals" / "private"
DEFAULT_GOLDEN = Path(os.environ.get("EVAL_GOLDEN_SET", PRIVATE_DIR / "golden_set.jsonl"))
DEFAULT_BASELINE = Path(os.environ.get("EVAL_BASELINE", PRIVATE_DIR / "baseline.json"))
DEFAULT_PROFILE = ROOT / "profiles" / "omer"

# Allowed drop vs the baseline before --baseline fails. Written into the baseline
# file so Omer can tune it there once pass@1 vs pass@3 shows the real noise floor.
DEFAULT_TOLERANCE = {"band_accuracy": 0.05, "mae": 0.5, "hard_filter_recall": 0.0}
# Max share of scorer-error results (over jobs x runs) before the run fails outright:
# a dead model or key turns every job into scorer-error and would otherwise leave no
# metrics to compare. Override with --max-error-share or tolerance.scorer_error_share.
DEFAULT_MAX_ERROR_SHARE = 0.10
# Metrics where a higher value is better; the rest (mae) are lower-is-better.
HIGHER_IS_BETTER = {"band_accuracy", "hard_filter_recall"}


def load_golden(path: Path) -> list[dict]:
    """Read and validate the golden set; raises ValueError naming the bad line."""
    items = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, start=1):
            if not line.strip():
                continue
            where = f"{path.name} line {lineno}"
            try:
                item = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{where}: invalid JSON ({e.msg})")
            if not isinstance(item, dict):
                raise ValueError(f"{where}: expected a JSON object")
            metrics.parse_label(item.get("label_score"), item.get("label_band"), where)
            items.append(item)
    return items


def _model_name() -> str:
    return ",".join(MODELS)  # the whole cascade - a fallback model may have scored some jobs


def _prompt_hash(profile_md: str, cv_default: str, cv_lead: str) -> str:
    h = hashlib.sha256()
    for part in (inspect.getsource(build_batch_prompt), profile_md, cv_default, cv_lead):
        h.update(part.encode("utf-8"))
    return h.hexdigest()[:12]


def score_golden(golden: list[dict], profile_dir: Path, client) -> list[dict]:
    """One scoring run. Mirrors score.py: same CV routing, batch size and scorer call."""
    profile_md = (profile_dir / "profile.md").read_text(encoding="utf-8")
    config = _load_profile_config(profile_dir)
    cv_default, cv_lead = _resolve_cvs(profile_dir, config, profile_dir.name)
    lead_terms = [t.lower() for t in config.get("lead_title_terms", [])]

    if lead_terms and cv_lead != cv_default:
        is_lead = [any(t in (g.get("title") or "").lower() for t in lead_terms) for g in golden]
        groups = [([i for i, l in enumerate(is_lead) if l], cv_lead),
                  ([i for i, l in enumerate(is_lead) if not l], cv_default)]
    else:
        groups = [(list(range(len(golden))), cv_default)]

    results = [None] * len(golden)
    for idx, cv in groups:
        if not idx:
            continue
        scored = _score_jobs_batched([golden[i] for i in idx], profile_md, cv, client, "eval")
        if len(scored) != len(idx):
            raise RuntimeError(f"quota exhausted after {len(scored)}/{len(idx)} jobs - partial eval is not comparable")
        for i, s in zip(idx, scored):
            results[i] = s
    return results


def compute_report(golden: list[dict], runs: list[list[dict]]) -> dict:
    """runs[r][i] = scorer result for golden[i] on run r."""
    pairs, errors = [], 0
    per_job = [[] for _ in golden]
    for run in runs:
        for i, (g, res) in enumerate(zip(golden, run)):
            # scorer-error items are infra noise, not scoring - excluded from every metric
            if "scorer-error" in res.get("flags", []):
                errors += 1
                continue
            pairs.append((g, res["score"]))
            per_job[i].append(metrics.label_band(g) == metrics.band(res["score"]))
    return {
        "n_jobs": len(golden),
        "runs": len(runs),
        "scorer_errors": errors,
        "band_accuracy": metrics.band_accuracy(pairs),
        "mae": metrics.mae(pairs),
        "hard_filter_recall": metrics.hard_filter_recall(pairs),
        "hard_filter_n": sum(metrics.is_hard_filter(g) for g in golden),
        "confusion": metrics.confusion(pairs),
        **metrics.pass_at_k(per_job),
    }


def _fmt(v) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def print_report(rep: dict) -> None:
    k = rep["runs"]
    print(f"\n=== Scorer eval - {rep['n_jobs']} jobs x {k} run(s) ===")
    print(f"Band accuracy:       {_fmt(rep['band_accuracy'])}")
    print(f"MAE (0-10):          {_fmt(rep['mae'])}")
    print(f"Hard-filter recall:  {_fmt(rep['hard_filter_recall'])}  ({rep['hard_filter_n']} hard-filter jobs)")
    print(f"Scorer errors:       {rep['scorer_errors']} (excluded)")
    if k > 1:
        print(f"pass@1 / pass@{k} / pass^{k}: {_fmt(rep['pass@1'])} / {_fmt(rep['pass@k'])} / {_fmt(rep['pass^k'])}")
    print("\nConfusion (rows = human band, cols = Gemini band):")
    print("        " + "".join(f"{b:>7}" for b in metrics.BANDS))
    for h in metrics.BANDS:
        print(f"{h:>7} " + "".join(f"{rep['confusion'][h][p]:>7}" for p in metrics.BANDS))


def compare_to_baseline(rep: dict, baseline: dict) -> list[str]:
    """Return a list of regression messages (empty = pass)."""
    tol = {**DEFAULT_TOLERANCE, **baseline.get("tolerance", {})}
    tol.pop("scorer_error_share", None)  # not a metric - checked by check_error_share
    base = baseline["metrics"]
    problems = []
    for name, t in tol.items():
        old, new = base.get(name), rep.get(name)
        if old is None:
            continue
        if new is None:
            # the baseline measured it, this run could not - never a silent pass
            print(f"  {name}: baseline {old:.3f} -> now n/a - REGRESSION")
            problems.append(f"{name} {old:.3f} -> n/a")
            continue
        regressed = new < old - t if name in HIGHER_IS_BETTER else new > old + t
        status = "REGRESSION" if regressed else "ok"
        print(f"  {name}: baseline {old:.3f} -> now {new:.3f} (tolerance {t}) - {status}")
        if regressed:
            problems.append(f"{name} {old:.3f} -> {new:.3f}")
    return problems


def load_baseline(path: Path) -> dict:
    """Read a baseline; raise ValueError unless it holds a measured band_accuracy and every gated metric key."""
    try:
        baseline = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON ({e})") from e
    m = baseline.get("metrics") if isinstance(baseline, dict) else None
    if not isinstance(m, dict):
        raise ValueError("no 'metrics' object")
    missing = [k for k in DEFAULT_TOLERANCE if k not in m]
    if missing:
        raise ValueError(f"metrics missing {', '.join(missing)}")
    if m["band_accuracy"] is None:
        raise ValueError("band_accuracy is null - the baseline measured nothing")
    return baseline


def check_error_share(rep: dict, max_share: float) -> str | None:
    """Return a failure message if too many results were scorer-error, else None."""
    total = rep["n_jobs"] * rep["runs"]
    share = rep["scorer_errors"] / total if total else 0.0
    if share > max_share:
        return (f"{rep['scorer_errors']}/{total} results were scorer-error ({share:.0%} > {max_share:.0%}) - "
                "the model or API key is likely broken; metrics are not trustworthy")
    return None


def _make_client():
    load_dotenv(ROOT / ".env")
    load_dotenv(DEFAULT_PROFILE / ".env", override=True)
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not set.", file=sys.stderr)
        sys.exit(2)
    from google import genai
    return genai.Client(api_key=api_key)


def main(argv: list[str] | None = None, client=None) -> int:
    p = argparse.ArgumentParser(description="Re-score the golden set and report scorer metrics.")
    p.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN,
                   help=f"golden set JSONL (default {DEFAULT_GOLDEN}, env EVAL_GOLDEN_SET)")
    p.add_argument("--profile", type=Path, default=DEFAULT_PROFILE,
                   help="profile dir with profile.md, cv.md, score_config.json (default profiles/omer)")
    p.add_argument("--runs", type=int, default=1, help="score every job k times for pass@1 vs pass@k (default 1)")
    p.add_argument("--baseline", type=Path, nargs="?", const=DEFAULT_BASELINE,
                   help=f"compare to a baseline file and exit 1 on regression (default {DEFAULT_BASELINE}, env EVAL_BASELINE)")
    p.add_argument("--write-baseline", type=Path, nargs="?", const=DEFAULT_BASELINE,
                   help="write this run's metrics as the new baseline file")
    p.add_argument("--max-error-share", type=float,
                   help=f"fail if more than this share of results are scorer-error (default {DEFAULT_MAX_ERROR_SHARE}, "
                        "or tolerance.scorer_error_share in the --baseline file)")
    args = p.parse_args(argv)
    if args.runs < 1:
        print("Error: --runs must be at least 1.", file=sys.stderr)
        return 2

    if not args.golden.exists():
        print(f"Error: golden set not found at {args.golden}. Label one first - see evals/README.md.", file=sys.stderr)
        return 2
    if args.baseline and not args.baseline.exists():
        print(f"Error: baseline not found at {args.baseline}. Record one with --write-baseline.", file=sys.stderr)
        return 2
    if not (args.profile / "profile.md").exists():
        print(f"Error: no profile.md in {args.profile}.", file=sys.stderr)
        return 2
    baseline = {}
    if args.baseline:
        try:
            baseline = load_baseline(args.baseline)
        except ValueError as e:
            print(f"Error: bad baseline {args.baseline} - {e}", file=sys.stderr)
            return 2

    try:
        golden = load_golden(args.golden)
    except ValueError as e:
        print(f"Error: bad golden set - {e}", file=sys.stderr)
        return 2
    if not golden:
        print(f"Error: golden set {args.golden} is empty.", file=sys.stderr)
        return 2
    print(f"Loaded {len(golden)} golden jobs from {args.golden}")
    if client is None:
        client = _make_client()

    runs = []
    for r in range(args.runs):
        print(f"--- run {r + 1}/{args.runs} ---")
        try:
            runs.append(score_golden(golden, args.profile, client))
        except Exception as e:
            print(f"Error: scoring failed on run {r + 1}: {e}", file=sys.stderr)
            return 1

    rep = compute_report(golden, runs)
    print_report(rep)

    max_share = args.max_error_share
    if max_share is None:
        max_share = baseline.get("tolerance", {}).get("scorer_error_share", DEFAULT_MAX_ERROR_SHARE)
    err = check_error_share(rep, max_share)
    if err:
        # also blocks --write-baseline from recording an all-error run
        print(f"FAIL - {err}", file=sys.stderr)
        return 1

    exit_code = 0
    if args.baseline:
        print(f"\nComparing to baseline {args.baseline}:")
        problems = compare_to_baseline(rep, baseline)
        if problems:
            print(f"FAIL - regression beyond tolerance: {'; '.join(problems)}", file=sys.stderr)
            exit_code = 1
        else:
            print("PASS - no regression beyond tolerance")

    if args.write_baseline and exit_code:
        print("Not writing a baseline from a run that failed the gate.", file=sys.stderr)
    elif args.write_baseline and rep["band_accuracy"] is None:
        print("Error: nothing was measured (band_accuracy n/a) - refusing to write a baseline.", file=sys.stderr)
        exit_code = 1
    elif args.write_baseline:
        profile_md = (args.profile / "profile.md").read_text(encoding="utf-8")
        cv_default, cv_lead = _resolve_cvs(args.profile, _load_profile_config(args.profile), args.profile.name)
        # keep a hand-tuned tolerance when re-recording over an existing baseline
        tolerance = DEFAULT_TOLERANCE
        if args.write_baseline.exists():
            tolerance = json.loads(args.write_baseline.read_text(encoding="utf-8")).get("tolerance", tolerance)
        record = {
            "date": date.today().isoformat(),
            "model": _model_name(),
            "prompt_hash": _prompt_hash(profile_md, cv_default, cv_lead),
            "n_jobs": rep["n_jobs"],
            "runs": rep["runs"],
            "metrics": {k: rep[k] for k in ("band_accuracy", "mae", "hard_filter_recall", "pass@1", "pass@k", "pass^k")},
            "tolerance": tolerance,
            "reason": "",
        }
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote baseline to {args.write_baseline} - fill in 'reason' before relying on it.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
