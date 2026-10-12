"""sync_positions.py must keep working before migration 008 adds
positions.description: it retries the upsert without the column."""
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
