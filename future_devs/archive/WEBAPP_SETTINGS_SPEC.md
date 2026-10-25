# Spec: webapp_settings

**Slug:** webapp_settings  
**Epic:** Web App v1  
**Effort:** S  
**Depends on:** webapp_digest ✅

---

## Goal

Build the settings page with 5 tabs: Profile, CV, Filters, API Key, Account. Each tab loads the user's current data and lets them save changes.

---

## File: `webapp/frontend/app/settings/page.tsx`

Replace the `<h1>Settings</h1>` stub. Client component (`'use client'`).

### Tab structure

```tsx
type Tab = 'profile' | 'cv' | 'filters' | 'apikey' | 'account'
const [activeTab, setActiveTab] = useState<Tab>('profile')
```

Tab bar at top: Profile | CV | Filters | API Key | Account

### Tab 1 — Profile

- Loads `profile_md` from GET /user/me
- Displays in a large `<textarea>` (20 rows)
- "Save profile" button — PATCH /user/profile with `{ profile_md }`
- Copyable prompt block (same prompt as onboarding step 1) under "Regenerate with AI" label
- No rescore button (out of scope per WEBAPP_SPEC.md)

### Tab 2 — CV

- Loads `cv_text` from GET /user/me
- Displays in a large `<textarea>` (20 rows)
- "Save CV" button — PATCH /user/cv with `{ cv_text }`

### Tab 3 — Filters

- Loads score_config from GET /user/filters
- Same tags-input UI as onboarding step 4 (location text, 4 tag arrays)
- "Save filters" button — PATCH /user/filters with the full filters object

### Tab 4 — API Key

- Masked password input (current key never shown — placeholder "••••••••••••")
- "Replace key" button — PATCH /user/apikey with `{ gemini_api_key }` (plaintext; backend encrypts)
- "Test key" button — POST /user/test-key — fires a minimal Gemini call, returns `{ ok: true }` or error message
- "Delete key" (red, destructive) — DELETE /user/apikey — sets `gemini_api_key_encrypted` to null

### Tab 5 — Account

- "Change email" — input + save (calls supabase.auth.updateUser)
- "Change password" — input + save (calls supabase.auth.updateUser)
- "Export data (JSON)" — GET /user/export — returns all scored_jobs as JSON, browser triggers download
- "Delete account" (red) — confirm dialog then DELETE /user/account, sign out, redirect to /

### Layout

- Same dark theme as auth/onboarding
- Tab bar: `flex border-b border-gray-700`, active tab has `border-b-2 border-green-500`
- Each tab panel is a card `bg-gray-900 rounded-xl p-6 mt-4`
- Success/error messages inline below each form

---

## Backend: new endpoints in `webapp/backend/routers/user.py`

Add to the existing user router (all require `Authorization: Bearer <token>`):

```python
from fastapi import APIRouter, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import os, json
from cryptography.fernet import Fernet
from db.supabase_client import supabase

# --- add these models and endpoints to existing user.py ---

class ProfileUpdate(BaseModel):
    profile_md: str

class CvUpdate(BaseModel):
    cv_text: str

class FiltersUpdate(BaseModel):
    location_terms: List[str] = []
    skip_title_terms: List[str] = []
    keep_title_terms: List[str] = []
    skip_companies: List[str] = []
    skip_industries: List[str] = []

class ApiKeyUpdate(BaseModel):
    gemini_api_key: str


@router.patch("/profile")
def update_profile(body: ProfileUpdate, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    supabase.table("users").update({"profile_md": body.profile_md}).eq("id", resp.user.id).execute()
    return {"status": "ok"}


@router.patch("/cv")
def update_cv(body: CvUpdate, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    supabase.table("users").update({"cv_text": body.cv_text}).eq("id", resp.user.id).execute()
    return {"status": "ok"}


@router.get("/filters")
def get_filters(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    row = supabase.table("score_configs").select("*").eq("user_id", resp.user.id).maybe_single().execute().data
    return row or {}


@router.patch("/filters")
def update_filters(body: FiltersUpdate, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    supabase.table("score_configs").upsert({
        "user_id": resp.user.id,
        **body.model_dump(),
    }, on_conflict="user_id").execute()
    return {"status": "ok"}


@router.patch("/apikey")
def update_apikey(body: ApiKeyUpdate, authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    fernet_key = os.environ.get("FERNET_KEY", "")
    f = Fernet(fernet_key.encode())
    encrypted = f.encrypt(body.gemini_api_key.encode()).decode()
    supabase.table("users").update({"gemini_api_key_encrypted": encrypted}).eq("id", resp.user.id).execute()
    return {"status": "ok"}


@router.post("/test-key")
def test_apikey(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    row = supabase.table("users").select("gemini_api_key_encrypted").eq("id", resp.user.id).maybe_single().execute().data
    if not row or not row.get("gemini_api_key_encrypted"):
        raise HTTPException(status_code=400, detail="No API key stored")
    fernet_key = os.environ.get("FERNET_KEY", "")
    f = Fernet(fernet_key.encode())
    api_key = f.decrypt(row["gemini_api_key_encrypted"].encode()).decode()
    try:
        import google.genai as genai
        client = genai.Client(api_key=api_key)
        client.models.generate_content(model="gemini-2.0-flash", contents="ping")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/apikey")
def delete_apikey(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    supabase.table("users").update({"gemini_api_key_encrypted": None}).eq("id", resp.user.id).execute()
    return {"status": "ok"}


@router.get("/export")
def export_data(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    jobs = supabase.table("scored_jobs").select("*").eq("user_id", resp.user.id).execute().data
    return JSONResponse(content=jobs, headers={"Content-Disposition": "attachment; filename=careerwatch_export.json"})


@router.delete("/account")
def delete_account(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = resp.user.id
    # Delete user data (cascade handles scored_jobs, score_configs)
    supabase.table("users").delete().eq("id", user_id).execute()
    # Note: deleting from Supabase Auth requires service role - done via admin API
    supabase.auth.admin.delete_user(user_id)
    return {"status": "ok"}
```

---

## Touches

- `webapp/frontend/app/settings/page.tsx` (replace stub)
- `webapp/backend/routers/user.py` (add new endpoints)

---

## Exit gate

```bash
ls C:/repos/cv-job-matching-app/webapp/frontend/app/settings/page.tsx
grep "use client" C:/repos/cv-job-matching-app/webapp/frontend/app/settings/page.tsx
grep "activeTab" C:/repos/cv-job-matching-app/webapp/frontend/app/settings/page.tsx
python3 -c "import ast; ast.parse(open('C:/repos/cv-job-matching-app/webapp/backend/routers/user.py').read()); print('syntax OK')"
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
