| Field | Value |
|---|---|
| **Phase** | P6 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Blocks** | — |
| **Touches** | `rag/ingest.py` (new PDF/doc path), `webapp/backend` CV-upload parser, `pyproject.toml` / `uv.lock` (new dep — see gate below) |
| **Spec files to update** | `CLAUDE.md` (Dependencies section), `RAG_CORE_SPEC.md` (if RAG ingest gains a doc source) |

## Overview

Evaluate and (if it clears the gate) adopt **Microsoft MarkItDown** (`pip install markitdown`, the [open-source Python library](https://github.com/microsoft/markitdown) — NOT the third-party `markitdown.tools` website) as the "arbitrary document → LLM-ready Markdown" step for two places that today parse documents ad hoc:

1. **CV upload** (webapp onboarding / Settings) — currently PDF/DOCX/TXT are parsed to text; MarkItDown gives structure-preserving Markdown (headings, bullets, links) that scores better against `cv.md`.
2. **RAG doc ingestion** (future) — if the `rag/` store ever ingests real PDFs (CVs, job-description PDFs, VC one-pagers) rather than just JSON, MarkItDown is the normalizer.

**Why this is a *spike + maybe adopt*, not a straight build:** the research (this session) showed MarkItDown solves the *easy* case (clean, digital, text-based PDFs → tidy Markdown) very cheaply, but does NOT solve the hard case — it uses `pdfminer.six` with no layout analysis and no built-in OCR, so scanned/image PDFs and dense multi-column layouts degrade badly (benchmarks ~25% success on messy PDFs). For a personal pipeline whose real inputs are Yotam's own clean CV and well-formed JDs, the easy case is exactly what we need — but that assumption must be verified against real inputs before wiring it in.

## Behaviour

- **Dependency gate (blocking):** CLAUDE.md requires asking before adding a dependency. Adding `markitdown` is a new dep — confirm with Yotam before landing. It is pure-Python for the base converter (no heavyweight ML stack), which fits the "keep the tree minimal" rule; the `markitdown-ocr` plugin (LLM-vision OCR) is explicitly OUT of scope for v1.
- **No OCR, no LLM calls in this path.** Base MarkItDown only. Scanned/image PDFs are accepted as "best effort" — if extraction yields near-empty text, surface a clear "couldn't read this PDF" message rather than silently indexing garbage.
- **CV path:** replace/augment the current CV parser so an uploaded PDF/DOCX becomes Markdown before it's stored as the user's CV text. Preserve the existing TXT passthrough. Do not regress DOCX support already shipped in `WEBAPP_CV_UPLOAD_FORMATS`.
- **RAG path:** only wire in if/when `rag/ingest.py` gains a document source. Not required for v1 of this task — the CV path is the concrete win.
- **Third-party site:** never route documents through `markitdown.tools` (unknown host, uploads user CVs off-machine). Local library only.

## Files to Touch
- `webapp/backend/...` — CV-upload document parser (locate the current PDF/DOCX handler wired by `WEBAPP_PDF_CV_UPLOAD` / `WEBAPP_CV_UPLOAD_FORMATS`)
- `rag/ingest.py` — optional doc-source path (defer if not needed)
- `pyproject.toml` / `uv.lock` — add `markitdown` (after dep gate approval)
- `CLAUDE.md` — note `markitdown` in Dependencies

## How to QA
1. Convert Yotam's real CV PDF via MarkItDown → eyeball the Markdown: headings, roles, dates, bullets preserved and readable (falsifiable: no dropped sections, no garbled columns).
2. Upload the same CV through the webapp CV-upload flow → stored CV text matches the MarkItDown output; scoring still runs end-to-end.
3. Feed a deliberately messy input (scanned/image PDF) → the flow surfaces a clear "couldn't read this PDF" message, does NOT store empty/garbage text, and does not crash.
4. `uv run python3 -m pytest tests/ -v` and `uv run python score.py --dry-run` both pass.

## Implementation notes (completed 2026-07-06)

- **Dependency scope:** shipped `markitdown[docx,pdf]>=0.1.6` in `webapp/backend/pyproject.toml`, NOT `markitdown[all]`. Yotam approved "full markitdown", but `[all]` dragged in pandas, onnxruntime-via-msal, pydub, speechrecognition, youtube-transcript-api, python-pptx, openpyxl — off-mission for a CV parser. Scoped to the two extras the CV path uses. Irreducible base cost that remains: `magika` + `onnxruntime` + `numpy` + `sympy` (markitdown's file-type sniffer) — a real deployment-weight increase on Render worth watching.
- **Removed orphans:** dropped `pypdf` and `python-docx` from the backend — MarkItDown's extras (`pdfminer-six`/`pdfplumber`, `mammoth`) replace them; grep confirmed no other backend usage.
- **Endpoint:** `webapp/backend/routers/user.py` `POST /user/parse-cv` — PDF/DOCX now go through a module-level `MarkItDown(enable_plugins=False)` singleton via `convert_stream` with an explicit `StreamInfo(extension, mimetype)` (we know the type from the client, so magika sniffing is skipped). TXT stays a plain UTF-8 decode. Empty/failed extraction still returns the graceful 422 "please paste manually".
- **Verified:** DOCX now preserves structure (headings + `*` bullets) vs the old flat paragraph join; text PDF extracts; a valid image-only/scanned PDF yields empty → 422 (no garbage, no crash).
- **RAG path deferred:** `rag/ingest.py` untouched — its inputs are JSON, not documents, so there's nothing to normalize yet. Wire in only when RAG gains a real document source.
- **Doc updated:** `WEBAPP_SPEC.md` CV-upload bullet (not root `CLAUDE.md` Dependencies — markitdown is a backend-only dep, and that section lists pipeline deps).
- **Not tested:** live browser upload through the deployed webapp (backend `/parse-cv` exercised directly, not via the React onboarding UI). QA should drive one real upload end-to-end.
