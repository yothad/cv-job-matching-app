"""GET /user/me derived `setup` object (first-login journey).

Run from webapp/backend:  uv run --with pytest python -m pytest tests -q

Supabase is stubbed - no network, no secrets needed.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if "db.supabase_client" not in sys.modules:
    _stub = types.ModuleType("db.supabase_client")
    _stub.supabase = types.SimpleNamespace()
    sys.modules["db.supabase_client"] = _stub

from routers import user  # noqa: E402


class _Query:
    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):  # select/eq/limit/maybe_single - all chain
        return lambda *a, **k: self

    def execute(self):
        return types.SimpleNamespace(data=self._data)


def _fake_supabase(users_row, filters_rows):
    tables = {"users": users_row, "score_configs": filters_rows}
    return types.SimpleNamespace(table=lambda name: _Query(tables[name]))


def _me(monkeypatch, users_row, filters_rows):
    monkeypatch.setattr(user, "supabase", _fake_supabase(users_row, filters_rows))
    monkeypatch.setattr(user, "require_user", lambda auth: "user-1")
    monkeypatch.setattr(user, "FERNET_KEY", "")
    return user.get_me(authorization="Bearer good")


def test_brand_new_user_gets_incomplete_setup(monkeypatch):
    d = _me(monkeypatch, None, [])
    assert d == {"setup": {"profile": False, "cv": False, "api_key": False, "filters_seen": False, "complete": False}}


def test_profile_only_is_incomplete(monkeypatch):
    d = _me(monkeypatch, {"profile_md": "# me", "cv_text": "  ", "gemini_api_key_encrypted": None}, [])
    assert d["setup"] == {"profile": True, "cv": False, "api_key": False, "filters_seen": False, "complete": False}


def test_profile_and_key_is_complete_and_key_never_returned(monkeypatch):
    d = _me(monkeypatch, {"profile_md": "# me", "cv_text": "", "gemini_api_key_encrypted": "gAAAA-secret"}, [{"user_id": "user-1"}])
    assert d["setup"] == {"profile": True, "cv": False, "api_key": True, "filters_seen": True, "complete": True}
    assert "gemini_api_key_encrypted" not in d
    assert "gAAAA-secret" not in repr(d)


def test_key_without_profile_is_incomplete():
    s = user.derive_setup({"gemini_api_key_encrypted": "x", "cv_text": "cv"}, False)
    assert s["api_key"] and s["cv"] and not s["complete"]
