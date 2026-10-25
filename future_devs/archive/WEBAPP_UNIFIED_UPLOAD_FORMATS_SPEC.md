# WEBAPP_UNIFIED_UPLOAD_FORMATS

| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | WEBAPP_CV_UPLOAD_FORMATS ✅, WEBAPP_PROFILE_UPLOAD_OR_PROMPT ✅ |
| **Blocks** | — |
| **Touches** | `webapp/frontend/app/onboarding/page.tsx`, `webapp/frontend/app/(app)/settings/page.tsx`, `webapp/backend/routers/user.py`, `webapp/frontend/lib/uploadFormats.ts` (new) |
| **Spec files to update** | `WEBAPP_SPEC.md` |

## Overview

The webapp has two upload flows that accept **different** file-type sets:

- **CV upload** (onboarding Step 2 + Settings): accepts `.pdf`, `.docx`, `.doc`, `.txt` — but **not** `.md`.
- **Profile document upload** (onboarding + Settings): accepts **only** `.md` (read client-side as raw text; never hits the backend).

Yotam wants **both** flows to accept the full set of text-bearing document types: `.md`, `.txt`, `.pdf`, `.docx`, `.doc`. Parsing should route consistently through the backend (`/user/parse-cv`, MarkItDown) so the same extraction path serves both flows, and the allowed-types list should live in **one** place so the `accept=` attributes, the frontend allow-list, and the backend MIME map cannot drift apart.

## Behaviour

**Supported set (both flows):** `.md`, `.txt`, `.pdf`, `.docx`, `.doc`.

- **`accept=` attribute** on every `<input type="file">` (both CV and profile inputs, onboarding and settings) → `.md,.txt,.pdf,.docx,.doc`.
- **Client validation** allows a file if its extension OR MIME is in the supported set. Text types by MIME: `text/markdown`, `text/plain`, `text/x-markdown` (some browsers). Doc types: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/msword`. Because browsers frequently report empty/`""` MIME for `.md`, extension match must be sufficient on its own.
- **Parsing:**
  - `.md`/`.txt` → decode as UTF-8 text (client-side `FileReader` is fine for these; keep the existing fast path).
  - `.pdf`/`.docx`/`.doc` → base64 POST to `/user/parse-cv` (existing endpoint), which extracts via MarkItDown. Because `.md` may report an empty MIME, the backend must map by extension too, not MIME alone — send a filename or explicit extension hint so the backend picks the right parser. Backend adds `text/markdown` → treat as text.
- **Profile flow specifically:** today it only reads `.md` client-side. For the new doc types it must call the backend parse endpoint (same as CV) and drop the extracted text into the profile textarea. The profile flow does not need to persist a "CV file" — it just needs the extracted plain text.
- **Size caps:** keep current caps — profile text path 1 MB; CV/doc path 10 MB. Apply the 10 MB cap to any file routed through the backend regardless of flow.
- **Errors:** on reject, message lists the full set: "Supported: .md, .txt, .pdf, .docx, .doc". On extraction failure, keep the existing "Could not extract text - please paste manually" fallback.
- `.doc` (legacy binary) support via MarkItDown is best-effort; on failure it falls through to the paste-manually message. That is acceptable — do not special-case it.

## Centralization

Create `webapp/frontend/lib/uploadFormats.ts` exporting:
- `ACCEPT_ATTR` — the `accept=` string.
- `SUPPORTED_EXTENSIONS` — array of extensions.
- `TEXT_MIME` / `DOC_MIME` sets and a helper `classifyUpload(file) -> 'text' | 'doc' | null` so both onboarding and settings share one decision function.

Backend `webapp/backend/routers/user.py`: extend `_DOC_EXTENSIONS` / the `parse-cv` branch to accept a `.md`/`.txt` extension hint as text, and key doc parsing off the extension hint (fallback to MIME) so an empty-MIME `.md` is not misrouted.

Import the shared frontend module in both `onboarding/page.tsx` and `settings/page.tsx`, replacing the three duplicated inline lists (two `accept=` attributes + the settings JS allow-list) so a future format change is a one-line edit.

## Files to Touch

- `webapp/frontend/lib/uploadFormats.ts` — **new** shared constants + `classifyUpload` helper.
- `webapp/frontend/app/onboarding/page.tsx` — profile input `accept`, CV input `accept`, `uploadMdFile`/CV `onChange` to use shared helper + backend routing for doc types.
- `webapp/frontend/app/(app)/settings/page.tsx` — same, plus replace the inline `uploadCvFile` allow-list.
- `webapp/backend/routers/user.py` — `parse-cv`: accept extension hint, route `.md`/`.txt` to text path, doc types by extension→parser.
- `WEBAPP_SPEC.md` — document the unified supported-format set for both flows.

## How to QA

1. In onboarding Step 2 (CV) and Settings CV section, upload a `.md` file → text is extracted and populates the CV field (previously rejected).
2. In the profile-document upload (onboarding + Settings), upload each of `.txt`, `.pdf`, `.docx` → extracted text lands in the profile textarea (previously only `.md` worked).
3. Upload an unsupported type (e.g. `.png`) to any of the four inputs → rejected with a message listing `.md, .txt, .pdf, .docx, .doc`; no crash.
4. Confirm the `accept=` attribute on all four file inputs is `.md,.txt,.pdf,.docx,.doc` (inspect the DOM / grep the source) and that all three former inline lists now import from `lib/uploadFormats.ts`.
5. Backend: `POST /user/parse-cv` with a base64 `.docx` and with a `.md` extension hint both return non-empty `text`; an empty-MIME `.md` is not routed to MarkItDown as a PDF.
