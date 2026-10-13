"""Background Score now: per-batch saves, progress, weekly-run accounting,
stale-run detection and the re-score mode.

Run from webapp/backend:  uv run --with pytest python -m pytest tests -q

Supabase and Gemini are stubbed - no network, no secrets needed.
"""
import sys
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if "db.supabase_client" not in sys.modules:
    _stub = types.ModuleType("db.supabase_client")
    _stub.supabase = types.SimpleNamespace()
    sys.modules["db.supabase_client"] = _stub

from routers import scoring  # noqa: E402


class _Quota(Exception):
    pass


class _Query:
    def __init__(self, db, name):
        self.db, self.name, self.op, self.payload = db, name, None, None

    def update(self, payload):
        self.op, self.payload = "update", payload
        return self

    def upsert(self, rows, **kw):
        self.op, self.payload = "upsert", rows
        return self

    def __getattr__(self, name):  # select/eq/or_/in_/neq/order/range - all chain
        return lambda *a, **k: self

    def execute(self):
        if self.op == "update" and "score_run" in self.payload:
            self.db.runs.append(dict(self.payload["score_run"]))
        elif self.op == "update":
            self.db.user_updates.append(self.payload)
        elif self.op == "upsert":
            self.db.upserts.append(self.payload)
        return types.SimpleNamespace(data=self.db.reads.get(self.name, []))


class _DB:
    def __init__(self, reads=None):
        self.runs, self.user_updates, self.upserts, self.reads = [], [], [], reads or {}

    def table(self, name):
        return _Query(self, name)


def _jobs(n):
    return [{"apply_url": f"https://x/{i}", "company": "Acme", "title": "DS",
             "location": "TLV", "description": "JD"} for i in range(n)]


def _run(monkeypatch, jobs, results_for, mode="new", remaining=0):
    """results_for(batch_index, batch) -> list of results, or raise."""
    db = _DB()
    monkeypatch.setattr(scoring, "supabase", db)
    monkeypatch.setattr(scoring, "BATCH_SIZE", 2)
    calls = {"n": 0}

    def score(batch, profile_md, cv, client):
        calls["n"] += 1
        return results_for(calls["n"] - 1, batch)

    monkeypatch.setattr(scoring, "_scorer", lambda key: (score, _Quota, object()))
    run = {"id": "r1", "mode": mode, "status": "running", "total": len(jobs), "scored": 0,
           "failed": 0, "remaining": remaining, "error": None, "warning": None}
    scoring._run_scoring("user-1", run, jobs, "# me", "cv", "secret-key", 3, 0)
    return db, run


def _ok(batch):
    return [{"score": 7, "reasoning": "fit", "flags": []} for _ in batch]


def _err(batch):
    return [{"score": 0, "reasoning": "scorer error: 503 secret-key", "flags": ["scorer-error"]} for _ in batch]


def test_saves_each_batch_and_reports_progress(monkeypatch):
    db, run = _run(monkeypatch, _jobs(5), lambda i, b: _ok(b))
    assert [len(u) for u in db.upserts] == [2, 2, 1]
    assert [r["scored"] for r in db.runs] == [2, 4, 5, 5]
    assert run["status"] == "done" and run["failed"] == 0
    assert db.user_updates == [{"scoring_runs_this_week": 1}]


def test_capped_run_does_not_use_a_weekly_run(monkeypatch):
    db, run = _run(monkeypatch, _jobs(2), lambda i, b: _ok(b), remaining=50)
    assert run["status"] == "done"
    assert db.user_updates == []


def test_whole_batch_failure_stops_and_never_persists_errors(monkeypatch):
    db, run = _run(monkeypatch, _jobs(6), lambda i, b: _ok(b) if i == 0 else _err(b))
    assert [len(u) for u in db.upserts] == [2]
    assert run["status"] == "done" and run["scored"] == 2 and run["failed"] == 4
    assert "secret-key" not in run["warning"] and "[key]" in run["warning"]


def test_nothing_scored_fails_without_charging(monkeypatch):
    db, run = _run(monkeypatch, _jobs(3), lambda i, b: _err(b))
    assert run["status"] == "failed" and "Gemini scoring failed" in run["error"]
    assert db.upserts == [] and db.user_updates == []


def test_quota_exhaustion_stops_the_run(monkeypatch):
    def results(i, b):
        if i == 1:
            raise _Quota("quota")
        return _ok(b)
    db, run = _run(monkeypatch, _jobs(6), results)
    assert run["scored"] == 2 and run["failed"] == 4 and run["status"] == "done"


def test_run_that_stops_early_does_not_use_a_weekly_run(monkeypatch):
    def results(i, b):
        if i == 1:
            raise _Quota("quota")
        return _ok(b)
    db, run = _run(monkeypatch, _jobs(6), results)
    assert db.user_updates == []
    db, run = _run(monkeypatch, _jobs(6), lambda i, b: _ok(b) if i == 0 else _err(b))
    assert db.user_updates == []


def test_crash_marks_run_failed(monkeypatch):
    def results(i, b):
        raise RuntimeError("boom secret-key")
    db, run = _run(monkeypatch, _jobs(2), results)
    assert run["status"] == "failed" and "secret-key" not in run["error"]


def test_rescore_restamps_scored_at_and_is_free(monkeypatch):
    db, run = _run(monkeypatch, _jobs(2), lambda i, b: _ok(b), mode="rescore")
    assert all("scored_at" in r for r in db.upserts[0])
    assert all("applied" not in r for r in db.upserts[0])
    assert db.user_updates == []


def test_stale_running_run_reads_as_interrupted():
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    fresh = datetime.now(timezone.utc).isoformat()
    assert scoring._effective_run({"status": "running", "updated_at": old})["status"] == "failed"
    assert scoring._effective_run({"status": "running", "updated_at": fresh})["status"] == "running"
    assert scoring._effective_run(None) is None


def test_rescore_candidates_join_catalog_descriptions(monkeypatch):
    db = _DB(reads={"scored_jobs": [{"apply_url": "https://x/1"}],
                    "positions": [{"apply_url": "https://x/1", "description": "JD"}]})
    monkeypatch.setattr(scoring, "supabase", db)
    assert scoring._rescore_candidates("user-1") == [{"apply_url": "https://x/1", "description": "JD"}]


def test_auto_endpoint_requires_the_shared_secret(monkeypatch):
    import pytest
    from fastapi import BackgroundTasks, HTTPException
    monkeypatch.setattr(scoring, "AUTO_SCORE_SECRET", "s3cret")
    with pytest.raises(HTTPException) as e:
        scoring.auto_score(BackgroundTasks(), x_cron_secret="wrong")
    assert e.value.status_code == 403
    monkeypatch.setattr(scoring, "AUTO_SCORE_SECRET", "")
    with pytest.raises(HTTPException):
        scoring.auto_score(BackgroundTasks(), x_cron_secret="")
    monkeypatch.setattr(scoring, "AUTO_SCORE_SECRET", "s3cret")
    tasks = BackgroundTasks()
    assert scoring.auto_score(tasks, x_cron_secret="s3cret") == {"accepted": True}
    assert len(tasks.tasks) == 1


def _auto(monkeypatch, users, pending_batches, results=lambda i, b: _ok(b), stored_runs=None):
    stored_runs = stored_runs or {}
    db = _DB(reads={"users": users})
    monkeypatch.setattr(scoring, "supabase", db)
    monkeypatch.setattr(scoring, "BATCH_SIZE", 2)
    monkeypatch.setattr(scoring, "RUN_CAP", 2)
    monkeypatch.setattr(scoring, "fetch_positions", lambda **k: _jobs(1))
    monkeypatch.setattr(scoring, "_decrypt_key", lambda enc: "key")
    calls = {"n": 0}

    def score(batch, *a):
        calls["n"] += 1
        return results(calls["n"] - 1, batch)

    monkeypatch.setattr(scoring, "_scorer", lambda key: (score, _Quota, object()))
    queue = list(pending_batches)
    monkeypatch.setattr(scoring, "_new_pending", lambda uid, jobs: queue.pop(0) if queue else [])
    stored = {u["id"]: u.get("score_run") for u in users}
    monkeypatch.setattr(scoring, "_fetch_run", lambda uid: stored_runs.get(uid, stored.get(uid)))
    scoring._run_auto()
    return db


def test_auto_chains_capped_runs_and_never_charges(monkeypatch):
    user = {"id": "user-1", "profile_md": "# me", "gemini_api_key_encrypted": "enc"}
    db = _auto(monkeypatch, [user], [_jobs(5), _jobs(3), _jobs(1)])
    finals = [r for r in db.runs if r.get("finished_at")]
    assert [r["mode"] for r in finals] == ["auto"] * 3
    assert [r["scored"] for r in finals] == [2, 2, 1]
    assert db.user_updates == []


def test_auto_stops_chaining_when_a_run_comes_up_short(monkeypatch):
    user = {"id": "user-1", "profile_md": "# me", "gemini_api_key_encrypted": "enc"}
    db = _auto(monkeypatch, [user], [_jobs(5), _jobs(5)], results=lambda i, b: _err(b))
    assert len([r for r in db.runs if r.get("finished_at")]) == 1


def test_auto_skips_users_without_profile_or_with_a_running_run(monkeypatch):
    fresh = datetime.now(timezone.utc).isoformat()
    users = [
        {"id": "no-profile", "profile_md": "", "gemini_api_key_encrypted": "enc"},
        {"id": "busy", "profile_md": "# me", "gemini_api_key_encrypted": "enc",
         "score_run": {"status": "running", "updated_at": fresh}},
    ]
    db = _auto(monkeypatch, users, [_jobs(2)])
    assert db.runs == [] and db.upserts == []


def test_auto_rereads_run_state_before_each_user(monkeypatch):
    # Snapshot says idle, but the user pressed Score now meanwhile.
    fresh = datetime.now(timezone.utc).isoformat()
    user = {"id": "user-1", "profile_md": "# me", "gemini_api_key_encrypted": "enc", "score_run": None}
    db = _auto(monkeypatch, [user], [_jobs(2)],
               stored_runs={"user-1": {"status": "running", "updated_at": fresh}})
    assert db.runs == [] and db.upserts == []


def test_second_auto_trigger_is_ignored_while_one_runs(monkeypatch):
    calls = []
    monkeypatch.setattr(scoring, "_run_auto_locked", lambda: calls.append(1))
    assert scoring._AUTO_LOCK.acquire(blocking=False)
    try:
        scoring._run_auto()
    finally:
        scoring._AUTO_LOCK.release()
    assert calls == []
    scoring._run_auto()
    assert calls == [1]
