import httpx

from ats.utils import HEADERS, sections_from_named, strip_html as _strip_html


def fetch_positions(company_uid: str, token: str) -> list[dict]:
    """
    Fetch open positions from the Comeet public API.
    Returns list of normalized job dicts: {title, location, description, apply_url}.
    Returns [] on error (caller logs).
    """
    url = (
        f"https://www.comeet.co/careers-api/2.0/company/{company_uid}/positions"
        f"?token={token}&details=true"
    )
    try:
        resp = httpx.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Comeet API error for {company_uid}: {e}")
        return []

    try:
        positions = resp.json()
    except Exception:
        return []

    if not isinstance(positions, list):
        return []

    results = []
    for pos in positions:
        if pos.get("is_internal"):
            continue

        title = pos.get("name", "")
        location = _parse_location(pos.get("location"))
        apply_url = pos.get("url_comeet_hosted_page") or pos.get("url_active_page") or ""

        # details is a list of {name, value} dicts; Description is the main one
        description = ""
        for detail in pos.get("details") or []:
            if detail.get("name", "").lower() == "description":
                description = _strip_html(detail.get("value") or "")
                break
        if not description:
            # Fall back: concat all details
            parts = [_strip_html(d.get("value") or "") for d in (pos.get("details") or [])]
            description = " ".join(p for p in parts if p)
        # The other details (Requirements, Responsibility, Who You Are, ...) are named
        # sections; keep them for the role fields even though `description` stays Description-only.
        sections = sections_from_named(
            [(d.get("name", ""), _strip_html(d.get("value") or "")) for d in pos.get("details") or []]
        )

        results.append(
            {
                "title": title,
                "location": location,
                "description": description,
                "apply_url": apply_url,
                "sections": sections,
            }
        )

    return results


# Comeet returns the country as an ISO-3166 alpha-2 code (e.g. "IL").
# location_filter does a plain substring match, so a job whose name is just
# "Tel Aviv" would be dropped by a "israel" filter even though country == "IL".
# Expand the code so the country name is present in the location string.
_ISO_COUNTRY = {
    "IL": "Israel",
    "US": "United States",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "IN": "India",
    "PL": "Poland",
    "NL": "Netherlands",
    "CA": "Canada",
    "AU": "Australia",
    "SG": "Singapore",
    "ES": "Spain",
    "IE": "Ireland",
}


def _parse_location(loc: dict | None) -> str:
    if not loc:
        return ""
    name = loc.get("name") or loc.get("city") or loc.get("state") or ""
    country = loc.get("country") or ""
    country = _ISO_COUNTRY.get(country, country)
    # Append the country only when it isn't already reflected in the name.
    if country and country.lower() not in name.lower():
        return f"{name}, {country}" if name else country
    return name
