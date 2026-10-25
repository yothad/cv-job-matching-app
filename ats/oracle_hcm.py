"""
Oracle Fusion HCM (Cloud Recruiting) puller.

The Candidate Experience REST API is public — no authentication required.
Response structure:
  d['items'][0] = search container with TotalJobsCount + requisitionList
  d['items'][0]['requisitionList'] = paged job list (default 25 per page)

Pagination: offset query param; continue while offset < TotalJobsCount.
Location filter: client-side on PrimaryLocationCountry == 'IL'.
Apply URL: https://{host}/hcmUI/CandidateExperience/en/sites/{site}/requisitions/{Id}
"""
import sys

import httpx

try:
    from ats.utils import HEADERS, strip_html as _strip_html
except ModuleNotFoundError:
    import os as _os
    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html as _strip_html

_PAGE_SIZE = 25
_MAX_PAGES = 20  # cap at 500 jobs to avoid hammering the API


def fetch_positions(host: str, site: str, location_query: str = "Israel") -> list[dict]:
    """
    Fetch open positions from an Oracle Fusion HCM Candidate Experience board.

    host: HCM REST API hostname, e.g. fa-extu-saasfaprod1.fa.ocs.oraclecloud.com
    site: site number from the careers URL, e.g. CX_1 or careers
    location_query: client-side country filter string (matched against PrimaryLocation
                    and PrimaryLocationCountry); pass "" to return all.
    """
    ui_base = f"https://{host}/hcmUI/CandidateExperience"
    api_base = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"

    results = []
    offset = 0
    total = None

    while True:
        url = (
            f"{api_base}?expand=all"
            f"&finder=findReqs;siteNumber={site},facet="
            f"&limit={_PAGE_SIZE}&offset={offset}"
        )
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"    Oracle HCM API error for {host} ({site}) at offset={offset}: {e}")
            break

        container = data.get("items", [{}])[0]
        if total is None:
            total = container.get("TotalJobsCount", 0)
            if total == 0:
                break

        jobs = container.get("requisitionList", [])
        if not jobs:
            break

        for job in jobs:
            country = job.get("PrimaryLocationCountry") or ""
            location = job.get("PrimaryLocation") or ""

            # Client-side location filter: match against location string or country name
            if location_query:
                combined = f"{location} {country}".lower()
                if location_query.lower() not in combined:
                    # Also check Israel via ISO code IL
                    if not (location_query.lower() == "israel" and country == "IL"):
                        continue

            title = job.get("Title") or ""
            job_id = job.get("Id") or ""
            apply_url = f"{ui_base}/en/sites/{site}/requisitions/{job_id}" if job_id else ""

            # Description: prefer ShortDescriptionStr (synopsis), fall back to qualifications
            description_html = (
                job.get("ShortDescriptionStr")
                or job.get("ExternalQualificationsStr")
                or job.get("ExternalResponsibilitiesStr")
                or ""
            )
            description = _strip_html(description_html)

            results.append(
                {
                    "title": title,
                    "location": f"{location}, {country}" if location and country else location or country,
                    "description": description,
                    "apply_url": apply_url,
                }
            )

        offset += len(jobs)
        if offset >= total or offset >= _PAGE_SIZE * _MAX_PAGES:
            break

    return results


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run ats/oracle_hcm.py <host> <site> [location_query]")
        print("  e.g. uv run ats/oracle_hcm.py fa-extu-saasfaprod1.fa.ocs.oraclecloud.com CX_1 Israel")
        sys.exit(1)

    host = sys.argv[1]
    site = sys.argv[2]
    loc = sys.argv[3] if len(sys.argv) > 3 else "Israel"
    print(f"Fetching Oracle HCM postings for: {host} site={site} filter={loc!r}")
    jobs = fetch_positions(host, site, loc)
    print(f"Found {len(jobs)} job(s) matching filter")
    for i, job in enumerate(jobs[:5]):
        print(f"  [{i + 1}] {job['title']} - {job['location']}")
        print(f"       {job['apply_url']}")
        if job["description"]:
            print(f"       desc: {job['description'][:80]}...")
    if len(jobs) > 5:
        print(f"  ... and {len(jobs) - 5} more")
