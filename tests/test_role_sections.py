"""Role sections: split at collect time (ats/utils.py), stored next to the unchanged
`description`, and read by the Gemini prompt (matcher/gemini_scorer.py)."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import collect_jobs  # noqa: E402
from ats.utils import (  # noqa: E402
    DESCRIPTION_CHARS,
    SECTION_CHARS,
    job_sections,
    sections_from_named,
    split_sections,
)
from matcher import gemini_scorer  # noqa: E402

PITCH = "Acme builds the future of payments for millions of merchants worldwide. " * 6
ROLE = ("About the Role As a Senior Data Scientist you will own our fraud models end to end, "
        "working with product and engineering to ship detection to production. ")
RESP = "Responsibilities: Build fraud models. Ship them weekly. Mentor two juniors. "
REQ = "Requirements: 5+ years Python. Production ML experience. SQL. "
EEO = "Acme is an equal opportunity employer and values diversity of every kind."
POST = PITCH + ROLE + RESP + REQ + EEO


# ---------------------------------------------------------------------------
# split_sections - flat text
# ---------------------------------------------------------------------------

def test_split_drops_pitch_and_boilerplate_and_separates_requirements():
    s = split_sections(POST)
    assert s["role_description"].startswith("About the Role")
    assert "Acme builds" not in s["role_description"]
    assert "equal opportunity" not in s["role_description"] + s["requirements"]
    assert s["responsibilities"].startswith("Responsibilities:") and "Mentor" in s["responsibilities"]
    assert s["requirements"].startswith("Requirements:") and "SQL" in s["requirements"]
    # role + requirements cover the role without repeating the requirements block
    assert "5+ years" not in s["role_description"]
    assert "Mentor" in s["role_description"]


def test_split_requirements_before_responsibilities():
    s = split_sections(PITCH + ROLE + REQ + RESP)
    assert "SQL" in s["requirements"] and "Mentor" not in s["requirements"]
    assert "Mentor" in s["responsibilities"]
    assert "Mentor" in s["role_description"] and "5+ years" not in s["role_description"]


def test_prose_words_are_not_headings():
    prose = ROLE + "You will review schematics for compilation requirements and take on responsibilities as needed. " * 2
    s = split_sections(PITCH + prose)
    assert s["requirements"] == "" and s["responsibilities"] == ""
    assert "compilation requirements" in s["role_description"]


def test_no_marker_keeps_full_text():
    text = "Join a great team building great things. " * 10
    s = split_sections(text)
    assert s["role_description"] == " ".join(text.split())
    assert s["responsibilities"] == "" and s["requirements"] == ""


def test_looking_for_needs_an_article():
    """A pitch line ("we're looking for talented people") is not the role start."""
    text = ("We're looking for talented people to join our mission. " + PITCH
            + "We're looking for a Senior ML Engineer to lead our detection platform and own it. " * 3)
    assert split_sections(text)["role_description"].startswith("We're looking for a Senior ML Engineer")


def test_html_entities_and_mojibake_apostrophe():
    text = PITCH.replace(" ", "&nbsp;") + "We�re looking for a Data Scientist to build models for us. " * 4
    s = split_sections(text)
    assert "&nbsp;" not in s["role_description"]
    assert s["role_description"].startswith("We�re looking for a Data Scientist")


def test_hebrew_sections():
    text = ("על החברה: אנחנו חברת סייבר מובילה עם לקוחות בכל העולם. " * 4
            + "תיאור התפקיד: אנו מחפשים מדען נתונים בכיר שיוביל את מודלי ההונאה שלנו מקצה לקצה. " * 3
            + "דרישות: חמש שנות ניסיון בפייתון. ניסיון בהעברת מודלים לייצור.")
    s = split_sections(text)
    assert s["role_description"].startswith("תיאור התפקיד")
    assert "על החברה" not in s["role_description"]
    assert s["requirements"].startswith("דרישות") and "פייתון" in s["requirements"]


# ---------------------------------------------------------------------------
# named sections (Comeet details, Lever lists, Amazon qualifications)
# ---------------------------------------------------------------------------

def test_named_sections_map_by_heading():
    s = sections_from_named([
        ("Description", "Lead our fraud data science team."),
        ("Responsibility", "Own the roadmap."),
        ("Requirements", "7+ years ML."),
        ("Who You Are", "A hands-on leader."),
        ("About the Team", "We are 12 people."),
    ])
    assert s["role_description"] == "Lead our fraud data science team. Own the roadmap."
    assert s["responsibilities"] == "Own the roadmap."
    assert s["requirements"] == "7+ years ML. A hands-on leader."
    assert "12 people" not in json.dumps(s)


def test_named_sections_without_requirements_split_inline():
    s = sections_from_named([("Description", PITCH + ROLE + RESP + REQ)])
    assert "SQL" in s["requirements"] and "Acme builds" not in s["role_description"]


def test_amazon_style_qualifications():
    s = sections_from_named([("Description", "Build recommendation models."),
                             ("Basic qualifications", "PhD or 3+ years."),
                             ("Preferred qualifications", "Publications.")])
    assert s["requirements"] == "PhD or 3+ years. Publications."


def test_job_sections_caps_each_field():
    s = job_sections("", {"role_description": "r" * 9000, "requirements": "q" * 9000})
    assert len(s["role_description"]) == SECTION_CHARS and len(s["requirements"]) == SECTION_CHARS
    assert s["responsibilities"] == ""


# ---------------------------------------------------------------------------
# pullers + collect_jobs
# ---------------------------------------------------------------------------

def test_comeet_keeps_requirements_in_sections_but_description_unchanged():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = [{
        "name": "DS", "is_internal": False, "location": {"name": "Tel Aviv", "country": "IL"},
        "url_comeet_hosted_page": "https://x.comeet.co/jobs/1",
        "details": [{"name": "Description", "value": "<p>Build models.</p>"},
                    {"name": "Requirements", "value": "<ul><li>5 years</li></ul>"}],
    }]
    with patch("httpx.get", return_value=resp):
        from ats.comeet import fetch_positions
        job = fetch_positions("uid", "tok")[0]
    assert job["description"] == "Build models."
    assert job["sections"]["requirements"] == "5 years"


def test_lever_lists_become_sections():
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = [{
        "text": "DS", "categories": {"location": "Tel Aviv"}, "hostedUrl": "https://jobs.lever.co/x/1",
        "descriptionPlain": "Build models.",
        "lists": [{"text": "What you'll do", "content": "<li>Ship</li>"},
                  {"text": "Requirements", "content": "<li>Python</li>"}],
    }]
    with patch("httpx.get", return_value=resp):
        from ats.lever import fetch_positions
        job = fetch_positions("x")[0]
    assert job["description"] == "Build models."
    assert job["sections"]["requirements"] == "Python"
    assert job["sections"]["responsibilities"] == "Ship"


@pytest.fixture
def in_tmp(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "companies.json").write_text(json.dumps([{
        "name": "Acme", "website": "https://acme.io", "source_vc": "YL Ventures", "vc_tier": 1,
        "careers_url": "https://acme.io/careers", "ats": "fake", "ats_params": {"x": 1},
        "consecutive_failures": 0,
    }]), encoding="utf-8")
    return tmp_path


def test_collect_splits_full_text_and_caps_description(in_tmp, monkeypatch):
    long_post = PITCH * 10 + ROLE + RESP + REQ  # requirements sit past the 4000-char cap
    assert len(long_post) > DESCRIPTION_CHARS
    monkeypatch.setitem(collect_jobs.ATS_PULLERS, "fake", lambda p: [
        {"title": "DS", "location": "Tel Aviv, Israel", "description": long_post, "apply_url": "https://acme.io/1"}])
    collect_jobs.collect()
    job = json.loads((in_tmp / "new_jobs.json").read_text(encoding="utf-8"))[0]
    assert job["description"] == long_post[:DESCRIPTION_CHARS]  # what it always was
    assert "SQL" in job["requirements"]  # recovered from past the cap
    assert job["role_description"].startswith("About the Role")


def test_collect_prefers_puller_sections(in_tmp, monkeypatch):
    monkeypatch.setitem(collect_jobs.ATS_PULLERS, "fake", lambda p: [
        {"title": "DS", "location": "Tel Aviv, Israel", "description": "d", "apply_url": "https://acme.io/1",
         "sections": {"role_description": "role", "responsibilities": "", "requirements": "reqs"}}])
    collect_jobs.collect()
    job = json.loads((in_tmp / "new_jobs.json").read_text(encoding="utf-8"))[0]
    assert (job["role_description"], job["requirements"], job["description"]) == ("role", "reqs", "d")


# ---------------------------------------------------------------------------
# Gemini prompt
# ---------------------------------------------------------------------------

JOB = {"company": "Acme", "title": "DS", "location": "Tel Aviv", "description": "FULL DESC",
       "apply_url": "https://acme.io/1"}


def test_prompt_uses_role_and_requirements():
    prompt = gemini_scorer.build_batch_prompt([{**JOB, "role_description": "ROLE TEXT", "requirements": "REQ TEXT"}], "p", "c")
    assert "Role: ROLE TEXT" in prompt and "Requirements: REQ TEXT" in prompt
    assert "FULL DESC" not in prompt


def test_prompt_falls_back_to_description_without_sections():
    """Jobs collected before the split (and webapp catalog rows) get the old prompt."""
    prompt = gemini_scorer.build_batch_prompt([JOB], "p", "c")
    assert "  Description: FULL DESC" in prompt and "Role:" not in prompt
    single = gemini_scorer.build_prompt(JOB, "p", "c")
    assert "Description: FULL DESC" in single


def test_scorer_text_description_reproduces_old_prompt(monkeypatch):
    monkeypatch.setattr(gemini_scorer, "SCORER_TEXT", "description")
    with_secs = {**JOB, "role_description": "ROLE TEXT", "requirements": "REQ TEXT"}
    assert gemini_scorer.build_batch_prompt([with_secs], "p", "c") == gemini_scorer.build_batch_prompt([JOB], "p", "c")


# ---------------------------------------------------------------------------
# regressions from the 2026-10-21 second sheet
# ---------------------------------------------------------------------------

def test_named_description_section_is_trimmed_of_pitch():
    """Comeet's "Description" section often opens with the company pitch itself."""
    s = sections_from_named([("Description", PITCH + ROLE * 2), ("Requirements", "5+ years.")])
    assert s["role_description"].startswith("About the Role")
    assert s["requirements"] == "5+ years."


def test_heading_words_in_prose_are_not_role_start():
    text = ("Join us for the opportunity to make a meaningful impact with exceptional people. " + PITCH
            + "We're looking for a Senior Data Scientist to drive our product analytics and models. " * 3)
    assert split_sections(text)["role_description"].startswith("We're looking for a Senior Data Scientist")


def test_looking_for_someone_is_role_start():
    text = PITCH + "We're looking for someone who has worked on both engineering and product sides. " * 4
    assert split_sections(text)["role_description"].startswith("We're looking for someone")
