"""
Lemonade careers puller.

Lemonade self-hosts its careers site as a Next.js app at makers.lemonade.com -
there is no third-party ATS. Every open role is embedded in the homepage's
__NEXT_DATA__ JSON, so we parse that directly (one request, no DOM scraping).
Lemonade also lists US/EU roles, so set location_filter=israel on the company
entry to keep only the relevant ones.
"""
import json
import re

import httpx

from ats.utils import HEADERS, strip_html

_HOME = "https://makers.lemonade.com/"
_NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _walk(obj):
    """Yield job dicts (title + location + slug) from nested __NEXT_DATA__."""
    if isinstance(obj, dict):
        keys = obj.keys()
        if {"title", "location", "slug"} <= keys and (
            "postingId" in keys or "employmentType" in keys
        ):
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def fetch_positions() -> list[dict]:
    r = httpx.get(_HOME, headers=HEADERS, follow_redirects=True, timeout=20)
    r.raise_for_status()
    m = _NEXT_DATA.search(r.text)
    if not m:
        return []
    data = json.loads(m.group(1))

    seen, results = set(), []
    for j in _walk(data):
        jid = j.get("id") or j.get("slug")
        if jid in seen:
            continue
        seen.add(jid)
        link = j.get("link") or f"/recipe/{j.get('slug', '')}"
        if not link.startswith("http"):
            link = _HOME.rstrip("/") + "/" + link.lstrip("/")
        results.append({
            "title": (j.get("title") or "").strip(),
            "location": (j.get("location") or "").strip(),
            "description": strip_html(j.get("content") or j.get("socialDescription") or ""),
            "apply_url": link,
        })
    return results


if __name__ == "__main__":
    pos = fetch_positions()
    print(f"{len(pos)} positions")
    for p in pos:
        print(f"  {p['title']}  |  {p['location']}")
