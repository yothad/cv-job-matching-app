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
    assert recorded["model"] == ",".join(gs.MODELS)

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

    runs = [run_eval.score_golden(run_eval.load_golden(golden), profile, Broken(good))]
    rep = run_eval.compute_report(run_eval.load_golden(golden), runs)
    assert rep["scorer_errors"] == 6 and rep["band_accuracy"] is None


class Broken(FakeClient):
    """Every Gemini call fails with a non-429 error (dead model / bad key)."""

    def generate_content(self, **kw):
        raise RuntimeError("404 model not found")


def test_all_scorer_errors_fail_baseline(env, capsys):
    tmp, golden, profile, good = env
    base = tmp / "baseline.json"
    assert run_eval.main(_args(golden, profile, "--write-baseline", str(base)), client=FakeClient(good)) == 0
    capsys.readouterr()
    assert run_eval.main(_args(golden, profile, "--baseline", str(base)), client=Broken(good)) == 1
    assert "scorer-error" in capsys.readouterr().err
    # even with the error-share gate disabled, n/a metrics vs a measured baseline regress
    assert run_eval.main(_args(golden, profile, "--baseline", str(base), "--max-error-share", "1"),
                         client=Broken(good)) == 1
    assert "band_accuracy 1.000 -> n/a" in capsys.readouterr().err


def test_error_share_threshold():
    rep = {"n_jobs": 10, "runs": 2, "scorer_errors": 3}  # 15%
    assert run_eval.check_error_share(rep, run_eval.DEFAULT_MAX_ERROR_SHARE) is not None
    assert run_eval.check_error_share(rep, 0.2) is None
    assert run_eval.check_error_share({**rep, "scorer_errors": 2}, 0.1) is None  # exactly 10% passes


def test_error_share_from_baseline_tolerance(env, capsys):
    tmp, golden, profile, good = env
    base = tmp / "baseline.json"
    assert run_eval.main(_args(golden, profile, "--write-baseline", str(base)), client=FakeClient(good)) == 0
    rec = json.loads(base.read_text(encoding="utf-8"))
    rec["tolerance"]["scorer_error_share"] = 0.0
    base.write_text(json.dumps(rec), encoding="utf-8")
    capsys.readouterr()
    # the baseline file's tolerance is honoured
    assert run_eval.main(_args(golden, profile, "--baseline", str(base)), client=Broken(good)) == 1
    assert "scorer-error" in capsys.readouterr().err


@pytest.mark.parametrize("content, msg", [
    ("{", "not valid JSON"),
    ('{"tolerance": {}}', "no 'metrics'"),
    ('{"metrics": {}}', "metrics missing"),
    ('{"metrics": {"band_accuracy": null, "mae": null, "hard_filter_recall": null}}', "band_accuracy is null"),
])
def test_bad_baseline_is_input_error(env, capsys, content, msg):
    tmp, golden, profile, good = env
    base = tmp / "baseline.json"
    base.write_text(content, encoding="utf-8")
    assert run_eval.main(_args(golden, profile, "--baseline", str(base)), client=FakeClient(good)) == 2
    assert msg in capsys.readouterr().err


def test_nothing_measured_is_never_a_pass(env, capsys):
    tmp, golden, profile, good = env
    empty = tmp / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert run_eval.main(_args(empty, profile), client=FakeClient(good)) == 2
    assert run_eval.main(_args(golden, profile, "--runs", "0"), client=FakeClient(good)) == 2
    # all-error run with the share gate disabled must not record a baseline
    base = tmp / "b.json"
    assert run_eval.main(_args(golden, profile, "--write-baseline", str(base), "--max-error-share", "1"),
                         client=Broken(good)) == 1
    assert not base.exists()


def test_failed_gate_does_not_overwrite_baseline(env):
    tmp, golden, profile, good = env
    base = tmp / "baseline.json"
    assert run_eval.main(_args(golden, profile, "--write-baseline", str(base)), client=FakeClient(good)) == 0
    before = base.read_text(encoding="utf-8")
    bad = {**good, "Haifa Data Scientist": 9}
    assert run_eval.main(_args(golden, profile, "--baseline", str(base), "--write-baseline", str(base)),
                         client=FakeClient(bad)) == 1
    assert base.read_text(encoding="utf-8") == before


@pytest.mark.parametrize("item, msg", [
    ({"title": "x"}, "line 2: label_score"),
    ({"title": "x", "label_score": 5, "label_band": "5-7"}, "line 2: label_band"),
])
def test_bad_golden_line_is_named(tmp_path, capsys, item, msg):
    golden = tmp_path / "g.jsonl"
    golden.write_text(json.dumps({"label_score": 3}) + "\n" + json.dumps(item) + "\n", encoding="utf-8")
    (tmp_path / "profile.md").write_text("profile", encoding="utf-8")
    assert run_eval.main(["--golden", str(golden), "--profile", str(tmp_path)], client=object()) == 2
    assert msg in capsys.readouterr().err


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


def _fill_quick(csv_path, bands):
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for row, b in zip(rows, bands):
        row["quick_band"] = b
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def test_quick_sheet_round_trip(tmp_path):
    jobs = [{**_job(i), "description": "שלום " + "x" * 2000} for i in range(4)]
    csv_path = tmp_path / "sheet.csv"
    sheet.write_quick_sheet(jobs, csv_path)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == sheet.QUICK_COLS
    assert len(rows[0]["excerpt"]) == sheet.EXCERPT_CHARS

    _fill_quick(csv_path, ["L", "m", "High", ""])
    golden = tmp_path / "golden.jsonl"
    assert sheet.main(["--import", str(csv_path), "--golden", str(golden)]) == 0
    items = run_eval.load_golden(golden)
    assert [i["label_score"] for i in items] == [2, 5, 8]
    assert [i["label_band"] for i in items] == ["0-4", "5-6", "7-8"]
    assert items[0]["description"] == jobs[0]["description"]  # full text, not the excerpt
    assert items[0]["company"] == "Co0" and items[0]["job_id"]


def test_quick_sheet_rejects_bad_band_and_missing_sidecar(tmp_path):
    csv_path = tmp_path / "sheet.csv"
    sheet.write_quick_sheet([_job(1)], csv_path)
    _fill_quick(csv_path, ["X"])
    assert sheet.main(["--import", str(csv_path), "--golden", str(tmp_path / "g.jsonl")]) == 1
    _fill_quick(csv_path, ["H"])
    (tmp_path / "sheet.jobs.jsonl").unlink()
    assert sheet.main(["--import", str(csv_path), "--golden", str(tmp_path / "g.jsonl")]) == 1


# ---------------------------------------------------------------------------
# --mix / --exclude / --max-per-company / --append / role excerpt
# ---------------------------------------------------------------------------

def test_allocate_fills_short_group_in_mix_ratio():
    mix = {"H": 35, "M": 35, "L": 30}
    assert sheet.allocate(100, mix, {"H": 18, "M": 60, "L": 60}) == {"H": 18, "M": 44, "L": 38}
    assert sheet.allocate(100, mix, {"H": 18, "M": 26, "L": 44}) == {"H": 18, "M": 26, "L": 44}
    assert sheet.allocate(20, mix, {"H": 50, "M": 50, "L": 50}) == {"H": 7, "M": 7, "L": 6}


def test_parse_mix_rejects_unknown_group():
    assert sheet.parse_mix("H=35,M=35,L=30") == {"H": 35.0, "M": 35.0, "L": 30.0}
    with pytest.raises(ValueError):
        sheet.parse_mix("X=10")


def _scored(i, score, company=None):
    return {**_job(i), "company": company or f"Co{i}", "score": score, "reasoning": "secret", "flags": []}


def test_mix_sample_quota_cap_and_exclude():
    scored = ([_scored(i, 8, company="Big" if i < 5 else None) for i in range(10)]
              + [_scored(100 + i, 5) for i in range(10)] + [_scored(200 + i, 1) for i in range(10)])
    excluded = {sheet._job_key(scored[9])}
    buckets = sheet.build_buckets([], scored, {}, exclude=excluded)
    picked, quotas = sheet.mix_sample(buckets, {"H": 35, "M": 35, "L": 30}, 20, seed=0, max_per_company=2)
    keys = {sheet._job_key(j) for j in picked}
    assert not keys & excluded
    assert sum(j["company"] == "Big" for j in picked) <= 2
    # H pool: 10 - 1 excluded - 3 over the Big cap = 6; the spare slot goes to M (35:30 remainder)
    assert quotas == {"H": 6, "M": 8, "L": 6} and len(picked) == 20


def test_quick_sheet_is_blind_and_uses_role_excerpt(tmp_path):
    job = {**_scored(1, 9), "description": "PITCH " * 200, "role_description": "THE ROLE " * 100,
           "requirements": "REQS", "responsibilities": "", "ats": "comeet"}
    csv_path = tmp_path / "sheet.csv"
    sheet.write_quick_sheet([job], csv_path)
    text = csv_path.read_text(encoding="utf-8-sig") + (tmp_path / "sheet.jobs.jsonl").read_text(encoding="utf-8")
    assert "score" not in text.split("\n")[0] and '"score"' not in text and "secret" not in text
    assert "9-10" not in text and '"flags"' not in text
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        assert next(csv.DictReader(f))["excerpt"].startswith("THE ROLE")
    side = json.loads((tmp_path / "sheet.jobs.jsonl").read_text(encoding="utf-8"))
    assert side["requirements"] == "REQS" and side["ats"] == "comeet"


def test_import_append_dedupes_and_fills_sections(tmp_path):
    golden = tmp_path / "golden.jsonl"
    first = tmp_path / "s1.csv"
    sheet.write_quick_sheet([_job(1), _job(2)], first)
    _fill_quick(first, ["H", "L"])
    assert sheet.main(["--import", str(first), "--golden", str(golden), "--jobs", str(tmp_path / "none.json")]) == 0

    second = tmp_path / "s2.csv"
    sheet.write_quick_sheet([_job(2), _job(3)], second)  # job 2 already labelled
    _fill_quick(second, ["M", "M"])
    assert sheet.main(["--import", str(second), "--golden", str(golden), "--append",
                       "--jobs", str(tmp_path / "none.json")]) == 0
    items = run_eval.load_golden(golden)
    assert [i["company"] for i in items] == ["Co1", "Co2", "Co3"]
    assert items[1]["label_score"] == 2  # the first label wins
    assert all(k in items[0] for k in ("role_description", "responsibilities", "requirements", "ats"))


def test_refresh_sections_takes_fresh_copy(tmp_path):
    golden = tmp_path / "golden.jsonl"
    item = {**_job(1), "job_id": sheet._job_key(_job(1)), "label_score": 8, "label_band": "7-8",
            "role_description": "old", "responsibilities": "", "requirements": "", "ats": ""}
    golden.write_text(json.dumps(item) + "\n", encoding="utf-8")
    jobs = tmp_path / "new_jobs.json"
    jobs.write_text(json.dumps([{**_job(1), "role_description": "new role", "requirements": "new reqs",
                                 "responsibilities": "", "ats": "ashby"}]), encoding="utf-8")
    assert sheet.main(["--refresh-sections", "--golden", str(golden), "--jobs", str(jobs)]) == 0
    out = run_eval.load_golden(golden)[0]
    assert (out["role_description"], out["requirements"], out["ats"]) == ("new role", "new reqs", "ashby")
    assert out["label_score"] == 8


# ---------------------------------------------------------------------------
# --recheck / --batch
# ---------------------------------------------------------------------------

def _golden_item(i, band, location="Tel Aviv"):
    j = _job(i, location=location)
    score = {"L": 2, "M": 5, "H": 8}[band]
    return {**j, "job_id": sheet._job_key(j), "label_score": score, "label_band": metrics.band(score),
            "label_flags": [], "notes": "first"}


def test_pick_recheck_spreads_bands_israel_only_and_hides_labels():
    golden = ([_golden_item(i, "L") for i in range(5)] + [_golden_item(10 + i, "M") for i in range(5)]
              + [_golden_item(20 + i, "H") for i in range(5)] + [_golden_item(30, "L", location="London, UK")])
    picked = sheet.pick_recheck(golden, 6, seed=0)
    assert len(picked) == 6 and all(p["recheck"] for p in picked)
    assert sorted(sheet.band3(metrics.label_band(next(g for g in golden if g["job_id"] == p["job_id"])))
                  for p in picked) == ["H", "H", "L", "L", "M", "M"]
    assert all("London" not in p["location"] for p in picked)
    assert not any(k in p for p in picked for k in ("label_score", "label_band", "notes"))


def test_recheck_rows_never_touch_golden_and_report_agreement(tmp_path, capsys):
    golden = tmp_path / "golden.jsonl"
    old = [_golden_item(1, "H"), _golden_item(2, "L")]
    golden.write_text("".join(json.dumps(o) + "\n" for o in old), encoding="utf-8")
    csv_path = tmp_path / "final.csv"
    rows = [{**sheet._row(_job(1)), "recheck": True}, {**sheet._row(_job(2)), "recheck": True}, _job(3)]
    sheet.write_quick_sheet(rows, csv_path)
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        assert "recheck" not in f.readline()  # the sheet never says which rows are re-checks
    _fill_quick(csv_path, ["H", "M", "L"])  # job 1 agrees, job 2 changes L -> M
    assert sheet.main(["--import", str(csv_path), "--golden", str(golden), "--append", "--batch", "2",
                       "--jobs", str(tmp_path / "none.json")]) == 0
    items = run_eval.load_golden(golden)
    assert [(i["company"], i["batch"]) for i in items] == [("Co1", "1"), ("Co2", "1"), ("Co3", "2")]
    assert items[1]["label_score"] == 2  # original label kept
    assert "recheck" not in items[2]
    rc = [json.loads(line) for line in (tmp_path / "recheck.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {(r["original"], r["recheck"]) for r in rc} == {("H", "H"), ("L", "M")}
    assert "agreed with your first label on 1/2" in capsys.readouterr().out
