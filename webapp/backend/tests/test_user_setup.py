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


class _RecordingUsers:
    """users table stub recording update/insert calls; update matches `existing` rows."""

    def __init__(self, existing):
        self.existing, self.calls = existing, []

    def update(self, fields):
        self.calls.append(("update", fields))
        return _Query(self.existing)

    def insert(self, row):
        self.calls.append(("insert", row))
        return _Query([row])

    def __getattr__(self, name):  # select chain used by update_profile's version read
        return getattr(_Query(None), name)


def _save(monkeypatch, existing, email="me@example.com"):
    users = _RecordingUsers(existing)
    monkeypatch.setattr(user, "supabase", types.SimpleNamespace(table=lambda name: users))
    monkeypatch.setattr(user, "require_user_and_email", lambda auth: ("user-1", email))
    user.update_cv(user.CvUpdate(cv_text="my cv"), authorization="Bearer good")
    return [c[0] for c in users.calls], users.calls


def test_existing_user_save_updates_only(monkeypatch):
    kinds, _ = _save(monkeypatch, [{"id": "user-1"}])
    assert kinds == ["update"]


def test_missing_row_save_inserts_with_email(monkeypatch):
    kinds, calls = _save(monkeypatch, [])
    assert kinds == ["update", "insert"]
    assert calls[1][1]["email"] == "me@example.com" and calls[1][1]["id"] == "user-1"
    assert calls[1][1]["cv_text"] == "my cv"


def test_missing_row_without_email_is_noop(monkeypatch):
    kinds, _ = _save(monkeypatch, [], email=None)
    assert kinds == ["update"]


def test_profile_save_existing_user_updates_only(monkeypatch):
    users = _RecordingUsers([{"id": "user-1"}])
    monkeypatch.setattr(user, "supabase", types.SimpleNamespace(table=lambda name: users))
    monkeypatch.setattr(user, "require_user_and_email", lambda auth: ("user-1", "me@example.com"))
    d = user.update_profile(user.ProfileUpdate(profile_md="# me"), authorization="Bearer good")
    assert [c[0] for c in users.calls] == ["update"] and d["profile_version"] == 2
