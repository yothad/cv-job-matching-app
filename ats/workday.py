import re

import httpx

from ats.utils import HEADERS, strip_html as _strip_html

_JSON_HEADERS = {**HEADERS, "Content-Type": "application/json"}
# Workday collapses a multi-location posting's list-view text to "N Locations",
# which hides the actual cities/countries from location_filter. Detect it so we
# can substitute the full location set from the per-job detail endpoint.
_COLLAPSED_LOC_RE = re.compile(r"^\s*\d+\s+locations?\s*$", re.IGNORECASE)


def fetch_positions(tenant: str, wd_instance: str, job_site: str) -> list[dict]:
    """
    Fetch open positions from a Workday public jobs board.

    Params come from ats_params in companies.json:
      tenant      - subdomain before .wd*.myworkdayjobs.com (e.g. "snyk")
      wd_instance - the wd* instance (e.g. "wd103")
      job_site    - the external site name in the URL path (e.g. "External")

    Returns list of {title, location, description, apply_url}.
    """
    base_url = f"https://{tenant}.{wd_instance}.myworkdayjobs.com"
    list_url = f"{base_url}/wday/cxs/{tenant}/{job_site}/jobs"

    # Step 1: paginate the job listing endpoint
    all_postings: list[dict] = []
    offset, limit = 0, 20
    while True:
        try:
            resp = httpx.post(
                list_url,
                json={"limit": limit, "offset": offset, "searchText": "", "locations": []},
                timeout=15,
                headers=_JSON_HEADERS,
            )
            resp.raise_for_status()
        except Exception as e:
            print(f"    Workday list error for {tenant}: {e}")
            break

        data = resp.json()
        postings = data.get("jobPostings") or []
        all_postings.extend(postings)
        if not postings or len(all_postings) >= data.get("total", 0):
            break
        offset += limit

    # Step 2: fetch description for each posting via the CXS detail endpoint
    results = []
    for posting in all_postings:
        title = posting.get("title", "")
        location = posting.get("locationsText", "")
        external_path = posting.get("externalPath", "")
        apply_url = f"{base_url}/{job_site}{external_path}" if external_path else ""

        description = ""
        if external_path:
            detail_url = f"{base_url}/wday/cxs/{tenant}/{job_site}{external_path}"
            try:
                dr = httpx.get(detail_url, timeout=10, headers=HEADERS)
                if dr.status_code == 200:
                    info = dr.json().get("jobPostingInfo", {})
                    description = _strip_html(info.get("jobDescription", ""))
                    # If the list view hid the real locations behind "N Locations"
                    # (or gave nothing), rebuild the string from the detail payload
                    # so a bundled Israel role isn't silently dropped by the filter.
                    if not location or _COLLAPSED_LOC_RE.match(location):
                        locs = [info.get("location", "")] + (info.get("additionalLocations") or [])
                        locs = [loc for loc in locs if loc]
                        if locs:
                            location = ", ".join(locs)
            except Exception:
                pass

        results.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": apply_url,
            }
        )

    return results
