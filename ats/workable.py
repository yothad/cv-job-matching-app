import sys

import httpx

try:
    from ats.utils import HEADERS, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/workable.py <slug>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html as _strip_html

_BASE = "https://apply.workable.com"
_LIST_PAYLOAD = {"query": "", "location": [], "department": [], "worktype": [], "remote": []}


def _list_jobs(company_slug: str) -> list[dict]:
    """
    Page through the v3 jobs listing and return all job stubs.
    Each stub has at least: shortcode, title, location (dict).
    """
    stubs = []
    token: str | None = None
    while True:
        payload = dict(_LIST_PAYLOAD)
        if token:
            payload["token"] = token
        try:
            resp = httpx.post(
                f"{_BASE}/api/v3/accounts/{company_slug}/jobs",
                json=payload,
                headers=HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"    Workable list error for {company_slug}: {e}")
            break

        try:
            data = resp.json()
        except Exception:
            break

        results = data.get("results") or []
        stubs.extend(results)

        token = data.get("nextPage")
        if not token:
            break

    return stubs


def _fetch_detail(company_slug: str, shortcode: str) -> dict:
    """
    Fetch a single job's detail from the v2 endpoint.
    Returns {} on error.
    """
    try:
        resp = httpx.get(
            f"{_BASE}/api/v2/accounts/{company_slug}/jobs/{shortcode}",
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {}


def fetch_positions(company_slug: str) -> list[dict]:
    """
    Fetch open positions from the Workable public API.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error (caller logs).
    """
    stubs = _list_jobs(company_slug)
    if not stubs:
        return []

    results = []
    for stub in stubs:
        shortcode = stub.get("shortcode", "")
        title = stub.get("title", "")
        loc_obj = stub.get("location") or {}
        location = loc_obj.get("display") or loc_obj.get("city") or ""

        apply_url = f"{_BASE}/{company_slug}/j/{shortcode}" if shortcode else ""

        # Fetch full description from detail endpoint
        detail = _fetch_detail(company_slug, shortcode) if shortcode else {}
        raw_desc = detail.get("description") or ""
        raw_req = detail.get("requirements") or ""
        raw_ben = detail.get("benefits") or ""
        combined = "\n\n".join(filter(None, [raw_desc, raw_req, raw_ben]))
        description = _strip_html(combined)

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
        print("Usage: uv run ats/workable.py <company_slug>")
        sys.exit(1)

    slug = sys.argv[1]
    print(f"Fetching Workable jobs for: {slug}")
    jobs = fetch_positions(slug)
    print(f"Found {len(jobs)} job(s)")
    for job in jobs:
        print(f"  - {job['title']} | {job['location']} | {job['apply_url']}")
