HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


def strip_html(text: str) -> str:
    import re
    return re.sub(r"<[^>]+>", " ", text).strip()


# ISO-3166 alpha-2 -> country name. location_filter is a plain substring match,
# so a location that carries only a bare ISO code ("Tel Aviv, IL") is silently
# dropped by an "israel" filter. Pullers expand the code so the country name is
# present in the location string.
ISO_COUNTRY = {
    "IL": "Israel", "US": "United States", "GB": "United Kingdom", "DE": "Germany",
    "FR": "France", "IN": "India", "PL": "Poland", "NL": "Netherlands", "CA": "Canada",
    "AU": "Australia", "SG": "Singapore", "ES": "Spain", "IE": "Ireland", "IT": "Italy",
    "JP": "Japan", "BR": "Brazil", "CO": "Colombia", "HK": "Hong Kong", "PT": "Portugal",
    "SE": "Sweden", "CH": "Switzerland", "RO": "Romania", "CZ": "Czech Republic",
}


def expand_country(code: str) -> str:
    """Map a 2-letter ISO-3166 alpha-2 code to its country name; pass through anything else."""
    if not code:
        return code
    return ISO_COUNTRY.get(code.strip().upper(), code)


def qualify_location(location: str) -> str:
    """
    Append the full country name when a location string carries a bare ISO country
    code but not the country name itself (e.g. "Ra'anana, IL, 4366202" -> ".., Israel").
    Fixes the location_filter substring gotcha for ATSes that emit ISO codes.
    """
    if not location:
        return location
    for part in location.split(","):
        code = part.strip()
        if len(code) == 2 and code.upper() in ISO_COUNTRY:
            country = ISO_COUNTRY[code.upper()]
            if country.lower() not in location.lower():
                return f"{location}, {country}"
    return location


# ---------------------------------------------------------------------------
# Role sections. Most posts open with a company pitch and close with benefits / EEO
# boilerplate; the role sits in between. strip_html flattens paragraphs, so sections are
# found by headings. collect_jobs.py stores each section capped at SECTION_CHARS next to
# the unchanged `description` (capped at DESCRIPTION_CHARS).
# ---------------------------------------------------------------------------

import html as _html
import re as _re

DESCRIPTION_CHARS = 4000
SECTION_CHARS = 4000
SECTION_KEYS = ("role_description", "responsibilities", "requirements")

_APOS = "['’�]?"  # ' or a curly ' or the U+FFFD that a mis-decoded curly ' becomes

# Where the role starts: the earliest role heading or role-opening phrase ("We are looking for
# an MLOps Team Lead" often precedes "Responsibilities"). Headings must look like headings
# (see _find_heading) so pitch prose - "the opportunity to make an impact" - doesn't match.
# Looking-for phrases need "a/an" so "we're looking for talented people" doesn't count.
# Failing both, the requirements heading is the start (better than the company pitch).
_ROLE_HEADINGS = [r"about the (?:role|position|job)", r"the role", r"role overview", r"position overview",
                  r"job description", r"the opportunity", r"your role", r"your mission", r"the position",
                  rf"what you{_APOS}ll (?:do|be doing)", r"what you will (?:do|be doing)",
                  r"key responsibilities", r"responsibilities", r"day[- ]to[- ]day",
                  r"תיאור התפקיד", r"על התפקיד", r"מה תעשו", r"מה תעשה", r"תחומי אחריות"]
_ROLE_PHRASES = [rf"we{_APOS}re (?:looking for|seeking|hiring) (?:an?|someone)",
                 r"we are (?:looking for|seeking|hiring) (?:an?|someone)",
                 r"in this role", r"(?i:as an?) [A-Z][\w-]*",  # "As a Data Scientist", not "as a company"
                 r"אנו מחפשים", r"אנחנו מחפשים", r"דרוש/ה", r"דרושה", r"דרוש"]
_REQ_START = [r"requirements", r"qualifications", rf"what you{_APOS}ll bring", r"who you are",
              r"about you", r"דרישות"]
# Section headings inside the role. English ones must look like a heading - capitalised or
# followed by ":" - so prose ("compilation requirements", "with responsibilities that") is skipped.
_RESP_HEADINGS = [r"key responsibilities", r"your responsibilities", r"responsibilities",
                  r"responsibility", rf"what you{_APOS}ll (?:do|be doing)",
                  r"what you will (?:do|be doing)", r"day[- ]to[- ]day",
                  r"תחומי אחריות", r"מה תעשו", r"מה תעשה"]
_REQ_HEADINGS = [r"requirements", r"qualifications", r"required skills", r"must have",
                 rf"what you{_APOS}ll (?:bring|need)", r"what you bring", r"who you are",
                 r"about you", rf"what we{_APOS}re looking for", r"what we are looking for",
                 r"דרישות התפקיד", r"דרישות", r"כישורים"]
# Trailing boilerplate; cut here only if it comes well after the start.
_END = [r"equal opportunity", r"equal employment", r"what we offer", r"why join",
        r"our benefits", r"benefits (?:&|and) perks", r"perks (?:&|and) benefits",
        r"we offer", r"diversity,? equity", r"privacy (?:notice|policy)", r"הזדמנות שווה"]
_MIN_ROLE_CHARS = 200

_END_RE = _re.compile(r"(?<!\w)(?:" + "|".join(_END) + r")(?!\w)", _re.IGNORECASE)


def _heading_re(patterns: list[str]):
    return _re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)(\s*:)?", _re.IGNORECASE)


_ROLE_HEADING_RE = _heading_re(_ROLE_HEADINGS)
_ROLE_PHRASE_RES = [_re.compile(rf"(?<!\w){p}(?!\w)", 0 if "[A-Z]" in p else _re.IGNORECASE)
                    for p in _ROLE_PHRASES]
_REQ_START_RE = _heading_re(_REQ_START)
_RESP_RE = _heading_re(_RESP_HEADINGS)
_REQ_RE = _heading_re(_REQ_HEADINGS)


def flatten_text(text: str) -> str:
    """Decode HTML entities (&nbsp; etc.) and collapse whitespace to single spaces."""
    return " ".join(_html.unescape(text or "").split())


def _heading_match(rx, text: str):
    """First match that looks like a heading - capitalised, followed by ":", or non-Latin
    (Hebrew has no case) - or None. Skips the same words used in prose."""
    for m in rx.finditer(text):
        word = m.group(0)
        if m.group(1) or not word.isascii() or word[0].isupper():
            return m
    return None


def _find_heading(rx, text: str) -> int:
    m = _heading_match(rx, text)
    return m.start() if m else -1


def find_role_start(text: str, include_requirements: bool = True) -> tuple[int, str]:
    """(start offset, matched marker) of the role section in flat text, or (0, "") if none."""
    hits = [m for m in [_heading_match(_ROLE_HEADING_RE, text)] if m]
    hits += [m for rx in _ROLE_PHRASE_RES for m in [rx.search(text)] if m]
    if not hits and include_requirements:
        hits = [m for m in [_heading_match(_REQ_START_RE, text)] if m]
    if not hits:
        return 0, ""
    m = min(hits, key=lambda m: m.start())
    return m.start(), m.group(0).rstrip(": ")


def trim_role(flat: str) -> str:
    """Cut the company pitch before the role start and boilerplate after it. Returns the text
    unchanged when no role marker is found or what would remain is too short to trust."""
    start, marker = find_role_start(flat, include_requirements=False)
    body = flat[start:] if marker else flat
    end = _END_RE.search(body, _MIN_ROLE_CHARS)
    if end:
        body = body[:end.start()]
    body = body.strip()
    return body if len(body) >= _MIN_ROLE_CHARS else flat


def split_sections(text: str) -> dict[str, str]:
    """Split a flat-text job description into role_description / responsibilities / requirements.

    role_description runs from the role start to the trailing boilerplate minus the
    requirements block, so role_description + requirements cover the role without repeating
    text. With no role marker at all, role_description is the whole text and the others are "".
    Values are uncapped; job_sections() caps them.
    """
    flat = flatten_text(text)
    start, marker = find_role_start(flat)
    body = flat[start:]
    end = _END_RE.search(body, _MIN_ROLE_CHARS)
    if end:
        body = body[:end.start()]
    body = body.strip()
    if not marker or len(body) < _MIN_ROLE_CHARS:
        return {"role_description": flat, "responsibilities": "", "requirements": ""}

    resp_at, req_at = _find_heading(_RESP_RE, body), _find_heading(_REQ_RE, body)
    requirements = responsibilities = ""
    if req_at >= 0:
        stop = resp_at if resp_at > req_at else len(body)
        requirements = body[req_at:stop].strip()
    if resp_at >= 0:
        stop = req_at if req_at > resp_at else len(body)
        responsibilities = body[resp_at:stop].strip()
    role = body
    if req_at >= 0:  # drop the requirements block from the role text
        role = (body[:req_at] + (" " + body[resp_at:] if resp_at > req_at else "")).strip()
    return {"role_description": role, "responsibilities": responsibilities, "requirements": requirements}


# Named sections (Comeet details, Lever lists) map to keys by their heading; no guessing needed.
_SKIP_NAMES = _re.compile(r"about (?:us|the (?:team|company))|benefits|perks|why join|our offer|"
                          r"equal opportunity|על החברה|הטבות", _re.IGNORECASE)
_RESP_NAMES = _re.compile(rf"responsib|what you{_APOS}ll do|what you will do|day[- ]to[- ]day|"
                          r"אחריות|מה תעש", _re.IGNORECASE)
_REQ_NAMES = _re.compile(rf"requirement|qualification|who you are|about you|you bring|you{_APOS}ll need|"
                         r"must have|nice to have|skills|looking for|דרישות|כישורים", _re.IGNORECASE)


def sections_from_named(parts: list[tuple[str, str]]) -> dict[str, str]:
    """Build the three sections from (heading, plain text) pairs, e.g. Comeet details.

    Responsibility sections go to responsibilities AND role_description; requirement sections
    to requirements; company / benefits sections are dropped; anything else (Description, What
    Success Looks Like, ...) goes to role_description. When no named requirements exist, the
    combined role text is split by headings instead (many posts inline "Requirements:").
    """
    role, resp, req = [], [], []
    for name, text in parts:
        text = flatten_text(text)
        if not text or _SKIP_NAMES.search(name or ""):
            continue
        if _REQ_NAMES.search(name or ""):
            req.append(text)
        elif _RESP_NAMES.search(name or ""):
            resp.append(text)
            role.append(text)
        else:
            role.append(text)
    if not req:
        out = split_sections(" ".join(role))
        if resp and not out["responsibilities"]:
            out["responsibilities"] = " ".join(resp)
        return out
    # A "Description" section often opens with the company pitch too (Comeet), so trim it the
    # same way as flat text; the named requirements are already separate.
    return {"role_description": trim_role(" ".join(role)), "responsibilities": " ".join(resp),
            "requirements": " ".join(req)}


def job_sections(description: str, named: dict[str, str] | None = None) -> dict[str, str]:
    """The three section fields for a job, each capped at SECTION_CHARS.

    `named` is a puller-supplied sections dict (Comeet, Lever); otherwise the full
    description is split by headings.
    """
    secs = named if named else split_sections(description)
    return {k: (secs.get(k) or "")[:SECTION_CHARS] for k in SECTION_KEYS}
