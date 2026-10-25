"""
Amazon Jobs puller.

Hits the public amazon.jobs search.json endpoint filtered by country code.
Covers all Amazon-family openings (AWS, Lab126, retail, Audible, etc.).

Usage: uv run ats/amazon_jobs.py [country_code]
  e.g. uv run ats/amazon_jobs.py ISR
"""

import sys
import time

import httpx

try:
    from ats.utils import HEADERS, sections_from_named, strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/amazon_jobs.py <country_code>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, sections_from_named, strip_html

BASE_URL = "https://www.amazon.jobs/en/search.json"
PAGE_SIZE = 100
MAX_PAGES = 50  # safety net: 5000 jobs max


def fetch_positions(country_code: str = "ISR") -> list[dict]:
    """
    Fetch open positions from amazon.jobs for a given country code.
    Returns list of normalized dicts: {title, location, description, apply_url}.
    Returns [] on error.
    """
    results: list[dict] = []
    offset = 0
    total_hits: int | None = None

    for page in range(MAX_PAGES):
        params = {
            "normalized_country_code[]": country_code,
            "result_limit": PAGE_SIZE,
            "offset": offset,
            "sort": "recent",
        }
        try:
            resp = httpx.get(BASE_URL, params=params, headers=HEADERS, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"    amazon_jobs fetch error at offset={offset}: {e}")
            break

        jobs = data.get("jobs") or []
        if total_hits is None:
            total_hits = data.get("hits", 0)
            print(f"    amazon_jobs {country_code}: {total_hits} total hits")

        if not jobs:
            break

        for job in jobs:
            title = job.get("title", "") or ""
            location = job.get("normalized_location", "") or ""
            desc_raw = job.get("description") or job.get("description_short") or ""
            description = strip_html(desc_raw)
            job_path = job.get("job_path", "") or ""
            apply_url = f"https://www.amazon.jobs{job_path}" if job_path else ""
            # Qualifications are separate fields, not part of `description`
            sections = sections_from_named([
                ("Description", description),
                ("Basic qualifications", strip_html(job.get("basic_qualifications") or "")),
                ("Preferred qualifications", strip_html(job.get("preferred_qualifications") or "")),
            ])

            results.append(
                {
                    "title": title,
                    "location": location,
                    "description": description,
                    "apply_url": apply_url,
                    "sections": sections,
                }
            )

        offset += PAGE_SIZE
        if total_hits is not None and len(results) >= total_hits:
            break

        time.sleep(0.3)

    return results


if __name__ == "__main__":
    country = sys.argv[1] if len(sys.argv) > 1 else "ISR"
    positions = fetch_positions(country)
    print(f"\n{len(positions)} positions for country={country}:")
    for p in positions[:20]:
        print(f"  {p['title']} - {p['location']}")
        print(f"    {p['apply_url']}")
    if len(positions) > 20:
        print(f"  ... and {len(positions) - 20} more")
