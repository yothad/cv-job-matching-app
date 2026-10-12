"""
score.py must exit non-zero when GEMINI_API_KEY is missing.

Regression: it used to print "[omer] Error: GEMINI_API_KEY not set." and exit 0,
so the CI workflow stayed green for ~2 months while nothing was scored.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent


def _make_profile(tmp_path: Path) -> tuple[Path, Path]:
    profiles = tmp_path / "profiles"
    p = profiles / "tester"
    p.mkdir(parents=True)
    (p / "profile.md").write_text("# profile", encoding="utf-8")
    (p / "cv.md").write_text("# cv", encoding="utf-8")
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps([{
        "company": "Acme", "title": "Data Scientist", "location": "Tel Aviv, Israel",
        "description": "x", "apply_url": "https://example.com/1",
    }]), encoding="utf-8")
    return profiles, jobs


def _run(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k != "GEMINI_API_KEY"}
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "score.py"), *args],
        cwd=tmp_path, env={**env, "PYTHONPATH": str(REPO_ROOT)},
        capture_output=True, text=True, timeout=60,
    )


def test_missing_api_key_exits_nonzero(tmp_path):
    profiles, jobs = _make_profile(tmp_path)
    result = _run(["--profiles-dir", str(profiles), "--input", str(jobs)], tmp_path)
    assert result.returncode != 0
    assert "GEMINI_API_KEY not set" in result.stderr


def test_missing_api_key_rescore_exits_nonzero(tmp_path):
    profiles, _ = _make_profile(tmp_path)
    (profiles / "tester" / "scored_jobs.json").write_text(json.dumps([
        {"company": "Acme", "title": "DS", "apply_url": "https://example.com/1", "score": 5},
    ]), encoding="utf-8")
    result = _run(["--profiles-dir", str(profiles), "--rescore"], tmp_path)
    assert result.returncode != 0
    assert "GEMINI_API_KEY not set" in result.stderr


def test_dry_run_without_key_still_succeeds(tmp_path):
    profiles, jobs = _make_profile(tmp_path)
    result = _run(["--profiles-dir", str(profiles), "--input", str(jobs), "--dry-run"], tmp_path)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# CV path fallback: score_config.json may point at local-only files (absolute
# Mac paths) that don't exist in CI. Must fall back, not FileNotFoundError.
# ---------------------------------------------------------------------------

from score import _resolve_cvs  # noqa: E402


def test_missing_configured_cvs_fall_back(tmp_path, capsys):
    (tmp_path / "cv.md").write_text("repo cv", encoding="utf-8")
    config = {"cv_default": "/nonexistent/default.docx", "cv_lead": "/nonexistent/lead.docx"}
    cv_default, cv_lead = _resolve_cvs(tmp_path, config, "tester")
    assert cv_default == "repo cv"
    assert cv_lead == "repo cv"
    out = capsys.readouterr().out
    assert "cv_default not found" in out and "cv_lead not found" in out


def test_existing_configured_cvs_are_used(tmp_path):
    (tmp_path / "cv.md").write_text("repo cv", encoding="utf-8")
    (tmp_path / "default.md").write_text("default cv", encoding="utf-8")
    (tmp_path / "lead.md").write_text("lead cv", encoding="utf-8")
    config = {"cv_default": str(tmp_path / "default.md"), "cv_lead": str(tmp_path / "lead.md")}
    assert _resolve_cvs(tmp_path, config, "tester") == ("default cv", "lead cv")


def test_missing_lead_falls_back_to_configured_default(tmp_path):
    (tmp_path / "default.md").write_text("default cv", encoding="utf-8")
    config = {"cv_default": str(tmp_path / "default.md"), "cv_lead": "/nonexistent/lead.docx"}
    assert _resolve_cvs(tmp_path, config, "tester") == ("default cv", "default cv")
