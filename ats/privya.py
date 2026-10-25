"""
Privya careers puller.

Privya self-hosts careers as a WordPress 'jobs' custom post type (no third-party
ATS). The WP REST API exposes them cleanly, so we pull from there. Location is
not modeled in the CMS; Privya is Tel Aviv based, so we default to Israel and let
the company entry's location_filter do the rest.
"""
import httpx

from ats.utils import HEADERS, strip_html

_API = "https://privya.ai/wp-json/wp/v2/jobs"


def fetch_positions() -> list[dict]:
    r = httpx.get(_API, headers=HEADERS,
                  params={"per_page": 100, "_fields": "link,title,content"}, timeout=20)
    r.raise_for_status()
    results = []
    for j in r.json():
        title = strip_html((j.get("title") or {}).get("rendered", "")).strip()
        if not title:
            continue
        results.append({
            "title": title,
            "location": "Israel",
            "description": strip_html((j.get("content") or {}).get("rendered", "")),
            "apply_url": j.get("link", ""),
        })
    return results


if __name__ == "__main__":
    pos = fetch_positions()
    print(f"{len(pos)} positions")
    for p in pos:
        print(f"  {p['title']}  |  {p['location']}")
