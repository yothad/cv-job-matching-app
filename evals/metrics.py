"""Pure metric functions for the scorer eval. No I/O.

Vocabulary follows the ECC eval-harness skill (MIT): pass@k = at least one of k
runs correct, pass^k = all k runs correct.
"""

BANDS = ["9-10", "7-8", "5-6", "0-4"]

# Human label flags that mean "this job must never reach the digest" (score <= 4).
HARD_FILTER_FLAGS = {"dealbreaker-location", "non-ds"}


def band(score: int) -> str:
    if score >= 9:
        return "9-10"
    if score >= 7:
        return "7-8"
    if score >= 5:
        return "5-6"
    return "0-4"


def label_band(item: dict) -> str:
    """The human band: explicit label_band if set, else derived from label_score."""
    return item.get("label_band") or band(int(item["label_score"]))


def is_hard_filter(item: dict) -> bool:
    return any(f.strip().lower() in HARD_FILTER_FLAGS for f in item.get("label_flags") or [])


def band_accuracy(pairs: list[tuple[dict, int]]) -> float | None:
    """pairs = [(golden_item, predicted_score)]. Fraction in the same band."""
    if not pairs:
        return None
    return sum(label_band(g) == band(p) for g, p in pairs) / len(pairs)


def mae(pairs: list[tuple[dict, int]]) -> float | None:
    if not pairs:
        return None
    return sum(abs(int(g["label_score"]) - p) for g, p in pairs) / len(pairs)


def hard_filter_recall(pairs: list[tuple[dict, int]]) -> float | None:
    """Of the human-marked hard-filter jobs, the fraction Gemini also scored <= 4."""
    hits = [p <= 4 for g, p in pairs if is_hard_filter(g)]
    if not hits:
        return None
    return sum(hits) / len(hits)


def confusion(pairs: list[tuple[dict, int]]) -> dict[str, dict[str, int]]:
    """{human_band: {predicted_band: count}} over all BANDS."""
    table = {h: {p: 0 for p in BANDS} for h in BANDS}
    for g, p in pairs:
        table[label_band(g)][band(p)] += 1
    return table


def pass_at_k(runs_correct: list[list[bool]]) -> dict[str, float | None]:
    """runs_correct[job] = [correct on run 1, run 2, ...].

    pass@1 = run 1 correct, pass@k = any run correct, pass^k = every run correct.
    Jobs with no scored runs are skipped.
    """
    rows = [r for r in runs_correct if r]
    if not rows:
        return {"pass@1": None, "pass@k": None, "pass^k": None}
    n = len(rows)
    return {
        "pass@1": sum(r[0] for r in rows) / n,
        "pass@k": sum(any(r) for r in rows) / n,
        "pass^k": sum(all(r) for r in rows) / n,
    }
