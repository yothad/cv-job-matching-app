# Spec: webapp_onboarding

**Slug:** webapp_onboarding  
**Epic:** Web App v1  
**Effort:** M  
**Depends on:** webapp_auth ✅

---

## Goal

Build the 4-step onboarding flow for first-time users. After the last step, trigger the first scoring run and redirect to /digest.

---

## File: `webapp/frontend/app/onboarding/page.tsx`

Replace the `<h1>Onboarding</h1>` stub with the full 4-step wizard.

This is a client component (`'use client'`). All API calls go to `NEXT_PUBLIC_API_URL`. All Supabase writes use the browser client from `lib/supabaseClient.ts`.

### State shape

```ts
const [step, setStep] = useState(1)          // 1-4
const [profileMd, setProfileMd] = useState('')
const [cvText, setCvText] = useState('')
const [geminiKey, setGeminiKey] = useState('')
const [filters, setFilters] = useState({
  location_terms: [] as string[],
  skip_title_terms: ['data engineer', 'analyst', 'data analyst', 'bi developer', 'bi analyst'] as string[],
  keep_title_terms: [] as string[],
  skip_companies: [] as string[],
  skip_industries: ['gaming', 'adtech', 'gambling', 'crypto'] as string[],
})
const [saving, setSaving] = useState(false)
const [error, setError] = useState('')
```

### Step 1 — Generate your profile

```
Title: "Generate your profile"
Subtitle: "Your profile tells the AI what to look for. The best way to create it is to use an AI assistant."

[Copyable prompt block — monospace textarea, read-only, with "Copy prompt" button]

Prompt text:
"""
I'm setting up a job-matching tool that scores job postings against my profile.
I need you to create a profile.md file for me by asking me questions about:
- My background and years of experience
- My target roles (title, seniority)
- My preferred domains/industries
- What I consider a strong fit vs. a dealbreaker
- My location and commute constraints
- What I explicitly don't want

Ask me one section at a time. When done, output a complete profile.md in markdown.
"""

Below the prompt block:
[Paste your profile.md here — textarea, 10 rows]

[Next →] button — disabled if profileMd.trim() is empty
```

### Step 2 — Upload your CV

```
Title: "Upload your CV"
Subtitle: "Your CV is used verbatim in scoring prompts."

Two options:
  (a) Paste text — large textarea
  (b) Upload PDF — <input type="file" accept=".pdf"> 
      On file select: read as ArrayBuffer, encode base64,
      POST to /api/parse-cv (see backend section below)
      On response: setCvText(response.text)

[← Back]  [Next →] — Next disabled if cvText.trim() is empty
```

### Step 3 — Gemini API key

```
Title: "Your Gemini API key"
Subtitle: "Used only for scoring. Never logged or shared."

[Password input — masked]

Expandable "How to get a key" section:
  1. Go to Google AI Studio (link: https://aistudio.google.com)
  2. Sign in with your Google account
  3. Click "Get API key" then "Create API key"
  4. Copy and paste the key here
  5. The free tier is enough to get started (quota resets daily)

Small note: "We never score jobs without your key. If you delete it, scoring stops."

[← Back]  [Next →] — Next disabled if geminiKey.trim() is empty
```

### Step 4 — Configure filters

```
Title: "Configure filters"
Subtitle: "Jobs not matching these filters are dropped before scoring."

Fields:
  Location (text input): "e.g. israel, tel aviv — leave blank for no filter"
    -> updates filters.location_terms as a single-element array if non-empty
  
  Title denylist (tags input): pre-populated from filters.skip_title_terms
    -> comma-separated tags; user can add/remove
  
  Title allowlist (tags input): pre-populated from filters.keep_title_terms (empty)
    -> leave blank = score everything that passes denylist
  
  Excluded companies (tags input): filters.skip_companies
  
  Excluded industries (tags input): filters.skip_industries, pre-populated

[← Back]  [Start scoring →]
```

Tags input implementation: simple comma-separated input with inline pill display. When user presses comma or Enter, add tag. Click X on pill to remove. No external library.

### Resume behaviour (superseded by WEBAPP_FIRST_LOGIN_JOURNEY)

The single `POST /user/setup` at the end is no longer used by the wizard. Each step now saves on Next (`PATCH /user/profile`, `/user/cv`, `/user/apikey`; filters via `PATCH /user/filters` on finish), and re-opening `/onboarding` resumes at the first incomplete step from `GET /user/me`'s derived `setup` object. A complete user sees a "You're all set" card instead of the wizard. The snippet below is the original design, kept for history.

### On "Start scoring →"

```ts
async function finishOnboarding() {
  setSaving(true)
  setError('')
  try {
    const { data: { session } } = await supabase.auth.getSession()
    const token = session?.access_token
    const userId = session?.user?.id
    if (!token || !userId) throw new Error('Not authenticated')

    // Encrypt and store Gemini key via backend
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/user/setup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({
        profile_md: profileMd,
        cv_text: cvText,
        gemini_api_key: geminiKey,
        filters,
      }),
    }).then(r => { if (!r.ok) throw new Error('Setup failed') })

    // Trigger first scoring run
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/score/`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    // Redirect even if scoring fails — user can retry from digest
  } catch (e: unknown) {
    setError(e instanceof Error ? e.message : 'Something went wrong')
    setSaving(false)
    return
  }
  window.location.href = '/digest'
}
```

### Layout

- Progress bar at top: 4 dots, current step highlighted green
- Step content in a centered card (`max-w-2xl mx-auto`)
- Back/Next buttons at bottom of card
- Dark theme matching auth page (`bg-gray-950`, card `bg-gray-900`)

---

## Backend: `webapp/backend/routers/user.py`

### POST /user/setup

Receives profile_md, cv_text, gemini_api_key (plaintext), filters. Encrypts the key with Fernet. Upserts into users + score_configs tables.

```python
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import List
import os
from cryptography.fernet import Fernet
from db.supabase_client import supabase

router = APIRouter(prefix="/user", tags=["user"])

FERNET_KEY = os.environ.get("FERNET_KEY", "")


class SetupRequest(BaseModel):
    profile_md: str
    cv_text: str
    gemini_api_key: str
    filters: dict


@router.post("/setup")
def setup_user(body: SetupRequest, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    auth_resp = supabase.auth.get_user(token)
    if not auth_resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = auth_resp.user.id

    f = Fernet(FERNET_KEY.encode())
    encrypted_key = f.encrypt(body.gemini_api_key.encode()).decode()

    supabase.table("users").upsert({
        "id": user_id,
        "profile_md": body.profile_md,
        "cv_text": body.cv_text,
        "gemini_api_key_encrypted": encrypted_key,
    }).execute()

    filters = body.filters
    supabase.table("score_configs").upsert({
        "user_id": user_id,
        "location_terms": filters.get("location_terms", []),
        "skip_title_terms": filters.get("skip_title_terms", []),
        "keep_title_terms": filters.get("keep_title_terms", []),
        "skip_companies": filters.get("skip_companies", []),
        "skip_industries": filters.get("skip_industries", []),
    }, on_conflict="user_id").execute()

    return {"status": "ok"}
```

### POST /api/parse-cv (optional — only if PDF upload is implemented)

If implementing PDF upload: add `pypdf>=4.0` to `webapp/backend/pyproject.toml` and create a simple endpoint that accepts a base64-encoded PDF and returns extracted text.

```python
@router.post("/parse-cv")
async def parse_cv(request: Request, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    auth_resp = supabase.auth.get_user(token)
    if not auth_resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    body = await request.json()
    pdf_b64 = body.get("pdf_b64", "")
    import base64, io
    from pypdf import PdfReader
    pdf_bytes = base64.b64decode(pdf_b64)
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return {"text": text}
```

Add this endpoint to the user router. Add `pypdf>=4.0` to `webapp/backend/pyproject.toml` dependencies.

### Register router in main.py

```python
from routers.user import router as user_router
app.include_router(user_router)
```

---

## Touches

- `webapp/frontend/app/onboarding/page.tsx` (replace stub)
- `webapp/backend/routers/user.py` (new)
- `webapp/backend/main.py` (add user router)
- `webapp/backend/pyproject.toml` (add pypdf)

---

## Exit gate

```bash
ls /Users/omerhedvat/git/careers-watch/webapp/frontend/app/onboarding/page.tsx
ls /Users/omerhedvat/git/careers-watch/webapp/backend/routers/user.py
grep "use client" /Users/omerhedvat/git/careers-watch/webapp/frontend/app/onboarding/page.tsx
grep "user_router" /Users/omerhedvat/git/careers-watch/webapp/backend/main.py
python3 -c "import ast; ast.parse(open('/Users/omerhedvat/git/careers-watch/webapp/backend/routers/user.py').read()); print('syntax OK')"
cd /Users/omerhedvat/git/careers-watch && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
