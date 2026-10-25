import html

import httpx

from ats.utils import HEADERS, strip_html as _strip_html


def fetch_positions(company_slug: str) -> list[dict]:
    """
    Fetch open positions from the Greenhouse public boards API.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error (caller logs).
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{company_slug}/jobs?content=true"
    try:
        resp = httpx.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Greenhouse API error for {company_slug}: {e}")
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
        location = (job.get("location") or {}).get("name", "")
        apply_url = job.get("absolute_url", "")
        raw_content = job.get("content") or ""
        description = _strip_html(html.unescape(raw_content))

        results.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": apply_url,
            }
        )

    return results
