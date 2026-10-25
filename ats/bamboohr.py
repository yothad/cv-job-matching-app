import sys

import httpx

try:
    from ats.utils import HEADERS, strip_html as _strip_html
except ModuleNotFoundError:
    import os as _os
    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html as _strip_html


def _fetch_detail(slug: str, job_id: str) -> dict:
    """Fetch full job detail (description + country) from /careers/{id}/detail."""
    url = f"https://{slug}.bamboohr.com/careers/{job_id}/detail"
    try:
        resp = httpx.get(url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
        return data.get("result", {}).get("jobOpening", {})
    except Exception:
        return {}


def fetch_positions(company_slug: str) -> list[dict]:
    """
    Fetch open positions from BambooHR public careers API.
    Returns list of normalized job dicts: {title, location, description, apply_url}.

    Uses /careers/list for the job index, then /careers/{id}/detail for
    full description and country — BambooHR's list endpoint omits both.
    """
    list_url = f"https://{company_slug}.bamboohr.com/careers/list"
    try:
        resp = httpx.get(list_url, headers=HEADERS, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    BambooHR API error for {company_slug}: {e}")
        return []

    jobs = data.get("result", [])
    results = []
    for job in jobs:
        job_id = str(job.get("id", ""))
        if not job_id:
            continue

        # Fetch detail for description + country
        detail = _fetch_detail(company_slug, job_id)

        title = detail.get("jobOpeningName") or job.get("jobOpeningName", "")

        loc = detail.get("location") or job.get("location") or {}
        city = loc.get("city") or ""
        country = loc.get("addressCountry") or ""
        # BambooHR often repeats city in the state field — skip state if duplicate
        state = loc.get("state") or ""
        if state.lower() == city.lower():
            state = ""
        location_parts = [p for p in [city, state, country] if p]
        location = ", ".join(location_parts)

        description_html = detail.get("description") or ""
        description = _strip_html(description_html)

        apply_url = f"https://{company_slug}.bamboohr.com/careers/{job_id}"

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
        print("Usage: uv run ats/bamboohr.py <company_slug>")
        sys.exit(1)

    slug = sys.argv[1]
    print(f"Fetching BambooHR postings for: {slug}")
    jobs = fetch_positions(slug)
    print(f"Found {len(jobs)} job(s)")
    for i, job in enumerate(jobs[:5]):
        print(f"  [{i + 1}] {job['title']} - {job['location']}")
        print(f"       {job['apply_url']}")
        if job["description"]:
            print(f"       desc: {job['description'][:80]}...")
    if len(jobs) > 5:
        print(f"  ... and {len(jobs) - 5} more")
