"""
Google Careers puller (proprietary SPA - no public ATS API).

Implementation note: Google's public careers UI lives at
https://www.google.com/about/careers/applications/jobs/results
and has no documented JSON endpoint. The page is rendered server-side and
embeds search results in an `AF_initDataCallback({key: 'ds:1', ..., data:[...]})`
block - we extract that array directly from the HTML. The careers.google.com/api/v3
endpoint mentioned in older docs returns 404.

Data shape (per job, observed 2026-05):
  data[0][i] = [job_id, title, signin_url, [None, responsibilities_html],
               [None, qualifications_html], tenant_path, None, "Google", locale,
               [[location_label, [addr], city, None, region, country_code]],
               [None, summary_html], categories, ... ]
  data[2] = total result count, data[3] = page_size (20).

Usage: uv run ats/google_careers.py [location_query]
"""

import json
import re
import sys
import time

import httpx

try:
    from ats.utils import HEADERS, strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/google_careers.py <location>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html

BASE_URL = "https://www.google.com/about/careers/applications/jobs/results"
MAX_PAGES = 100  # safety cap; Google Israel currently shows ~70 roles across 4 pages
THROTTLE_SECONDS = 0.4  # be polite, Google may rate-limit aggressive crawlers


def _extract_ds1_data(html: str) -> list | None:
    """
    Extract the `data:[...]` array from the AF_initDataCallback({key: 'ds:1', ...}) block.
    Returns the parsed list, or None if the block is missing.

    Implementation note: we can't naively count parens — the embedded job descriptions
    contain literal `(` and `)` inside JS string literals. Instead we anchor on the
    `data:[` substring after the key marker, then walk square brackets while tracking
    JS string state (single quotes and double quotes, with backslash escapes).
    """
    # Locate the ds:1 callback - this is the search results dataset.
    # Other datasets exist (ds:0 = company list, etc.) so we anchor on the key.
    idx = html.find("AF_initDataCallback({key: 'ds:1'")
    if idx == -1:
        return None

    # Find the `data:` field inside this callback, then the `[` that opens its value.
    data_idx = html.find("data:", idx)
    if data_idx == -1:
        return None
    arr_start = html.find("[", data_idx)
    if arr_start == -1:
        return None

    # Walk brackets to find the matching close, ignoring brackets inside JS strings.
    depth = 0
    j = arr_start
    in_str: str | None = None  # active string delimiter (" or ') if inside a literal
    while j < len(html):
        c = html[j]
        if in_str is not None:
            # Skip escaped char inside string
            if c == "\\":
                j += 2
                continue
            if c == in_str:
                in_str = None
        else:
            if c == '"' or c == "'":
                in_str = c
            elif c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
        j += 1
    if depth != 0:
        return None
    arr_str = html[arr_start : j + 1]
    try:
        return json.loads(arr_str)
    except Exception:
        return None


def _format_location(loc_field) -> str:
    """
    Build a readable location string from the nested locations field.
    Shape: [[label, [addresses], city, ?, region, country_code], ...]
    """
    if not isinstance(loc_field, list) or not loc_field:
        return ""
    parts = []
    for entry in loc_field:
        if isinstance(entry, list) and entry:
            label = entry[0]
            if isinstance(label, str) and label:
                parts.append(label)
    return "; ".join(parts)


def _job_apply_url(job_id: str) -> str:
    """Public results page deep-link - resolves to the apply flow when clicked."""
    return f"https://www.google.com/about/careers/applications/jobs/results/{job_id}"


def fetch_positions(location_query: str = "Israel") -> list[dict]:
    """
    Fetch open Google positions for the given location string.
    Returns list of normalized dicts: {title, location, description, apply_url}.
    Returns whatever was accumulated so far on any error.
    """
    results: list[dict] = []
    seen_ids: set[str] = set()
    total_hits: int | None = None

    for page in range(1, MAX_PAGES + 1):
        params = {"location": location_query, "q": "", "page": page}
        try:
            resp = httpx.get(BASE_URL, params=params, headers=HEADERS, timeout=20, follow_redirects=True)
            resp.raise_for_status()
        except Exception as e:
            print(f"    google_careers fetch error on page {page}: {e}")
            break

        data = _extract_ds1_data(resp.text)
        if data is None:
            # ds:1 block missing - likely bot challenge / WAF page. Bail without crashing.
            print(f"    google_careers: ds:1 block missing on page {page} (possible bot challenge)")
            break

        # data layout: [jobs_or_None, _, total, page_size]
        jobs = data[0] if (len(data) > 0 and isinstance(data[0], list)) else []
        if total_hits is None and len(data) > 2 and isinstance(data[2], int):
            total_hits = data[2]
            print(f"    google_careers location={location_query!r}: {total_hits} total hits")

        if not jobs:
            # Empty page = we've paginated past the last result.
            break

        for job in jobs:
            if not isinstance(job, list) or len(job) < 10:
                continue
            job_id = job[0] if isinstance(job[0], str) else ""
            if not job_id or job_id in seen_ids:
                continue
            seen_ids.add(job_id)

            title = job[1] if isinstance(job[1], str) else ""
            # Combine all HTML description fragments into one strip-and-trim body.
            # Fields: [3]=responsibilities, [4]=qualifications, [10]=summary, [19]=min_quals
            html_chunks: list[str] = []
            for idx in (10, 3, 4, 19):
                if idx < len(job):
                    fld = job[idx]
                    if isinstance(fld, list) and len(fld) >= 2 and isinstance(fld[1], str):
                        html_chunks.append(fld[1])
            description = strip_html(" ".join(html_chunks))

            location = _format_location(job[9]) if len(job) > 9 else ""

            results.append(
                {
                    "title": title,
                    "location": location,
                    "description": description,
                    "apply_url": _job_apply_url(job_id),
                }
            )

        # Stop early if we've collected the announced total.
        if total_hits is not None and len(results) >= total_hits:
            break

        time.sleep(THROTTLE_SECONDS)

    return results


if __name__ == "__main__":
    loc = sys.argv[1] if len(sys.argv) > 1 else "Israel"
    print(f"Fetching Google Careers postings for location={loc!r}")
    positions = fetch_positions(loc)
    print(f"\n{len(positions)} positions:")
    for p in positions[:20]:
        print(f"  {p['title']} - {p['location']}")
        print(f"    {p['apply_url']}")
    if len(positions) > 20:
        print(f"  ... and {len(positions) - 20} more")
