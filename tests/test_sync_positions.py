"""sync_positions.py must keep working before migration 008 adds
positions.description: it retries the upsert without the column. It also
reconciles scored_jobs liveness from live_positions.json."""
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import sync_positions  # noqa: E402


def _run(tmp_path, monkeypatch, has_description_column: bool):
    jobs = [{"company": "Acme", "title": "DS", "location": "Tel Aviv, Israel",
             "description": "JD text", "apply_url": f"https://x/{i}"} for i in range(3)]
    path = tmp_path / "new_jobs.json"
    path.write_text(json.dumps(jobs), encoding="utf-8")
    posted: list[list[dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            body = json.loads(request.content)
            if not has_description_column and any("description" in r for r in body):
                return httpx.Response(400, json={"code": "PGRST204", "message": "Could not find the 'description' column of 'positions' in the schema cache"})
            posted.append(body)
            return httpx.Response(201)
        return httpx.Response(200, json=[])

    real_client = httpx.Client
    monkeypatch.setattr(sync_positions.httpx, "Client", lambda **kw: real_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setattr(sync_positions, "NEW_JOBS_PATH", path)
    monkeypatch.setattr(sync_positions, "LIVE_POSITIONS_PATH", tmp_path / "missing.json")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test")
    sync_positions.main()
    return posted


def test_syncs_description_when_column_exists(tmp_path, monkeypatch):
    posted = _run(tmp_path, monkeypatch, has_description_column=True)
    assert all(r["description"] == "JD text" for r in posted[0])


def test_falls_back_without_description_column(tmp_path, monkeypatch):
    posted = _run(tmp_path, monkeypatch, has_description_column=False)
    assert len(posted[0]) == 3
    assert all("description" not in r for r in posted[0])


def _reconcile(tmp_path, monkeypatch, live: dict | None, rows: list[dict]):
    if live is not None:
        live_path = tmp_path / "live_positions.json"
        live_path.write_text(json.dumps(live), encoding="utf-8")
        monkeypatch.setattr(sync_positions, "LIVE_POSITIONS_PATH", live_path)
    else:
        monkeypatch.setattr(sync_positions, "LIVE_POSITIONS_PATH", tmp_path / "missing.json")
    patches: list[tuple[str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH":
            patches.append((request.url.params["id"], json.loads(request.content)))
            return httpx.Response(204)
        offset = int(request.url.params.get("offset", 0))
        return httpx.Response(200, json=rows[offset:offset + sync_positions.PAGE_SIZE])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = sync_positions.reconcile_scored_jobs(client, "https://example.supabase.co", {}, "2026-10-13")
    return result, patches


def test_reconcile_closes_reopens_and_spares_failed_companies(tmp_path, monkeypatch):
    live = {"live_apply_urls": ["https://x/live", "https://x/back"], "successful_companies": ["Acme"]}
    rows = [
        {"id": 1, "apply_url": "https://x/live", "company": "Acme", "status": "open"},
        {"id": 2, "apply_url": "https://x/gone", "company": "acme", "status": "open"},
        {"id": 3, "apply_url": "https://x/back", "company": "Acme", "status": "closed"},
        {"id": 4, "apply_url": "https://x/other", "company": "FailedCo", "status": "open"},
        {"id": 5, "apply_url": "https://x/old", "company": "Acme", "status": "closed"},
    ]
    result, patches = _reconcile(tmp_path, monkeypatch, live, rows)
    assert result == (1, 1)
    assert patches == [
        ("in.(2)", {"status": "closed", "closed_at": "2026-10-13"}),
        ("in.(3)", {"status": "open", "closed_at": None}),
    ]


def test_reconcile_skips_without_live_positions(tmp_path, monkeypatch):
    rows = [{"id": 1, "apply_url": "https://x/gone", "company": "Acme", "status": "open"}]
    assert _reconcile(tmp_path, monkeypatch, None, rows) == ((0, 0), [])


def test_reconcile_pages_through_all_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(sync_positions, "PAGE_SIZE", 2)
    monkeypatch.setattr(sync_positions, "ID_BATCH", 2)
    live = {"live_apply_urls": [], "successful_companies": ["Acme"]}
    rows = [{"id": i, "apply_url": f"https://x/{i}", "company": "Acme", "status": "open"} for i in range(5)]
    result, patches = _reconcile(tmp_path, monkeypatch, live, rows)
    assert result == (5, 0)
    assert [p[0] for p in patches] == ["in.(0,1)", "in.(2,3)", "in.(4)"]


def test_reconcile_closes_old_unseen_jobs_from_uncollected_companies(tmp_path, monkeypatch):
    live = {"live_apply_urls": ["https://x/live"], "successful_companies": ["Acme"]}
    rows = [
        {"id": 1, "apply_url": "https://x/may", "company": "Dropped", "status": "open", "first_seen": "2026-05-02T08:00:00+00:00"},
        {"id": 2, "apply_url": "https://x/recent", "company": "Dropped", "status": "open", "first_seen": "2026-10-01"},
        {"id": 3, "apply_url": "https://x/nodate", "company": "Dropped", "status": "open", "first_seen": None},
        {"id": 4, "apply_url": "https://x/live", "company": "Dropped", "status": "open", "first_seen": "2026-05-02"},
    ]
    result, patches = _reconcile(tmp_path, monkeypatch, live, rows)
    assert result == (1, 0)
    assert patches == [("in.(1)", {"status": "closed", "closed_at": "2026-10-13"})]


def test_reconcile_age_rule_needs_live_urls(tmp_path, monkeypatch):
    # A run where nothing came back live must not age-close everything.
    live = {"live_apply_urls": [], "successful_companies": ["Acme"]}
    rows = [{"id": 1, "apply_url": "https://x/may", "company": "Dropped", "status": "open", "first_seen": "2026-05-02"}]
    assert _reconcile(tmp_path, monkeypatch, live, rows) == ((0, 0), [])


def test_reconcile_age_rule_spares_companies_whose_pull_failed(tmp_path, monkeypatch):
    live = {"live_apply_urls": ["https://x/live"], "successful_companies": ["Acme"],
            "failed_companies": ["Flaky"]}
    rows = [{"id": 1, "apply_url": "https://x/may", "company": "flaky", "status": "open", "first_seen": "2026-05-02"}]
    assert _reconcile(tmp_path, monkeypatch, live, rows) == ((0, 0), [])
