"""require_user + the JSON-500 middleware.

Run from webapp/backend:  uv run --with pytest python -m pytest tests -q

Supabase is stubbed - no network, no secrets needed.
"""
import sys
import types
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))


class _Auth:
    def get_user(self, token):
        if token == "good":
            return types.SimpleNamespace(user=types.SimpleNamespace(id="user-1"))
        if token == "empty":
            return types.SimpleNamespace(user=None)
        raise RuntimeError("invalid JWT: token is malformed")  # what supabase-py does


_stub = types.ModuleType("db.supabase_client")
_stub.supabase = types.SimpleNamespace(auth=_Auth())
sys.modules["db.supabase_client"] = _stub

from auth import require_user  # noqa: E402


def test_valid_token_returns_user_id():
    assert require_user("Bearer good") == "user-1"


@pytest.mark.parametrize("header", ["Bearer bad", "Bearer empty", "Bearer ", "", None])
def test_bad_tokens_raise_401(header):
    with pytest.raises(HTTPException) as exc:
        require_user(header)
    assert exc.value.status_code == 401
    assert "malformed" not in exc.value.detail  # upstream error text never leaks


def test_app_returns_401_and_json_500_with_cors():
    import main

    @main.app.get("/__boom")
    def boom():
        raise RuntimeError("secret-ish internals")

    client = TestClient(main.app, raise_server_exceptions=False)
    origin = {"Origin": "https://careerwatch-frontend.onrender.com"}

    r = client.get("/user/me", headers={**origin, "Authorization": "Bearer bad"})
    assert r.status_code == 401
    assert r.headers.get("access-control-allow-origin")

    r = client.get("/__boom", headers=origin)
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin")
    assert "secret-ish" not in r.text
    assert r.json()["detail"]
