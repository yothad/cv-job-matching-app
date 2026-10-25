import sys

import httpx

try:
    from ats.utils import HEADERS, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/breezy.py <slug>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html as _strip_html


def fetch_positions(company_slug: str) -> list[dict]:
    """
    Fetch open positions from the Breezy HR public job board JSON endpoint.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error.
    """
    url = f"https://{company_slug}.breezy.hr/json"
    try:
        resp = httpx.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Breezy API error for {company_slug}: {e}")
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    if not isinstance(data, list):
        return []

    results = []
    for job in data:
        if job.get("state") != "published":
            continue

        title = job.get("name", "")
        loc = job.get("location") or {}
        location = ""
        if isinstance(loc, dict):
            location = loc.get("name") or (loc.get("country") or {}).get("name") or ""

        description = _strip_html(job.get("description") or "")
        path = job.get("url") or ""
        apply_url = f"https://{company_slug}.breezy.hr{path}" if path else ""

        results.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": apply_url,
            }
        )

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run ats/breezy.py <company_slug>")
        sys.exit(1)

    slug = sys.argv[1]
    print(f"Fetching Breezy postings for: {slug}")
    jobs = fetch_positions(slug)
    print(f"Found {len(jobs)} job(s)")
    for i, job in enumerate(jobs[:5]):
        print(f"  [{i + 1}] {job['title']} - {job['location']}")
        print(f"       {job['apply_url']}")
    if len(jobs) > 5:
        print(f"  ... and {len(jobs) - 5} more")
