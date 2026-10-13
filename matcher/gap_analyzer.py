import json
import re
import time

from matcher.gemini_scorer import _is_retryable, generate


def _call_gemini(client, prompt: str) -> dict:
    backoff = [4, 8, 16, 32]
    last_exc = None
    for attempt in range(5):
        try:
            resp = generate(
                client,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            raw = resp.text.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            return json.loads(raw)
        except Exception as e:
            last_exc = e
            err = str(e)
            is_quota = _is_retryable(e)
            if not is_quota:
                raise
            if attempt < 4:
                retry_delay = None
                m = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', err)
                if m:
                    val = int(m.group(1))
                    if 1 <= val <= 120:
                        retry_delay = val
                time.sleep(retry_delay or backoff[attempt])
    raise RuntimeError(f"Gemini unavailable after 5 attempts: {last_exc}")


def analyze_profile_cv_gap(profile_md: str, cv_md: str, client) -> dict:
    prompt = f"""You are analyzing the fit between a job seeker's stated goals (profile.md) and their actual career history (CV).

Compare what the profile says the user wants with what the CV actually demonstrates. Identify strengths (CV clearly supports the profile target) and gaps (things the profile says they want that the CV doesn't clearly demonstrate).

Return ONLY a JSON object with this exact schema:
{{
  "alignment_score": <integer 0-10>,
  "positioning_notes": "<one paragraph: how well the CV framing matches the stated target>",
  "strengths": ["<strength 1>", "<strength 2>"],
  "gaps": [
    {{
      "area": "<short area name, e.g. formal people management>",
      "profile_says": "<what the profile expects or targets>",
      "cv_shows": "<what the CV actually demonstrates>",
      "severity": "critical|moderate|minor",
      "suggestion": "<actionable suggestion to close this gap>"
    }}
  ]
}}

Severity guide: critical = CV actively contradicts the profile goal or is missing something a recruiter will ask about in the first screen; moderate = missing proof point that would significantly strengthen the application; minor = nice-to-have that is absent.

<profile>
{profile_md}
</profile>

<cv>
{cv_md}
</cv>"""
    return _call_gemini(client, prompt)


def analyze_position_cv_gap(job: dict, cv_md: str, client) -> dict:
    jd = f"Company: {job.get('company', '')}\nTitle: {job.get('title', '')}\n\n{job.get('description', '')}"
    prompt = f"""You are analyzing whether a job seeker's CV covers the requirements of a specific job description.

For the requirements and preferred qualifications in this JD, assess whether the CV clearly covers each one, partially covers it, or doesn't cover it at all.

Return ONLY a JSON object with this exact schema:
{{
  "match_strength": "strong|partial|weak",
  "strengths": ["<JD requirement clearly covered by the CV>"],
  "gaps": [
    {{
      "requirement": "<specific JD requirement or preferred qualification>",
      "cv_coverage": "none|partial|implicit",
      "note": "<brief note on what is missing or how the partial coverage falls short>"
    }}
  ]
}}

<job_description>
{jd}
</job_description>

<cv>
{cv_md}
</cv>"""
    result = _call_gemini(client, prompt)
    result["job_id"] = job.get("apply_url", "")
    result["company"] = job.get("company", "")
    result["title"] = job.get("title", "")
    result["score"] = job.get("score", 0)
    return result


def analyze_position_profile_gap(job: dict, profile_md: str, client) -> dict:
    jd = f"Company: {job.get('company', '')}\nTitle: {job.get('title', '')}\n\n{job.get('description', '')}"
    prompt = f"""You are checking whether a specific job posting actually matches a job seeker's stated targets in their profile.

Look for divergences: cases where the title looks appealing but the description reveals something that contradicts the profile's stated goals (wrong seniority level, wrong domain, IC work framed as lead, etc.).

Return ONLY a JSON object with this exact schema:
{{
  "alignment": "strong|partial|mismatch",
  "divergences": [
    {{
      "profile_says": "<what the profile requires or prefers>",
      "jd_says": "<what the JD actually reveals>",
      "impact": "high|medium|low"
    }}
  ]
}}

If alignment is strong and there are no meaningful divergences, return an empty divergences array.

<profile>
{profile_md}
</profile>

<job_description>
{jd}
</job_description>"""
    result = _call_gemini(client, prompt)
    result["job_id"] = job.get("apply_url", "")
    return result
