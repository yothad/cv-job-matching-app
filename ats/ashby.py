import sys

import httpx

try:
    from ats.utils import HEADERS, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/ashby.py <org_name>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html as _strip_html


def fetch_positions(org_name: str) -> list[dict]:
    """
    Fetch open positions from the Ashby public job board API.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error (caller logs).
    """
    url = f"https://api.ashbyhq.com/posting-api/job-board/{org_name}"
    try:
        resp = httpx.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Ashby API error for {org_name}: {e}")
        return []

    try:
        data = resp.json()
    except Exception:
        return []

    jobs = data.get("jobs") if isinstance(data, dict) else None
    if not isinstance(jobs, list):
        return []

    results = []
    for job in jobs:
        title = job.get("title", "")
        location = job.get("location", "")
        # location is often just a city ("Tel Aviv"); the country lives in the
        # structured address. Append it so location_filter (a substring match)
        # can match on country, not only city name.
        country = ((job.get("address") or {}).get("postalAddress") or {}).get("addressCountry", "")
        if country and country.lower() not in location.lower():
            location = f"{location}, {country}" if location else country
        apply_url = job.get("applyUrl") or job.get("jobUrl", "")
        raw_content = job.get("descriptionHtml") or job.get("descriptionPlain") or ""
        description = _strip_html(raw_content)

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
        print("Usage: uv run ats/ashby.py <org_name>")
        sys.exit(1)

    org = sys.argv[1]
    print(f"Fetching jobs for Ashby org: {org}")
    positions = fetch_positions(org)
    print(f"Found {len(positions)} job(s)")
    for i, pos in enumerate(positions[:5]):
        print(f"  [{i + 1}] {pos['title']} - {pos['location']}")
        print(f"       {pos['apply_url']}")
    if len(positions) > 5:
        print(f"  ... and {len(positions) - 5} more")
