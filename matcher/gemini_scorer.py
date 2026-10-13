import json
import os
import re
import time
import threading
from collections import deque


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class QuotaExhaustedError(Exception):
    """Raised when Gemini returns RESOURCE_EXHAUSTED and retries are exhausted."""


# ---------------------------------------------------------------------------
# Per-minute rate limiter (sliding window, thread-safe)
# ---------------------------------------------------------------------------

# Ordered model cascade (borrowed from PowerME's GeminiApiClient). Which model ids a key can use
# depends on its Google project - gemini-2.5-flash 404s for keys created after 2026-10 - so a
# model-specific failure (gone, busy, rate-limited, server error) moves on to the next model
# instead of failing the job. Pinned ids only: the floating "-latest" aliases hung or 503'd.
# Override without a code change via GEMINI_MODELS (comma list) on Render / GitHub Actions.
MODELS = [m.strip() for m in os.environ.get("GEMINI_MODELS", "gemini-3.5-flash,gemini-3.5-flash-lite").split(",")
          if m.strip()]

_NEXT_MODEL_CODES = {404, 429, 500, 502, 503, 504}
_SERVER_CODES = {500, 502, 503, 504}
# A model that just returned busy/5xx is skipped for a while, so every batch does not spend a call
# on it before falling back (3.5-flash 503'd on nearly every batch on 2026-10-13).
_COOLDOWN_S = 120
_cooldown_until: dict[str, float] = {}


def _status_code(e: Exception) -> int | None:
    code = getattr(e, "code", None)  # google.genai errors.APIError carries the HTTP status
    if isinstance(code, int):
        return code
    m = re.match(r"\s*(\d{3})\b", str(e))
    return int(m.group(1)) if m else None


def generate(client, contents, config=None):
    """client.models.generate_content over the MODELS cascade. Advances to the next model on a
    model-specific failure; anything else (bad key, bad request) is raised at once. When every
    model fails, the last error is raised so the callers' 429 backoff still applies."""
    now = time.monotonic()
    ready = [m for m in MODELS if _cooldown_until.get(m, 0) <= now]
    order = ready + [m for m in MODELS if m not in ready]  # cooling models last, never dropped
    last = None
    for i, model in enumerate(order):
        try:
            return client.models.generate_content(model=model, contents=contents, config=config)
        except Exception as e:
            code = _status_code(e)
            if code not in _NEXT_MODEL_CODES:
                raise
            last = e
            if code in _SERVER_CODES or code == 429:
                _cooldown_until[model] = time.monotonic() + _COOLDOWN_S
            if i + 1 < len(order):
                print(f"[gemini] {model} failed ({code}) - trying {order[i + 1]}")
    raise last


def _is_retryable(e: Exception) -> bool:
    """429 / quota, or a transient Gemini server error (5xx) - worth a backoff and another try."""
    s = str(e)
    return (_status_code(e) in _SERVER_CODES or "429" in s or "RESOURCE_EXHAUSTED" in s
            or "quota" in s.lower() or "rate" in s.lower())

_RPM_LIMIT = int(os.environ.get("GEMINI_RPM", "8"))
_rpm_lock = threading.Lock()
_rpm_timestamps: deque = deque()  # timestamps of recent calls (seconds)


def _rpm_wait():
    """Block until it is safe to make another generate_content call."""
    while True:
        with _rpm_lock:
            now = time.monotonic()
            # Drop timestamps older than 60 s
            while _rpm_timestamps and now - _rpm_timestamps[0] >= 60.0:
                _rpm_timestamps.popleft()
            if len(_rpm_timestamps) < _RPM_LIMIT:
                _rpm_timestamps.append(now)
                return  # cleared to proceed
            # Need to wait until the oldest call ages out
            oldest = _rpm_timestamps[0]
            wait_secs = 60.0 - (now - oldest) + 0.05  # small buffer
        time.sleep(wait_secs)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def build_batch_prompt(jobs: list[dict], profile_md: str, cv_md: str) -> str:
    jobs_block = ""
    for i, job in enumerate(jobs, 1):
        job_text = "\n".join(
            f"  {k}: {v}" for k, v in {
                "Company": job.get("company", ""),
                "Title": job.get("title", ""),
                "Location": job.get("location", ""),
                "Source VC": job.get("source_vc", ""),
                "VC Tier": job.get("vc_tier", ""),
                "Apply URL": job.get("apply_url", ""),
                "Description": job.get("description", ""),
            }.items()
        )
        jobs_block += f'<job index="{i}">\n{job_text}\n</job>\n\n'

    n = len(jobs)
    return f"""You are a job-fit scorer for a specific candidate. Score each of the {n} jobs below against the candidate profile and CV.

Return ONLY a JSON array with exactly {n} objects, one per job in order. Each object must have:
{{
  "score": <integer 0-10>,
  "reasoning": "<one concise sentence>",
  "flags": ["<short-flag>", ...]
}}

Flag examples: "location-unclear", "lead-path-implied", "management-gap", "wrong-domain", "dealbreaker-location", "title-laundering", "llm-not-security"

Do not add any text outside the JSON array.

<profile>
{profile_md}
</profile>

<cv>
{cv_md}
</cv>

{jobs_block.rstrip()}"""


def score_jobs_batch(jobs: list[dict], profile_md: str, cv_md: str, client) -> list[dict]:
    """Score a batch of jobs in a single API call. Returns one {score, reasoning, flags} per job."""
    prompt = build_batch_prompt(jobs, profile_md, cv_md)
    backoff_seconds = [4, 8, 16, 32]
    last_exc = None

    for attempt in range(5):
        _rpm_wait()
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
            data = json.loads(raw)
            if not isinstance(data, list):
                data = [data]
            results = []
            for i in range(len(jobs)):
                # Per-item isolation: one malformed or missing item must not fail the whole batch.
                try:
                    item = data[i]
                    results.append({
                        "score": int(item.get("score", 0)),
                        "reasoning": str(item.get("reasoning", "")),
                        "flags": list(item.get("flags", [])),
                    })
                except Exception as item_err:
                    results.append({
                        "score": 0,
                        "reasoning": f"scorer error: bad item {i + 1}/{len(jobs)}: {item_err!r}",
                        "flags": ["scorer-error"],
                    })
            return results
        except Exception as e:
            last_exc = e
            err_str = str(e)
            is_server = _status_code(e) in _SERVER_CODES
            is_429 = _is_retryable(e)
            if not is_429:
                fallback = {"score": 0, "reasoning": f"scorer error: {e}", "flags": ["scorer-error"]}
                return [fallback] * len(jobs)

            retry_delay = None
            match = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', err_str)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 120:
                    retry_delay = val

            if attempt < 4:
                wait = retry_delay if retry_delay else backoff_seconds[attempt]
                kind = "Gemini server error" if is_server else "429 RESOURCE_EXHAUSTED"
                print(f"[scorer] {kind} on attempt {attempt + 1}/5 - waiting {wait}s before retry...")
                time.sleep(wait)
            elif is_server:
                # a Gemini outage, not quota: skip these jobs (retried next run), keep the run going
                return [{"score": 0, "reasoning": f"scorer error: {e}", "flags": ["scorer-error"]}] * len(jobs)
            else:
                raise QuotaExhaustedError(
                    f"Gemini quota exhausted after 5 attempts. Last error: {last_exc}"
                ) from last_exc

    raise QuotaExhaustedError(f"Gemini quota exhausted. Last error: {last_exc}")


def build_prompt(job: dict, profile_md: str, cv_md: str) -> str:
    job_block = "\n".join(
        f"{k}: {v}" for k, v in {
            "Company": job.get("company", ""),
            "Title": job.get("title", ""),
            "Location": job.get("location", ""),
            "Source VC": job.get("source_vc", ""),
            "VC Tier": job.get("vc_tier", ""),
            "Apply URL": job.get("apply_url", ""),
            "Description": job.get("description", ""),
        }.items()
    )

    return f"""You are a job-fit scorer for a specific candidate. Your job is to read the candidate profile (what they want), their CV (what they have done), and a job posting, then score the fit 0-10 per the rubric defined in the profile.

Return ONLY a JSON object with this exact schema:
{{
  "score": <integer 0-10>,
  "reasoning": "<one concise sentence explaining the score>",
  "flags": ["<short-flag>", ...]
}}

Flag examples: "location-unclear", "lead-path-implied", "management-gap", "wrong-domain", "dealbreaker-location", "title-laundering", "llm-not-security"

Do not add any text outside the JSON.

<profile>
{profile_md}
</profile>

<cv>
{cv_md}
</cv>

<job>
{job_block}
</job>"""


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

def score_job(job: dict, profile_md: str, cv_md: str, client) -> dict:
    prompt = build_prompt(job, profile_md, cv_md)

    backoff_seconds = [4, 8, 16, 32]  # delays before attempts 2-5
    last_exc = None

    for attempt in range(5):
        _rpm_wait()
        try:
            resp = generate(
                client,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )
            raw = resp.text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            data = json.loads(raw)
            return {
                "score": int(data.get("score", 0)),
                "reasoning": str(data.get("reasoning", "")),
                "flags": list(data.get("flags", [])),
            }
        except Exception as e:
            last_exc = e
            err_str = str(e)
            # Detect quota / rate-limit errors
            is_server = _status_code(e) in _SERVER_CODES
            is_429 = _is_retryable(e)
            if not is_429:
                # Non-quota error - per-job problem, return score=0 immediately
                return {"score": 0, "reasoning": f"scorer error: {e}", "flags": ["scorer-error"]}

            # Quota error - try to parse retryDelay from Gemini error body.
            # Gemini encodes retryDelay as a string like "retryDelay": "30s".
            # Cap at 120s to guard against malformed values (e.g. epoch timestamps).
            retry_delay = None
            match = re.search(r'"retryDelay"\s*:\s*"(\d+)s"', err_str)
            if match:
                val = int(match.group(1))
                if 1 <= val <= 120:
                    retry_delay = val

            if attempt < 4:
                wait = retry_delay if retry_delay else backoff_seconds[attempt]
                kind = "Gemini server error" if is_server else "429 RESOURCE_EXHAUSTED"
                print(f"[scorer] {kind} on attempt {attempt + 1}/5 - waiting {wait}s before retry...")
                time.sleep(wait)
            elif is_server:
                return {"score": 0, "reasoning": f"scorer error: {e}", "flags": ["scorer-error"]}
            else:
                # Final attempt also failed with quota error
                raise QuotaExhaustedError(
                    f"Gemini quota exhausted after 5 attempts. Last error: {last_exc}"
                ) from last_exc

    # Should not reach here
    raise QuotaExhaustedError(f"Gemini quota exhausted. Last error: {last_exc}")
