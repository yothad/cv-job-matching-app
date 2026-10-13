"""score.py:_prune_closed keeps scored_jobs.json from growing forever."""
from score import _prune_closed


def _jobs():
    return {
        "old": {"status": "closed", "closed_at": "2026-08-01"},
        "old-applied": {"status": "closed", "closed_at": "2026-08-01", "applied": True},
        "recent": {"status": "closed", "closed_at": "2026-10-01"},
        "edge": {"status": "closed", "closed_at": "2026-09-13"},
        "no-date": {"status": "closed"},
        "open": {"status": "open"},
    }


def test_prunes_only_old_unapplied_closed():
    jobs = _jobs()
    assert _prune_closed(jobs, "2026-10-13") == 1
    assert set(jobs) == {"old-applied", "recent", "edge", "no-date", "open"}


def test_retention_window_is_configurable():
    jobs = _jobs()
    assert _prune_closed(jobs, "2026-10-13", days=5) == 3
    assert set(jobs) == {"old-applied", "no-date", "open"}
