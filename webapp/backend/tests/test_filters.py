"""db/filters.passes_filters and the Digest's outside_filters flag on GET /jobs/.

Run from webapp/backend:  uv run --with pytest python -m pytest tests -q
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if "db.supabase_client" not in sys.modules:
    _stub = types.ModuleType("db.supabase_client")
    _stub.supabase = types.SimpleNamespace()
    sys.modules["db.supabase_client"] = _stub

from db import filters  # noqa: E402
from routers import jobs  # noqa: E402

CFG = {"location_terms": ["israel", "herzliya"], "skip_title_terms": ["product manager"],
       "keep_title_terms": ["data scientist", "ai engineer"], "skip_companies": ["badco"]}


def _job(title="Senior Data Scientist", location="Tel Aviv, Israel", company="Acme"):
    return {"title": title, "location": location, "company": company}


def test_no_filters_passes_everything():
    assert filters.passes_filters(_job(location="San Francisco"), {})


def test_any_location_term_matches():
    assert filters.passes_filters(_job(location="Herzliya"), CFG)
    assert filters.passes_filters(_job(location="Tel Aviv, Israel"), CFG)
    assert not filters.passes_filters(_job(location="San Francisco"), CFG)


def test_title_and_company_rules():
    assert not filters.passes_filters(_job(title="Product Manager, Data Scientist tools"), CFG)
    assert not filters.passes_filters(_job(title="Backend Engineer"), CFG)
    assert not filters.passes_filters(_job(company="BadCo Ltd"), CFG)


def test_blank_terms_are_ignored():
    assert filters.passes_filters(_job(location="San Francisco"), {"location_terms": ["", "  "]})


class _Q:
    def __init__(self, data):
        self.data = data

    def __getattr__(self, name):
        return lambda *a, **k: self

    def execute(self):
        return self


def test_list_jobs_flags_rows_outside_filters(monkeypatch):
    rows = [dict(_job(), id="1"), dict(_job(location="Remote - United States"), id="2")]
    monkeypatch.setattr(jobs, "supabase", types.SimpleNamespace(table=lambda n: _Q(rows)))
    monkeypatch.setattr(jobs, "load_filters", lambda uid: CFG)
    monkeypatch.setattr(jobs, "_get_user", lambda a: "user-1")
    out = jobs.list_jobs(authorization="Bearer good")
    assert [(r["id"], r["outside_filters"]) for r in out] == [("1", False), ("2", True)]
