"""scripts/push_scores_to_webapp.py: which pipeline scores reach the webapp."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import push_scores_to_webapp as push  # noqa: E402


def test_parse_mapping():
    assert push.parse_mapping(" omer=A@x.com , bad, other=b@y.io") == {"omer": "a@x.com", "other": "b@y.io"}
    assert push.parse_mapping("") == {}


def test_latest_scores_keeps_last_good_record(tmp_path):
    p = tmp_path / "all_scores.jsonl"
    lines = [
        {"apply_url": "u1", "score": 4, "flags": []},
        {"apply_url": "u1", "score": 7, "flags": []},
        {"apply_url": "u1", "score": 0, "flags": ["scorer-error"]},
        {"apply_url": "u2", "score": 0, "flags": ["scorer-error"]},
        {"apply_url": "", "score": 5, "flags": []},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\nnot json\n", encoding="utf-8")
    best = push.latest_scores(p)
    assert set(best) == {"u1"} and best["u1"]["score"] == 7
    assert push.latest_scores(tmp_path / "missing.jsonl") == {}


def test_build_rows_only_live_and_new_or_description_less():
    scores = {u: {"score": "8", "flags": ["applied-ai"], "description": "JD", "company": "Acme"}
              for u in ("new", "dull", "good", "gone")}
    existing = {"dull": "", "good": "already has JD"}
    rows = push.build_rows({"id": "user-1", "profile_version": 3}, scores, {"new", "dull", "good"}, existing, "now")
    assert sorted(r["apply_url"] for r in rows) == ["dull", "new"]
    r = rows[0]
    assert r["score"] == 8 and r["profile_version"] == 3 and r["scored_at"] == "now"
    assert "applied" not in r and "status" not in r


def test_build_rows_never_repushes_description_less_over_description_less():
    scores = {"both-bare": {"score": 6, "flags": [], "description": ""},
              "new-bare": {"score": 6, "flags": [], "description": ""}}
    rows = push.build_rows({"id": "u"}, scores, {"both-bare", "new-bare"}, {"both-bare": ""}, "now")
    assert [r["apply_url"] for r in rows] == ["new-bare"]
