import re

import httpx

from ats.utils import HEADERS, strip_html as _strip_html


def fetch_positions(subdomain: str, careers_url: str | None = None) -> list[dict]:
    """
    Fetch open positions from a Teamtailor career site's public RSS feed.
    Tries `<sub>.teamtailor.com/jobs.rss`, `career.<sub>.com/jobs.rss`,
    `careers.<sub>.com/jobs.rss`, and the careers_url's host + /jobs.rss.
    Returns [] on error.
    """
    candidates = [
        f"https://{subdomain}.teamtailor.com/jobs.rss",
        f"https://career.{subdomain}.com/jobs.rss",
        f"https://careers.{subdomain}.com/jobs.rss",
    ]
    if careers_url:
        from urllib.parse import urlparse
        host = urlparse(careers_url).netloc
        if host:
            candidates.insert(0, f"https://{host}/jobs.rss")
    text = None
    for url in candidates:
        try:
            r = httpx.get(url, timeout=15, headers=HEADERS, follow_redirects=True)
            if r.status_code == 200 and "<item>" in r.text:
                text = r.text
                break
        except Exception:
            continue
    if text is None:
        print(f"    Teamtailor: no RSS feed found for '{subdomain}'")
        return []

    return _parse_rss(text)


def _parse_rss(text: str) -> list[dict]:
    items = re.findall(r"<item>(.*?)</item>", text, re.DOTALL)
    out = []
    for item in items:
        title = _strip_cdata(_first(item, "title"))
        link = _strip_cdata(_first(item, "link"))
        desc_html = _strip_cdata(_first(item, "description"))
        description = _strip_html(_decode_entities(desc_html))
        location = _parse_location(item)
        out.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": link,
            }
        )
    return out


def _first(blob: str, tag: str) -> str:
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", blob, re.DOTALL)
    return m.group(1).strip() if m else ""


def _parse_location(item_blob: str) -> str:
    loc_block = _first(item_blob, "tt:location")
    if not loc_block:
        return ""
    parts = []
    for tag in ("tt:city", "tt:name", "tt:country"):
        v = _first(loc_block, tag)
        if v:
            parts.append(v)
    seen = set()
    uniq = []
    for p in parts:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    return ", ".join(uniq)


_CDATA_RE = re.compile(r"^<!\[CDATA\[(.*)\]\]>$", re.DOTALL)


def _strip_cdata(s: str) -> str:
    m = _CDATA_RE.match(s.strip())
    return m.group(1) if m else s


_ENTITY_MAP = {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&quot;": '"', "&#39;": "'"}


def _decode_entities(s: str) -> str:
    for k, v in _ENTITY_MAP.items():
        s = s.replace(k, v)
    return s
