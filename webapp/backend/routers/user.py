from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel
from typing import List, Optional
import os
from datetime import datetime, timezone, date, timedelta
from cryptography.fernet import Fernet
from auth import require_user
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
    user_id = require_user(authorization)

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


def derive_setup(row: dict, filters_seen: bool) -> dict:
    """Onboarding state from existing fields only - booleans, never the values.

    complete = profile AND api_key; CV and filters are recommended, not required.
    filters_seen = a score_configs row exists (written by the wizard's filter step
    or Settings).
    """
    def present(k):
        v = row.get(k)
        return bool(v.strip()) if isinstance(v, str) else bool(v)
    profile, cv, api_key = present("profile_md"), present("cv_text"), present("gemini_api_key_encrypted")
    return {"profile": profile, "cv": cv, "api_key": api_key, "filters_seen": filters_seen, "complete": profile and api_key}


@router.get("/me")
def get_me(authorization: str = Header(...)):
    user_id = require_user(authorization)
    row = getattr(supabase.table("users").select(
        "scoring_runs_this_week,last_week_reset,profile_md,cv_text,profile_version,profile_updated_at,cv_updated_at,gemini_api_key_encrypted"
    ).eq("id", user_id).maybe_single().execute(), "data", None)
    filters_row = getattr(supabase.table("score_configs").select("user_id").eq("user_id", user_id).limit(1).execute(), "data", None)
    if not row:
        return {"setup": derive_setup({}, bool(filters_row))}
    setup = derive_setup(row, bool(filters_row))
    has_api_key = bool(row.get("gemini_api_key_encrypted"))
    api_key_last4 = None
    if has_api_key and FERNET_KEY:
        try:
            f = Fernet(FERNET_KEY.encode())
            decrypted = f.decrypt(row["gemini_api_key_encrypted"].encode()).decode()
            api_key_last4 = decrypted[-4:] if len(decrypted) >= 4 else None
        except Exception:
            pass
    row = {k: v for k, v in row.items() if k != "gemini_api_key_encrypted"}
    row["has_api_key"] = has_api_key
    if api_key_last4:
        row["api_key_last4"] = api_key_last4
    # The weekly scoring run limit resets at the start of the ISO week (Monday).
    # Mirror scoring._reset_if_new_week's notion of "week" by reporting the next
    # upcoming Monday. If today is Monday, the next reset is 7 days out.
    today = date.today()
    days_until_monday = (7 - today.weekday()) % 7 or 7
    row["run_limit_resets_on"] = (today + timedelta(days=days_until_monday)).isoformat()
    row["setup"] = setup
    return row


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
    user_id = require_user(authorization)
    current = getattr(supabase.table("users").select("profile_version").eq("id", user_id).maybe_single().execute(), "data", None)
    new_version = ((current or {}).get("profile_version") or 1) + 1
    now = datetime.now(timezone.utc).isoformat()
    # upsert, not update: the onboarding wizard saves per step, possibly before the users row exists
    supabase.table("users").upsert({"id": user_id, "profile_md": body.profile_md, "profile_version": new_version, "profile_updated_at": now}).execute()
    return {"status": "ok", "profile_version": new_version, "profile_updated_at": now}


@router.patch("/cv")
def update_cv(body: CvUpdate, authorization: str = Header(...)):
    user_id = require_user(authorization)
    now = datetime.now(timezone.utc).isoformat()
    supabase.table("users").upsert({"id": user_id, "cv_text": body.cv_text, "cv_updated_at": now}).execute()
    return {"status": "ok", "cv_updated_at": now}


@router.get("/filters")
def get_filters(authorization: str = Header(...)):
    user_id = require_user(authorization)
    row = getattr(supabase.table("score_configs").select("*").eq("user_id", user_id).maybe_single().execute(), "data", None)
    return row or {}


@router.patch("/filters")
def update_filters(body: FiltersUpdate, authorization: str = Header(...)):
    user_id = require_user(authorization)
    supabase.table("score_configs").upsert({
        "user_id": user_id,
        **body.model_dump(),
    }, on_conflict="user_id").execute()
    return {"status": "ok"}


@router.patch("/apikey")
def update_apikey(body: ApiKeyUpdate, authorization: str = Header(...)):
    user_id = require_user(authorization)
    fernet_key = os.environ.get("FERNET_KEY", "")
    f = Fernet(fernet_key.encode())
    encrypted = f.encrypt(body.gemini_api_key.encode()).decode()
    supabase.table("users").upsert({"id": user_id, "gemini_api_key_encrypted": encrypted}).execute()
    return {"status": "ok"}


class TestKeyRequest(BaseModel):
    gemini_api_key: str

@router.post("/test-key-inline")
def test_apikey_inline(body: TestKeyRequest, authorization: str = Header(...)):
    user_id = require_user(authorization)
    try:
        import google.genai as genai
        client = genai.Client(api_key=body.gemini_api_key)
        client.models.generate_content(model="gemini-3.5-flash-lite", contents="ping")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/test-key")
def test_apikey(authorization: str = Header(...)):
    user_id = require_user(authorization)
    row = getattr(supabase.table("users").select("gemini_api_key_encrypted").eq("id", user_id).maybe_single().execute(), "data", None)
    if not row or not row.get("gemini_api_key_encrypted"):
        raise HTTPException(status_code=400, detail="No API key saved yet - save your key first, or paste one to test it")
    fernet_key = os.environ.get("FERNET_KEY", "")
    f = Fernet(fernet_key.encode())
    api_key = f.decrypt(row["gemini_api_key_encrypted"].encode()).decode()
    try:
        import google.genai as genai
        client = genai.Client(api_key=api_key)
        client.models.generate_content(model="gemini-3.5-flash-lite", contents="ping")
        return {"ok": True}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/apikey")
def delete_apikey(authorization: str = Header(...)):
    user_id = require_user(authorization)
    supabase.table("users").update({"gemini_api_key_encrypted": None}).eq("id", user_id).execute()
    return {"status": "ok"}


@router.get("/export")
def export_data(authorization: str = Header(...)):
    from fastapi.responses import JSONResponse
    user_id = require_user(authorization)
    jobs = supabase.table("scored_jobs").select("*").eq("user_id", user_id).execute().data
    return JSONResponse(content=jobs, headers={"Content-Disposition": "attachment; filename=careerwatch_export.json"})


@router.delete("/account")
def delete_account(authorization: str = Header(...)):
    user_id = require_user(authorization)
    supabase.table("users").delete().eq("id", user_id).execute()
    try:
        supabase.auth.admin.delete_user(user_id)
    except Exception:
        pass
    return {"status": "ok"}


_MARKITDOWN = None

# MIME -> file extension hint. We know the type from the client, so we pass it
# explicitly and skip MarkItDown's magika-based type sniffing.
_DOC_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
}

# Extensions we decode as UTF-8 text directly - no MarkItDown needed.
_TEXT_EXTENSIONS = {".md", ".txt"}
_TEXT_MIMES = {"text/plain", "text/markdown", "text/x-markdown"}
# Reverse of _DOC_EXTENSIONS: extension -> MIME, for the extension hint path.
_DOC_EXT_TO_MIME = {v: k for k, v in _DOC_EXTENSIONS.items()}


def _markitdown():
    global _MARKITDOWN
    if _MARKITDOWN is None:
        from markitdown import MarkItDown
        _MARKITDOWN = MarkItDown(enable_plugins=False)
    return _MARKITDOWN


@router.post("/parse-cv")
async def parse_cv(request: Request, authorization: str = Header(...)):
    user_id = require_user(authorization)
    body = await request.json()
    file_b64 = body.get("pdf_b64", "")
    mime_type = body.get("mime_type", "application/pdf")
    # Extension hint from the client - browsers often report an empty or wrong
    # MIME for .md/.txt, so prefer the extension when it is present.
    extension = (body.get("extension") or "").lower()
    import base64, io
    file_bytes = base64.b64decode(file_b64)
    try:
        is_text = extension in _TEXT_EXTENSIONS or (not extension and mime_type in _TEXT_MIMES)
        doc_ext = extension if extension in _DOC_EXT_TO_MIME else _DOC_EXTENSIONS.get(mime_type)
        if is_text:
            text = file_bytes.decode("utf-8", errors="replace")
        elif doc_ext:
            from markitdown import StreamInfo
            result = _markitdown().convert_stream(
                io.BytesIO(file_bytes),
                stream_info=StreamInfo(
                    extension=doc_ext, mimetype=_DOC_EXT_TO_MIME[doc_ext]
                ),
            )
            text = result.text_content
        else:
            raise HTTPException(status_code=422, detail="Unsupported file type")
        if not text or not text.strip():
            raise HTTPException(status_code=422, detail="Could not extract text - please paste manually")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=422, detail="Could not extract text - please paste manually")
    return {"text": text}
