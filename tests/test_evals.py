"""Tests for the scorer eval harness (evals/). Fake Gemini client - no network."""

import csv
import json
import re

import pytest

import matcher.gemini_scorer as gs
from evals import make_labelling_sheet as sheet
from evals import metrics
from evals import run_eval


# ---------------------------------------------------------------------------
# metrics
# ---------------------------------------------------------------------------

def _g(score, flags=None, band=None):
    return {"label_score": score, "label_flags": flags or [], "label_band": band}


def test_band_edges():
    assert [metrics.band(s) for s in (0, 4, 5, 6, 7, 8, 9, 10)] == \
        ["0-4", "0-4", "5-6", "5-6", "7-8", "7-8", "9-10", "9-10"]


def test_band_accuracy_mae_confusion():
    pairs = [(_g(9), 10), (_g(7), 5), (_g(2), 3), (_g(6, band="7-8"), 7)]
    assert metrics.band_accuracy(pairs) == 0.75  # explicit label_band wins over label_score
    assert metrics.mae(pairs) == (1 + 2 + 1 + 1) / 4
    conf = metrics.confusion(pairs)
    assert conf["7-8"]["5-6"] == 1 and conf["9-10"]["9-10"] == 1
    assert sum(sum(r.values()) for r in conf.values()) == 4
    assert metrics.band_accuracy([]) is None and metrics.mae([]) is None


def test_hard_filter_recall():
    pairs = [(_g(1, ["dealbreaker-location"]), 3), (_g(0, ["Non-DS"]), 8), (_g(9), 9)]
    assert metrics.hard_filter_recall(pairs) == 0.5
    assert metrics.hard_filter_recall([(_g(9), 9)]) is None


def test_pass_at_k():
    r = metrics.pass_at_k([[True, True], [False, True], [False, False], []])
    assert r == {"pass@1": 1 / 3, "pass@k": 2 / 3, "pass^k": 1 / 3}


# ---------------------------------------------------------------------------
# run_eval end to end with a fake client
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, text):
        self.text = text


class FakeClient:
    """Returns a score per job, keyed by the Title line in the batch prompt."""

    def __init__(self, scores_by_title):
        self.scores = scores_by_title
        self.calls = 0
        self.models = self

    def generate_content(self, model, contents, config):
        self.calls += 1
        titles = re.findall(r"^  Title: (.*)$", contents, flags=re.M)
        return _Resp(json.dumps([{"score": self.scores[t], "reasoning": "fake", "flags": []} for t in titles]))


GOLDEN = [
    # (title, human score, human flags, fake Gemini score)
    ("Fraud DS Lead", 9, [], 9),
    ("Senior Data Scientist", 8, [], 7),
    ("ML Engineer", 6, [], 5),
    ("Haifa Data Scientist", 2, ["dealbreaker-location"], 3),
    ("Sales Engineer", 0, ["non-ds"], 1),
    ("Applied Scientist", 4, [], 4),
]


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(gs, "_rpm_wait", lambda: None)
    golden = tmp_path / "golden_set.jsonl"
    golden.write_text("".join(
        json.dumps({"job_id": f"id{i}", "company": "Acme", "title": t, "location": "Tel Aviv",
                    "description": "x", "label_score": s, "label_band": "", "label_flags": f}) + "\n"
        for i, (t, s, f, _) in enumerate(GOLDEN)), encoding="utf-8")
    profile = tmp_path / "profile"
    profile.mkdir()
    (profile / "profile.md").write_text("profile", encoding="utf-8")
    (profile / "cv.md").write_text("cv", encoding="utf-8")
    good = {t: p for t, _, _, p in GOLDEN}
    return tmp_path, golden, profile, good


def _args(golden, profile, *extra):
    return ["--golden", str(golden), "--profile", str(profile), *extra]


def test_missing_golden_set_exits_nonzero(tmp_path, capsys):
    rc = run_eval.main(["--golden", str(tmp_path / "nope.jsonl")], client=object())
    assert rc != 0
    assert "golden set not found" in capsys.readouterr().err


def test_run_eval_baseline_then_regression(env, capsys):
    tmp, golden, profile, good = env
    base = tmp / "baseline.json"

    assert run_eval.main(_args(golden, profile, "--write-baseline", str(base)), client=FakeClient(good)) == 0
    recorded = json.loads(base.read_text(encoding="utf-8"))
    assert recorded["metrics"]["band_accuracy"] == 1.0
    assert recorded["metrics"]["hard_filter_recall"] == 1.0
    assert recorded["model"] == "gemini-2.5-flash"

    # same scores -> at baseline, exit 0; --runs 3 makes 3 scoring calls
    fake = FakeClient(good)
    assert run_eval.main(_args(golden, profile, "--runs", "3", "--baseline", str(base)), client=fake) == 0
    assert fake.calls == 3
    assert "pass@1 / pass@3" in capsys.readouterr().out

    # simulated regression: the dealbreaker-location job now tops the digest
    bad = {**good, "Haifa Data Scientist": 9}
    assert run_eval.main(_args(golden, profile, "--baseline", str(base)), client=FakeClient(bad)) == 1
    assert "hard_filter_recall" in capsys.readouterr().err


def test_scorer_errors_are_excluded(env):
    tmp, golden, profile, good = env

    class Broken(FakeClient):
        def generate_content(self, **kw):
            raise RuntimeError("503 unavailable")

    runs = [run_eval.score_golden(run_eval.load_golden(golden), profile, Broken(good))]
    rep = run_eval.compute_report(run_eval.load_golden(golden), runs)
    assert rep["scorer_errors"] == 6 and rep["band_accuracy"] is None


# ---------------------------------------------------------------------------
# labelling sheet
# ---------------------------------------------------------------------------

def _job(i, title="Data Scientist", location="Tel Aviv"):
    return {"company": f"Co{i}", "title": title, "location": location,
            "description": "שלום desc", "apply_url": f"https://x/{i}"}


def test_sheet_round_trip(tmp_path):
    scored = [{**_job(i), "score": s, "flags": []} for i, s in enumerate([10, 9, 8, 7, 6, 5, 3, 0])]
    new_jobs = [_job(100, title="Account Executive"), _job(101, location="London, UK")]
    buckets = sheet.build_buckets(new_jobs, scored, {})
    assert len(buckets["filtered"]) == 2 and len(buckets["9-10"]) == 2

    picked = sheet.stratified_sample(buckets, 5, seed=0)
    assert len(picked) == 5
    assert {metrics.band(j["score"]) if "score" in j else "filtered" for j in picked} == set(sheet.BUCKETS)

    csv_path = tmp_path / "sheet.csv"
    sheet.write_sheet(picked, csv_path)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert "score" not in rows[0]  # blind labelling: Gemini's score is not in the sheet
    rows[0].update(label_score="8", label_flags="lead-path-implied; wrong-domain")
    rows[1].update(label_score="1", label_band="0-4", label_flags="non-ds")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    golden = tmp_path / "golden.jsonl"
    assert sheet.main(["--import", str(csv_path), "--golden", str(golden)]) == 0
    items = run_eval.load_golden(golden)
    assert len(items) == 2
    assert items[0]["label_score"] == 8 and items[0]["label_band"] == "7-8"
    assert items[0]["label_flags"] == ["lead-path-implied", "wrong-domain"]
    assert items[0]["description"] == "שלום desc"
    assert metrics.is_hard_filter(items[1])


def test_sheet_import_rejects_bad_score(tmp_path):
    csv_path = tmp_path / "sheet.csv"
    sheet.write_sheet([_job(1)], csv_path)
    text = csv_path.read_text(encoding="utf-8-sig").splitlines()
    text[-1] = text[-1].rstrip(",") + ",11,,,"
    csv_path.write_text("\n".join(text) + "\n", encoding="utf-8")
    assert sheet.main(["--import", str(csv_path), "--golden", str(tmp_path / "g.jsonl")]) == 1
