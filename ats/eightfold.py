"""
Eightfold AI careers puller.

Eightfold AI (eightfold.ai) is an enterprise talent platform used by PayPal,
Cisco, Bayer, Hilton, etc. Two endpoint shapes are in the wild:

  (A) Standard:  GET /api/apply/v2/jobs?domain={tenant}.com&start=0&num=100&location=Israel
      Response: {"count": N, "positions": [{id, name, location, display_job_description, canonical_positionUrl, ...}]}

  (B) PCSX wrapper (PayPal etc): GET /api/pcsx/search?domain={tenant}.com&query=&location=Israel&start=0
      Response: {"data": {"count": N, "positions": [{id, name, locations[], positionUrl, ...}]}}
      Descriptions live behind a separate GET /api/pcsx/position_details?position_id=...&domain=...

When `/api/apply/v2/jobs` returns 403 with body containing "PCSX", we transparently
switch to the PCSX endpoint and (best-effort) enrich each position with its
description. Throttle 0.3s between any pagination/details hop.

Usage: uv run ats/eightfold.py <tenant> [location]
  e.g. uv run ats/eightfold.py paypal Israel
"""

import sys
import time

import httpx

try:
    from ats.utils import HEADERS, strip_html as _strip_html
except ModuleNotFoundError:
    # Allow running as a script from the repo root: uv run ats/eightfold.py <tenant>
    import os as _os

    sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
    from ats.utils import HEADERS, strip_html as _strip_html


PAGE_SIZE = 100
MAX_PAGES = 50
THROTTLE_SECONDS = 0.3


def fetch_positions(tenant: str, location_query: str = "Israel") -> list[dict]:
    """
    Fetch open positions from an Eightfold AI tenant.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns whatever was accumulated so far on error (never raises).
    """
    # Eightfold expects the company's primary domain in the `domain` param;
    # `{tenant}.com` is the convention that works for the major customers.
    domain = f"{tenant}.com"

    # Try the standard endpoint first; fall back to PCSX on 403 (PayPal pattern).
    standard = _fetch_standard(tenant, domain, location_query)
    if standard is not None:
        return standard
    return _fetch_pcsx(tenant, domain, location_query)


def _fetch_standard(tenant: str, domain: str, location_query: str) -> list[dict] | None:
    """
    Hit /api/apply/v2/jobs. Returns None if this endpoint is not authorized
    (signals caller to fall back to PCSX); otherwise returns the result list.
    """
    base_url = f"https://{tenant}.eightfold.ai/api/apply/v2/jobs"
    results: list[dict] = []
    start = 0

    for _ in range(MAX_PAGES):
        params = {
            "domain": domain,
            "start": start,
            "num": PAGE_SIZE,
            "location": location_query,
            "pid": "",
            "Codes": "",
            "query": "",
        }
        try:
            resp = httpx.get(base_url, params=params, timeout=20, headers=HEADERS)
        except Exception as e:
            print(f"    Eightfold API error for tenant '{tenant}' (start={start}): {e}")
            return results

        # 403 with PCSX hint -> caller falls back; only treat as fallback before any data fetched.
        if resp.status_code == 403 and "PCSX" in resp.text and start == 0:
            return None

        if resp.status_code >= 400:
            print(f"    Eightfold API HTTP {resp.status_code} for tenant '{tenant}' (start={start})")
            return results

        try:
            data = resp.json()
        except Exception:
            print(f"    Eightfold: JSON parse error for tenant '{tenant}' (start={start})")
            return results

        positions = data.get("positions")
        if not isinstance(positions, list) or not positions:
            break

        for pos in positions:
            results.append(_normalize_standard(pos, tenant))

        total = data.get("count", 0)
        start += len(positions)
        if total and start >= total:
            break

        time.sleep(THROTTLE_SECONDS)

    return results


def _normalize_standard(pos: dict, tenant: str) -> dict:
    title = pos.get("name") or ""
    location = pos.get("location") or ""
    description_html = pos.get("display_job_description") or pos.get("job_description") or ""
    description = _strip_html(description_html)

    apply_url = pos.get("canonical_positionUrl") or ""
    if not apply_url:
        pid = pos.get("id")
        if pid:
            apply_url = f"https://{tenant}.eightfold.ai/careers/job/{pid}"

    return {
        "title": title,
        "location": location,
        "description": description,
        "apply_url": apply_url,
    }


def _fetch_pcsx(tenant: str, domain: str, location_query: str) -> list[dict]:
    """
    Hit /api/pcsx/search. The PCSX response wraps the actual payload under `data`
    and uses camelCase keys. Descriptions require a per-position details call.
    """
    base_url = f"https://{tenant}.eightfold.ai/api/pcsx/search"
    details_url = f"https://{tenant}.eightfold.ai/api/pcsx/position_details"
    headers = {**HEADERS, "Referer": f"https://{tenant}.eightfold.ai/careers"}

    results: list[dict] = []
    start = 0

    for _ in range(MAX_PAGES):
        params = {
            "domain": domain,
            "query": "",
            "location": location_query,
            "start": start,
            "num": PAGE_SIZE,
        }
        try:
            resp = httpx.get(base_url, params=params, timeout=20, headers=headers)
            resp.raise_for_status()
        except Exception as e:
            print(f"    Eightfold PCSX API error for tenant '{tenant}' (start={start}): {e}")
            return results

        try:
            envelope = resp.json()
        except Exception:
            print(f"    Eightfold PCSX: JSON parse error for tenant '{tenant}' (start={start})")
            return results

        data = envelope.get("data") or {}
        positions = data.get("positions")
        if not isinstance(positions, list) or not positions:
            break

        for pos in positions:
            results.append(_normalize_pcsx(pos, tenant, details_url, domain, headers, location_query))

        total = data.get("count", 0)
        start += len(positions)
        if total and start >= total:
            break

        time.sleep(THROTTLE_SECONDS)

    return results


def _normalize_pcsx(
    pos: dict,
    tenant: str,
    details_url: str,
    domain: str,
    headers: dict,
    location_query: str,
) -> dict:
    title = pos.get("name") or ""

    # PCSX returns a list under `locations`; join for our normalized string field.
    locs = pos.get("locations") or []
    location = ", ".join(locs) if isinstance(locs, list) else (pos.get("location") or "")

    pid = pos.get("id")
    position_path = pos.get("positionUrl") or (f"/careers/job/{pid}" if pid else "")
    apply_url = f"https://{tenant}.eightfold.ai{position_path}" if position_path.startswith("/") else position_path

    # Description requires a separate hop; best-effort, swallow errors so one bad
    # position doesn't abort the whole pull.
    description = ""
    if pid:
        time.sleep(THROTTLE_SECONDS)
        try:
            d_resp = httpx.get(
                details_url,
                params={
                    "position_id": pid,
                    "domain": domain,
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
            description = _strip_html(description_html)
        except Exception as e:
            print(f"    Eightfold PCSX details error for position {pid}: {e}")

    return {
        "title": title,
        "location": location,
        "description": description,
        "apply_url": apply_url,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run ats/eightfold.py <tenant> [location]")
        print("  e.g. uv run ats/eightfold.py paypal Israel")
        sys.exit(1)

    tenant_arg = sys.argv[1]
    location_arg = sys.argv[2] if len(sys.argv) >= 3 else "Israel"
    print(f"Fetching Eightfold postings for tenant='{tenant_arg}' location='{location_arg}'")
    jobs = fetch_positions(tenant_arg, location_arg)
    print(f"Found {len(jobs)} job(s)")
    for i, job in enumerate(jobs[:5]):
        print(f"  [{i + 1}] {job['title']} - {job['location']}")
        print(f"       {job['apply_url']}")
    if len(jobs) > 5:
        print(f"  ... and {len(jobs) - 5} more")
