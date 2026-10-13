"""
Regression tests for PIPELINE_FAILURE_RESILIENCE (see
future_devs/PIPELINE_FAILURE_RESILIENCE_SPEC.md, "Diagnosis" section).

Covers:
1. consecutive_failures: increments once on a puller exception, resets on next success
2. refresh re-verification: a failed re-discovery must not wipe a working ATS config
3. error vs genuine zero: a genuine 0-job pull is a success (the ATS-side masking
   of errors as [] is a known gap, pinned by a strict xfail)
4. scorer: one malformed item does not drop the batch; scorer errors are not
   persisted as "seen" and do not clobber existing scores on --rescore
5. atomic state writes for companies.json / new_jobs.json
"""

import json
from pathlib import Path

import pytest

import collect_jobs
import refresh_companies
import score
from matcher import gemini_scorer


# ---------------------------------------------------------------------------
# collect_jobs helpers
# ---------------------------------------------------------------------------

def _company(name="Acme", ats="fake", **kw):
    e = {
        "name": name,
        "website": f"https://{name.lower()}.io",
        "source_vc": "YL Ventures",
        "vc_tier": 1,
        "careers_url": f"https://{name.lower()}.io/careers",
        "ats": ats,
        "ats_params": {"board_token": name.lower()},
        "last_verified_at": "2026-10-01T00:00:00+00:00",
        "consecutive_failures": 0,
    }
    e.update(kw)
    return e


JOB = {"title": "Data Scientist", "location": "Tel Aviv, Israel",
       "description": "d", "apply_url": "https://acme.io/jobs/1"}


def _write(path: Path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# 1. consecutive_failures semantics
# ---------------------------------------------------------------------------

def test_failure_increments_once_then_resets_on_success(in_tmp, monkeypatch):
    _write(in_tmp / "companies.json", [_company()])
    state = {"fail": True}

    def puller(params):
        if state["fail"]:
            raise RuntimeError("503 transient")
        return [JOB]

    monkeypatch.setitem(collect_jobs.ATS_PULLERS, "fake", puller)

    collect_jobs.collect()
    assert _read(in_tmp / "companies.json")[0]["consecutive_failures"] == 1
    assert "Acme" not in _read(in_tmp / "live_positions.json")["successful_companies"]

    state["fail"] = False
    collect_jobs.collect()
    entry = _read(in_tmp / "companies.json")[0]
    assert entry["consecutive_failures"] == 0
    assert entry["last_jobs_pulled_at"]
    assert "Acme" in _read(in_tmp / "live_positions.json")["successful_companies"]
    assert len(_read(in_tmp / "new_jobs.json")) == 1


# ---------------------------------------------------------------------------
# 3. error vs genuine zero
# ---------------------------------------------------------------------------

def test_genuine_zero_jobs_is_not_a_failure(in_tmp, monkeypatch):
    _write(in_tmp / "companies.json", [_company(consecutive_failures=2)])
    monkeypatch.setitem(collect_jobs.ATS_PULLERS, "fake", lambda p: [])

    collect_jobs.collect()
    assert _read(in_tmp / "companies.json")[0]["consecutive_failures"] == 0
    assert "Acme" in _read(in_tmp / "live_positions.json")["successful_companies"]


@pytest.mark.xfail(
    strict=True,
    reason="Known gap (Needs Omer): ATS pullers swallow HTTP errors and return [], "
    "so collect_jobs cannot tell a failed pull from a genuine 0-job pull. "
    "Flips to XPASS once pullers raise on fetch failure.",
)
def test_transient_http_error_in_real_puller_counts_as_failure(in_tmp, monkeypatch):
    _write(in_tmp / "companies.json", [_company(ats="greenhouse")])

    def boom(*a, **kw):
        raise ConnectionError("connection reset")

    monkeypatch.setattr("ats.greenhouse.httpx.get", boom)
    collect_jobs.collect()
    assert _read(in_tmp / "companies.json")[0]["consecutive_failures"] == 1
    assert "Acme" not in _read(in_tmp / "live_positions.json")["successful_companies"]


# ---------------------------------------------------------------------------
# 5. atomic state writes
# ---------------------------------------------------------------------------

def _crash_after_partial_write(real_dump):
    def dump(obj, fp, **kw):
        fp.write('[{"name": "trunc')  # partial bytes hit the file, then the process dies
        raise KeyboardInterrupt
    return dump


def test_collect_crash_mid_write_leaves_companies_json_intact(in_tmp, monkeypatch):
    original = [_company()]
    _write(in_tmp / "companies.json", original)
    monkeypatch.setitem(collect_jobs.ATS_PULLERS, "fake", lambda p: [JOB])
    monkeypatch.setattr(collect_jobs.json, "dump", _crash_after_partial_write(json.dump))

    with pytest.raises(KeyboardInterrupt):
        collect_jobs.collect()
    assert _read(in_tmp / "companies.json") == original
    assert not list(in_tmp.glob("*.tmp"))


def test_collect_crash_mid_jobs_write_leaves_new_jobs_json_intact(in_tmp, monkeypatch):
    _write(in_tmp / "companies.json", [_company()])
    previous_jobs = [{**JOB, "company": "Acme", "first_seen": "2026-01-01"}]
    _write(in_tmp / "new_jobs.json", previous_jobs)
    monkeypatch.setitem(collect_jobs.ATS_PULLERS, "fake", lambda p: [JOB])

    real_dump = json.dump

    def dump(obj, fp, **kw):
        # let companies.json + live_positions.json through, crash on the jobs list
        if isinstance(obj, list) and obj and "apply_url" in obj[0]:
            fp.write("[{")
            raise KeyboardInterrupt
        return real_dump(obj, fp, **kw)

    monkeypatch.setattr(collect_jobs.json, "dump", dump)
    with pytest.raises(KeyboardInterrupt):
        collect_jobs.collect()
    assert _read(in_tmp / "new_jobs.json") == previous_jobs


def test_refresh_save_crash_leaves_companies_json_intact(in_tmp, monkeypatch):
    original = [_company()]
    _write(in_tmp / "companies.json", original)
    monkeypatch.setattr(refresh_companies.json, "dump", _crash_after_partial_write(json.dump))

    with pytest.raises(KeyboardInterrupt):
        refresh_companies.save_companies({"Acme": _company(ats="greenhouse")})
    assert _read(in_tmp / "companies.json") == original


# ---------------------------------------------------------------------------
# 2. refresh re-verification must not strand a recoverable company
# ---------------------------------------------------------------------------

def _run_refresh_with_discovery(in_tmp, monkeypatch, entry, discovery):
    _write(in_tmp / "companies.json", [entry])
    monkeypatch.setattr(
        refresh_companies, "VC_REGISTRY",
        {"YL Ventures": {"tier": 1, "fetch": lambda: [
            {"company_name": entry["name"], "company_website": entry["website"]}]}},
    )
    monkeypatch.setattr(refresh_companies, "discover", lambda name, website: discovery)
    refresh_companies.refresh()
    return _read(in_tmp / "companies.json")[0]


@pytest.mark.parametrize("discovery", [
    {"careers_url": None, "ats": "unknown", "ats_params": {}},                      # careers page not found (flake)
    {"careers_url": "https://acme.io/careers", "ats": "unknown", "ats_params": {}},  # ATS not detected (flake)
])
@pytest.mark.parametrize("trigger", [
    {"last_verified_at": "2025-01-01T00:00:00+00:00"},  # 30d+ stale
    {"consecutive_failures": 3},                        # failure threshold
])
def test_failed_reverify_keeps_working_ats_config(in_tmp, monkeypatch, discovery, trigger):
    entry = _company(ats="greenhouse", **trigger)
    after = _run_refresh_with_discovery(in_tmp, monkeypatch, entry, discovery)

    assert after["ats"] == "greenhouse"
    assert after["ats_params"] == {"board_token": "acme"}
    assert after["careers_url"] == entry["careers_url"]
    # stamped so the weekly run doesn't rediscover it every week
    assert after["last_verified_at"] != "2025-01-01T00:00:00+00:00"


def test_successful_reverify_still_updates_config(in_tmp, monkeypatch):
    entry = _company(ats="greenhouse", consecutive_failures=3)
    discovery = {"careers_url": "https://jobs.ashbyhq.com/acme", "ats": "ashby",
                 "ats_params": {"org_name": "acme"}}
    after = _run_refresh_with_discovery(in_tmp, monkeypatch, entry, discovery)

    assert after["ats"] == "ashby"
    assert after["ats_params"] == {"org_name": "acme"}
    assert after["consecutive_failures"] == 0


def test_reverify_of_unknown_entry_still_records_discovery(in_tmp, monkeypatch):
    entry = _company(ats="unknown", ats_params={}, careers_url=None,
                     last_verified_at="2025-01-01T00:00:00+00:00")
    discovery = {"careers_url": "https://acme.io/careers", "ats": "unknown", "ats_params": {}}
    after = _run_refresh_with_discovery(in_tmp, monkeypatch, entry, discovery)
    assert after["careers_url"] == "https://acme.io/careers"


# ---------------------------------------------------------------------------
# 4. score-stage robustness
# ---------------------------------------------------------------------------

class _Resp:
    def __init__(self, text):
        self.text = text


class _Client:
    def __init__(self, text):
        self.models = self
        self._text = text

    def generate_content(self, **kw):
        return _Resp(self._text)


@pytest.fixture
def no_rpm(monkeypatch):
    monkeypatch.setattr(gemini_scorer, "_rpm_wait", lambda: None)


def _jobs(n):
    return [{"company": "Acme", "title": f"DS {i}", "apply_url": f"https://acme.io/{i}"}
            for i in range(n)]


def test_one_malformed_item_does_not_drop_the_batch(no_rpm):
    raw = "```json\n" + json.dumps([
        {"score": 8, "reasoning": "good", "flags": []},
        {"score": "N/A", "reasoning": "bad item", "flags": []},
        None,
        {"score": 6, "reasoning": "ok", "flags": ["lead-path-implied"]},
    ]) + "\n```"
    results = gemini_scorer.score_jobs_batch(_jobs(4), "p", "c", _Client(raw))

    assert results[0]["score"] == 8 and "scorer-error" not in results[0]["flags"]
    assert results[3]["score"] == 6 and results[3]["flags"] == ["lead-path-implied"]
    assert "scorer-error" in results[1]["flags"]
    assert "scorer-error" in results[2]["flags"]


def test_short_response_flags_missing_items_as_scorer_error(no_rpm):
    raw = json.dumps([{"score": 7, "reasoning": "r", "flags": []}])
    results = gemini_scorer.score_jobs_batch(_jobs(3), "p", "c", _Client(raw))

    assert results[0]["score"] == 7
    assert all("scorer-error" in r["flags"] for r in results[1:])


def test_scorer_errors_are_not_persisted_as_seen(monkeypatch, tmp_path):
    jobs = _jobs(3)
    monkeypatch.setattr(score, "score_jobs_batch", lambda batch, *a: [
        {"score": 7, "reasoning": "r", "flags": []},
        {"score": 0, "reasoning": "scorer error: 503 UNAVAILABLE", "flags": ["scorer-error"]},
        {"score": 2, "reasoning": "r", "flags": []},
    ][: len(batch)])

    log = tmp_path / "all_scores.jsonl"
    with log.open("a", encoding="utf-8") as fp:
        score._score_jobs_batched(jobs, "p", "c", None, "t", fp)

    logged = [json.loads(line)["apply_url"] for line in log.read_text(encoding="utf-8").splitlines()]
    assert logged == [jobs[0]["apply_url"], jobs[2]["apply_url"]]


def test_rescore_error_does_not_clobber_existing_score(monkeypatch, tmp_path):
    prof = tmp_path / "p"
    prof.mkdir()
    (prof / "profile.md").write_text("profile", encoding="utf-8")
    (prof / "cv.md").write_text("cv", encoding="utf-8")
    existing = [{"company": "Acme", "title": "Lead DS", "apply_url": "https://acme.io/1",
                 "score": 9, "reasoning": "great fit", "flags": []}]
    (prof / "scored_jobs.json").write_text(json.dumps(existing), encoding="utf-8")

    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    from google import genai
    monkeypatch.setattr(genai, "Client", lambda api_key: None)
    monkeypatch.setattr(score, "_score_jobs_batched", lambda jobs, *a, **kw: [
        {**j, "score": 0, "reasoning": "scorer error: 503", "flags": ["scorer-error"]} for j in jobs])

    score._rescore_profile(prof)
    after = _read(prof / "scored_jobs.json")[0]
    assert after["score"] == 9
    assert after["reasoning"] == "great fit"
