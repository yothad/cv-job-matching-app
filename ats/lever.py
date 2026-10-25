import sys

import httpx

try:
    from ats.utils import HEADERS, sections_from_named, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: python ats/lever.py <slug>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, sections_from_named, strip_html as _strip_html


def fetch_positions(company_slug: str) -> list[dict]:
    """
    Fetch open positions from the Lever public postings API.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error.
    """
    url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    try:
        resp = httpx.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Lever API error for {company_slug}: {e}")
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    results = []
    for job in data:
        title = job.get("text", "")
        categories = job.get("categories") or {}
        location = categories.get("location", "")
        apply_url = job.get("hostedUrl", "")
        # Prefer plain-text description; fall back to HTML-stripped version
        raw_plain = job.get("descriptionPlain") or ""
        raw_html = job.get("description") or ""
        description = raw_plain if raw_plain else _strip_html(raw_html)
        # Lever keeps requirement / responsibility bullets in `lists` ({text: heading, content: html})
        lists = [(lst.get("text", ""), _strip_html(lst.get("content") or "")) for lst in job.get("lists") or []]
        sections = sections_from_named([("Description", description)] + lists) if lists else None

        results.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": apply_url,
                "sections": sections,
            }
        )

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run ats/lever.py <company_slug>")
        sys.exit(1)

    slug = sys.argv[1]
    print(f"Fetching Lever postings for: {slug}")
    jobs = fetch_positions(slug)
    print(f"Found {len(jobs)} job(s)")
    for job in jobs:
        print(f"  - {job['title']} | {job['location']} | {job['apply_url']}")
