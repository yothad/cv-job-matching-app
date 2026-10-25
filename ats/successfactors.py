"""
SAP SuccessFactors public-careers puller.

SuccessFactors is a multi-tenant enterprise platform whose tenants expose three
quite different public surfaces. This puller targets the most common branded
"jobs2web" front-end (e.g. https://jobs.sap.com/search/) because it serves
plain HTML with server-side location filtering — the cleanest of the three.

Reconnaissance notes (run on 2026-05-17):

- SAP's branded host (https://jobs.sap.com/search/?locationsearch=israel) returns
  6 Israel-based postings as static HTML in <tr class="data-row"> rows. Job
  detail pages embed the description inside <span class="jobdescription">. This
  surface is fully scrapable with httpx, no JS rendering required.

- CyberArk was acquired by Palo Alto Networks. https://www.cyberark.com/careers/
  now embeds Palo Alto's Workday board (paloaltonetworks.wd5.myworkdayjobs.com),
  and the residual https://www.cyberark.com/careers/all-job-openings/job-post/
  template links out to https://jobs.smartrecruiters.com/Cyberark1— CyberArk
  is on SmartRecruiters, not SuccessFactors anymore. So no SuccessFactors
  fetcher will ever return CyberArk jobs; that's a SmartRecruiters puller.

- The other two SuccessFactors surfaces (the JS SPA at career.successfactors.eu
  and the OData /odata/v2/JobRequisition feed) are not used here. The SPA needs
  Playwright; the OData feed needs tenant API credentials. Both are blocked for
  the SAP tenant. Add support only when a real big_companies.yml entry needs it.
"""

import html
import re
import sys
from urllib.parse import urljoin

import httpx

try:
    from ats.utils import HEADERS, qualify_location, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/successfactors.py <tenant>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, qualify_location, strip_html as _strip_html


# Each posting on a jobs2web /search/ page is wrapped in <tr class="data-row">.
_ROW_RE = re.compile(r'<tr[^>]*class="data-row"[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
# The desktop-visible title anchor lives in colTitle; the visible-phone duplicate
# uses the same href, so capturing the first match per row is enough. jobs2web
# renders class= and href= in either order across templates, so we do a two-pass
# extract instead of one big regex with backreferences.
_TITLE_ANCHOR_RE = re.compile(
    r'<a\b[^>]*class="jobTitle-link"[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
_HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)
# Each row contains a <span class="jobLocation"> block whose text is e.g.
# "Ra'anana, IL, 4366202". The hidden-phone (desktop) version is preferred; the
# visible-phone variant duplicates it. We just take the first non-empty match.
_LOCATION_RE = re.compile(
    r'<span[^>]*class="jobLocation"[^>]*>(.*?)</span>',
    re.DOTALL | re.IGNORECASE,
)
# Job-detail page wraps the description in <span class="jobdescription">.
_DESC_RE = re.compile(r'<span\s+class="jobdescription">(.*?)</span>\s*</span>', re.DOTALL | re.IGNORECASE)
# Total-result count appears as 'Results 1 to N of TOTAL' — used to drive pagination.
_TOTAL_RE = re.compile(r'Results\s+\d+\s+to\s+\d+\s+of\s+(\d+)', re.IGNORECASE)

# jobs2web pages return ~25 results per request; bumping past that risks
# silently truncating to 25, so we just page through.
_PAGE_SIZE = 25
# Hard cap on pages to avoid runaway loops if a tenant returns malformed totals.
_MAX_PAGES = 20


def _clean(text: str) -> str:
    # Decode HTML entities (e.g. &amp;, &apos;, &#39;) since jobs2web renders
    # apostrophes and ampersands as escaped HTML even inside link text.
    return re.sub(r"\s+", " ", _decode_entities(_strip_html(text))).strip()


def _decode_entities(text: str) -> str:
    # jobs2web renders apostrophes as double-encoded &amp;apos; — one pass of
    # html.unescape handles named and numeric refs; a second pass catches the
    # double-encoded apostrophe cases that show up in href attributes.
    return html.unescape(html.unescape(text))


def _resolve_base(tenant: str, branded_host: str | None) -> str:
    """
    Return the absolute base URL we should hit for search + job-detail pages.

    A branded host (jobs.sap.com, careers.foo.com) is the preferred surface
    because it serves plain HTML. Without one, we fall back to the multi-tenant
    legacy hostname; that surface tends to be JS-rendered and may return very
    little useful HTML from a single httpx call.
    """
    if branded_host:
        host = branded_host.strip().rstrip("/")
        if not host.startswith("http"):
            host = f"https://{host}"
        return host
    return f"https://career.successfactors.eu/career?career_company={tenant}"


def _fetch_job_description(detail_url: str) -> str:
    try:
        resp = httpx.get(detail_url, follow_redirects=True, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except Exception:
        return ""
    m = _DESC_RE.search(resp.text)
    if not m:
        return ""
    return _clean(m.group(1))


def fetch_positions(
    tenant: str,
    branded_host: str | None = None,
    location_query: str | None = None,
) -> list[dict]:
    """
    Fetch open positions from a SuccessFactors-backed careers site.

    Args:
        tenant: SF tenant slug (e.g. "sap"). Used only when branded_host is None,
            to build the legacy career.successfactors.eu URL.
        branded_host: Preferred — the public host that serves the /search/ HTML
            (e.g. "jobs.sap.com"). When set we hit /search/?startrow=N directly.
        location_query: Optional server-side filter pushed into the search URL
            (jobs2web's ?locationsearch= param). For tenants with thousands of
            global postings this avoids hydrating every job-detail page just to
            throw most of them away in the location_filter step.

    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error. Always returns; never raises.
    """
    base = _resolve_base(tenant, branded_host)
    # The branded host only serves clean HTML at /search/ — the root redirects
    # to a landing page that doesn't list jobs.
    is_branded = bool(branded_host)
    search_root = f"{base}/search/" if is_branded else base
    if location_query and is_branded:
        sep = "&" if "?" in search_root else "?"
        search_root = f"{search_root}{sep}locationsearch={location_query}"

    results: list[dict] = []
    seen_urls: set[str] = set()
    total: int | None = None
    startrow = 0

    for _page in range(_MAX_PAGES):
        sep = "&" if "?" in search_root else "?"
        url = f"{search_root}{sep}startrow={startrow}"
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=20, headers=HEADERS)
            resp.raise_for_status()
        except Exception as e:
            print(f"    SuccessFactors error for {tenant} (startrow={startrow}): {e}")
            break

        html = resp.text

        # Capture total once so we can stop paginating at the right boundary
        # even when a tenant doesn't render row counts on later pages.
        if total is None:
            m = _TOTAL_RE.search(html)
            if m:
                total = int(m.group(1))

        rows = _ROW_RE.findall(html)
        if not rows:
            break

        page_added = 0
        for row in rows:
            anchor_m = _TITLE_ANCHOR_RE.search(row)
            if not anchor_m:
                continue
            href_m = _HREF_RE.search(anchor_m.group(0))
            if not href_m:
                continue
            href = _decode_entities(href_m.group(1))
            title = _clean(anchor_m.group(1))
            if not title or not href:
                continue

            apply_url = urljoin(base if is_branded else search_root, href)
            if apply_url in seen_urls:
                continue
            seen_urls.add(apply_url)

            location = ""
            loc_m = _LOCATION_RE.search(row)
            if loc_m:
                # jobs2web emits a bare ISO code ("Ra'anana, IL, ...") — expand it
                # so location_filter can match on the country name.
                location = qualify_location(_clean(loc_m.group(1)))

            results.append(
                {
                    "title": title,
                    "location": location,
                    # Description is fetched lazily per-job below — left empty
                    # here so a search-only run still completes quickly.
                    "description": "",
                    "apply_url": apply_url,
                }
            )
            page_added += 1

        if page_added == 0:
            break
        startrow += _PAGE_SIZE
        if total is not None and startrow >= total:
            break

    # Hydrate descriptions in a second pass. Done sequentially with a short
    # timeout — the caller (collect_jobs.py) already runs pullers in a
    # ThreadPool, so we don't fan out further here.
    for job in results:
        job["description"] = _fetch_job_description(job["apply_url"])

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run ats/successfactors.py <tenant> [branded_host] [location_query]")
        print("  e.g. uv run ats/successfactors.py sap jobs.sap.com israel")
        sys.exit(1)

    tenant = sys.argv[1]
    branded = sys.argv[2] if len(sys.argv) > 2 else None
    loc_query = sys.argv[3] if len(sys.argv) > 3 else None

    # Built-in convenience: when the user just says "sap", default to the
    # known branded host so the CLI does the obvious thing. Defaulting to
    # an Israel location query here too keeps the manual smoke test honest
    # with how big_companies.yml actually invokes the puller.
    if tenant.lower() == "sap" and branded is None:
        branded = "jobs.sap.com"
    if tenant.lower() == "sap" and loc_query is None:
        loc_query = "israel"

    print(f"Fetching SuccessFactors postings for tenant={tenant} branded_host={branded} location_query={loc_query}")
    jobs = fetch_positions(tenant, branded, loc_query)
    print(f"Found {len(jobs)} job(s)")
    for i, job in enumerate(jobs[:10]):
        print(f"  [{i + 1}] {job['title']} - {job['location']}")
        print(f"       {job['apply_url']}")
    if len(jobs) > 10:
        print(f"  ... and {len(jobs) - 10} more")
