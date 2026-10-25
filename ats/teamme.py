"""
TeamMe ATS puller (Israeli niche ATS, e.g. Claroty, Quantum Machines).

No public API. Reverse-engineered approach: the tenant homepage at
    https://{tenant}.teamme.link/
is a Next.js SSR app that ships every open job inside the page as a
schema.org JobPosting JSON-LD object. The records are embedded inside
Next.js streaming chunks (`self.__next_f.push([1, "..."])`), so we
extract each chunk, JSON-decode it to unescape the inner JSON string,
concatenate, then regex-pull every JobPosting block.

Why not /careers? On some tenants (Claroty) the /careers route renders
an empty SPA shell while the root path returns the full SSR payload.
Both tenants we've seen serve data at "/". Falls back to /careers if
the root yields nothing.
"""

import json
import re
import sys

import httpx

try:
    from ats.utils import HEADERS, expand_country, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/teamme.py <tenant>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, expand_country, strip_html as _strip_html


# Captures every self.__next_f.push([1, "<escaped JSON-ish string>"]) call.
# Arg 1 is a JS array literal whose 2nd element is a JSON string; parsing
# the whole arg as JSON cleanly unescapes the embedded payload.
_PUSH_RE = re.compile(r'self\.__next_f\.push\((\[1,"(?:[^"\\]|\\.)*"\])\)')

# JobPosting JSON-LD record (non-greedy up to the closing url field).
_JOB_RE = re.compile(
    r'\{"@context":"https://schema\.org","@type":"JobPosting",.*?"url":"[^"]+"\}'
)


def _extract_jobpostings(html: str) -> list[dict]:
    """Return parsed JobPosting dicts from a TeamMe SSR HTML page."""
    chunks: list[str] = []
    for m in _PUSH_RE.finditer(html):
        try:
            arr = json.loads(m.group(1))
        except Exception:
            continue
        if isinstance(arr, list) and len(arr) >= 2 and isinstance(arr[1], str):
            chunks.append(arr[1])
    combined = "".join(chunks)
    if not combined:
        return []

    out: list[dict] = []
    for raw in _JOB_RE.findall(combined):
        try:
            out.append(json.loads(raw))
        except Exception:
            continue
    return out


def _location_str(jp: dict) -> str:
    """Flatten the schema.org jobLocation / applicantLocationRequirements field."""
    loc = jp.get("jobLocation")
    if isinstance(loc, list) and loc:
        loc = loc[0]
    if isinstance(loc, dict):
        addr = loc.get("address") or {}
        if isinstance(addr, dict):
            city = str(addr.get("addressLocality") or addr.get("addressRegion") or "").strip()
            country = str(addr.get("addressCountry") or "").strip()
            # addressCountry may be a bare ISO code — expand so location_filter
            # (a substring match) can match on the country name, not just the city.
            if len(country) == 2:
                country = expand_country(country)
            parts = [p for p in (city, country) if p]
            if len(parts) == 2 and parts[0].lower() == parts[1].lower():
                parts = parts[:1]
            if parts:
                return ", ".join(parts)
        name = loc.get("name")
        if name:
            return str(name)

    # Remote-only roles use applicantLocationRequirements instead of jobLocation
    alr = jp.get("applicantLocationRequirements")
    if isinstance(alr, dict):
        return str(alr.get("name") or "")
    if isinstance(alr, list) and alr:
        return str(alr[0].get("name") or "") if isinstance(alr[0], dict) else ""

    if jp.get("jobLocationType") == "TELECOMMUTE":
        return "Remote"
    return ""


def fetch_positions(tenant: str) -> list[dict]:
    """
    Fetch open positions from {tenant}.teamme.link.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error.
    """
    # Try the root first; tenants reliably embed JobPostings there.
    # Fall back to /careers in case a future tenant flips the layout.
    candidates = [
        f"https://{tenant}.teamme.link/",
        f"https://{tenant}.teamme.link/careers",
    ]

    postings: list[dict] = []
    for url in candidates:
        try:
            resp = httpx.get(url, timeout=15, headers=HEADERS, follow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            print(f"    TeamMe HTTP error for {tenant} ({url}): {e}")
            continue
        postings = _extract_jobpostings(resp.text)
        if postings:
            break

    if not postings:
        print(f"    TeamMe: no JobPostings found for tenant '{tenant}'")
        return []

    results: list[dict] = []
    seen_urls: set[str] = set()
    for jp in postings:
        url = jp.get("url") or ""
        if url in seen_urls:
            continue
        seen_urls.add(url)
        title = (jp.get("title") or "").strip()
        location = _location_str(jp)
        description = _strip_html(jp.get("description") or "")
        results.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": url,
            }
        )
    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run ats/teamme.py <tenant>")
        sys.exit(1)

    tenant = sys.argv[1]
    print(f"Fetching TeamMe postings for: {tenant}")
    jobs = fetch_positions(tenant)
    print(f"Found {len(jobs)} job(s)")
    for i, job in enumerate(jobs[:5]):
        print(f"  [{i + 1}] {job['title']} - {job['location']}")
        print(f"       {job['apply_url']}")
    if len(jobs) > 5:
        print(f"  ... and {len(jobs) - 5} more")
