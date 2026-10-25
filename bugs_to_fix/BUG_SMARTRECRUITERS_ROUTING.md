# BUG: SmartRecruiters puller returns 0 jobs — site routing changed

## Status
✅ Wrapped

## Severity
P2

## Description
`ats/smartrecruiters.py` scrapes server-side-rendered HTML from `careers.smartrecruiters.com/{company_slug}`, parsing job listings out of the markup with regex (`_JOB_ANCHOR_RE`, `_LOCATION_RE`). SmartRecruiters has since changed their routing: requests to company-specific career pages now 302-redirect to a generic `jobs.smartrecruiters.com` search page instead of returning the company-specific SSR HTML the parser expects.

Confirmed live during a QA pass on 2026-07-04: both tracked SmartRecruiters companies (Palo Alto Networks, CyberArk) return `Found 0 job(s)`.

```
$ uv run ats/smartrecruiters.py PaloAltoNetworks2
Found 0 job(s)

$ uv run ats/smartrecruiters.py Cyberark1
Found 0 job(s)
```

Confirmed via a direct request with `follow_redirects=False`:
```
GET https://careers.smartrecruiters.com/PaloAltoNetworks2
-> 302, final destination: https://jobs.smartrecruiters.com
```

Likely root cause: SmartRecruiters appears to have migrated away from per-company SSR pages under `careers.smartrecruiters.com/{slug}` toward a centralized job-search experience at `jobs.smartrecruiters.com`, which is likely client-rendered rather than server-rendered — meaning the current regex-based HTML scraping approach may not work at all even with a URL fix. The puller's own docstring already notes the official public API (`api.smartrecruiters.com/v1/companies/{slug}/postings`) was "effectively gated for anonymous access" at build time; that should be re-checked too, since SmartRecruiters' access policy may have changed in either direction since then.

## Steps to Reproduce
1. `uv run ats/smartrecruiters.py PaloAltoNetworks2`
2. `uv run ats/smartrecruiters.py Cyberark1`
3. Expected: ≥5 jobs each (per the original `ATS_SMARTRECRUITERS` spec's QA criteria). Actual: `Found 0 job(s)` for both.

## Dependencies
- **Depends on:** —
- **Blocks:** —
- **Touches:** `ats/smartrecruiters.py`
- **Spec files to update:** — (`future_devs/archive/ATS_SMARTRECRUITERS_SPEC.md` is already wrapped and stays as the historical record; this bug tracks the live regression)

## Fix Notes
Rewrote `ats/smartrecruiters.py` from regex-based HTML scraping to the public JSON API (`api.smartrecruiters.com/v1/companies/{slug}/postings`). The API is **not** gated for anonymous access as the old docstring claimed — verified against `Sutherland` (357 real postings) and `Visa` (2 real postings). `apply_url` is built as `jobs.smartrecruiters.com/{slug}/{posting_id}` — confirmed this bare-ID form resolves as a working link with no per-job detail fetch needed, so the puller stays a single paginated list call, same request profile as before.

Important finding while investigating: `big_companies.yml` already has notes from 2026-06-17 on both the CyberArk and Palo Alto Networks entries stating their SmartRecruiters boards return 0 jobs and hiring likely moved to PAN's Workday post-acquisition. This is **not a new regression** — the "0 jobs" outcome for these two specific companies was already known and documented; only the puller's *mechanism* (HTML scraping against a page that's now a client-rendered SPA) was actually broken, and that's what's fixed here. Re-verified against the new API: both `PaloAltoNetworks2` and `Cyberark1` genuinely return `totalFound: 0`, confirming the boards are abandoned, not that the puller is broken.

**Follow-up for Yotam (not done here — out of scope for an automated fix per CLAUDE.md, which reserves `big_companies.yml` discovery/verification for manual review):** if you want CyberArk/PAN Israel roles surfaced, their actual current careers URL/ATS needs to be manually re-verified — the existing notes already suspect Workday. That would be a manual `big_companies.yml` edit, not a puller fix.
