"""
Microsoft Careers puller.

Microsoft moved its public careers site from jobs.careers.microsoft.com
(backed by gcsservices.careers.microsoft.com) to apply.careers.microsoft.com,
which is an Eightfold AI "PCSX" instance. Domain identifier is microsoft.com.

  GET https://apply.careers.microsoft.com/api/pcsx/search
      ?domain=microsoft.com&query=&location=Israel&start=0&num=20

  Response: {"data": {"positions": [{id, name, locations[], positionUrl, ...}], "count": N}}

Note: the previous gcsservices.careers.microsoft.com search/api/v1/search endpoint
now serves an invalid TLS certificate (CN=*.azureedge.net) and routes to an Azure
404 page - the SPA has been migrated. PCSX is the live backing API as of 2026-05.

Usage: uv run ats/microsoft_careers.py [location]
  e.g. uv run ats/microsoft_careers.py Israel
"""

import sys
import time

import httpx

try:
    from ats.utils import HEADERS, strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/microsoft_careers.py <location>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html

BASE_HOST = "https://apply.careers.microsoft.com"
SEARCH_URL = f"{BASE_HOST}/api/pcsx/search"
DETAILS_URL = f"{BASE_HOST}/api/pcsx/position_details"
DOMAIN = "microsoft.com"
# pgSz=20 mirrors the public SPA; larger pages occasionally 500 on the PCSX backend.
PAGE_SIZE = 20
MAX_PAGES = 100  # safety net: 2000 jobs max
THROTTLE_SECONDS = 0.4


def fetch_positions(location_query: str = "Israel") -> list[dict]:
    """
    Fetch open positions from Microsoft's careers API for a given location.
    Returns list of normalized dicts: {title, location, description, apply_url}.
    Returns whatever was accumulated on per-page error (no crash on 429).
    """
    # PCSX is referer-checked - without this, the API responds with the SPA shell HTML.
    headers = {
        **HEADERS,
        "Accept": "application/json",
        "Referer": f"{BASE_HOST}/careers",
    }
    results: list[dict] = []
    total_jobs: int | None = None

    for page in range(1, MAX_PAGES + 1):
        start = (page - 1) * PAGE_SIZE
        params = {
            "domain": DOMAIN,
            "query": "",
            "location": location_query,
            "start": start,
            "num": PAGE_SIZE,
            "sort_by": "relevance",
        }
        try:
            resp = httpx.get(SEARCH_URL, params=params, headers=headers, timeout=20)
            resp.raise_for_status()
            envelope = resp.json()
        except Exception as e:
            # 429 / transient 5xx: keep what we have rather than failing the whole pull.
            print(f"    microsoft_careers fetch error at pg={page}: {e}")
            break

        # Response shape: {"status": 200, "data": {"positions": [...], "count": N}}
        data = envelope.get("data") or {}
        positions = data.get("positions") or []

        if total_jobs is None:
            total_jobs = data.get("count", 0)
            print(f"    microsoft_careers {location_query}: {total_jobs} total jobs")

        if not positions:
            break

        for pos in positions:
            results.append(_normalize(pos, headers, location_query))

        if total_jobs is not None and len(results) >= total_jobs:
            break

        time.sleep(THROTTLE_SECONDS)

    return results


def _normalize(pos: dict, headers: dict, location_query: str) -> dict:
    job_id = pos.get("id")
    title = pos.get("name", "") or ""

    locs = pos.get("locations") or []
    location = ", ".join(loc for loc in locs if loc) if isinstance(locs, list) else ""

    position_path = pos.get("positionUrl") or (f"/careers/job/{job_id}" if job_id else "")
    apply_url = f"{BASE_HOST}{position_path}" if position_path.startswith("/") else position_path

    # Search results don't include descriptions - fetch per-position via details endpoint.
    # Best-effort: swallow errors (Microsoft rate-limits 429 aggressively on this endpoint)
    # so one bad fetch doesn't abort the whole pull.
    description = ""
    if job_id:
        time.sleep(THROTTLE_SECONDS * 2)
        try:
            d_resp = httpx.get(
                DETAILS_URL,
                params={
                    "position_id": job_id,
                    "domain": DOMAIN,
                    "hl": "en",
                    "queried_location": location_query,
                },
                headers=headers,
                timeout=20,
            )
            d_resp.raise_for_status()
            d_envelope = d_resp.json()
            d_data = d_envelope.get("data") or {}
            description_html = d_data.get("jobDescription") or d_data.get("job_description") or ""
            description = strip_html(description_html)
        except Exception as e:
            print(f"    microsoft_careers details error for position {job_id}: {e}")

    return {
        "title": title,
        "location": location,
        "description": description,
        "apply_url": apply_url,
    }


if __name__ == "__main__":
    location = sys.argv[1] if len(sys.argv) > 1 else "Israel"
    positions = fetch_positions(location)
    print(f"\n{len(positions)} positions for location={location}:")
    for p in positions[:20]:
        print(f"  {p['title']} - {p['location']}")
        print(f"    {p['apply_url']}")
    if len(positions) > 20:
        print(f"  ... and {len(positions) - 20} more")
