| Field | Value |
|---|---|
| **Phase** | P5 |
| **Status** | `wrapped` |
| **Effort** | S |
| **Epic** | — |
| **Depends on** | — |
| **Touches** | `webapp/frontend/app/settings/page.tsx`, `webapp/backend/routers/user.py` |

## Overview

The Settings page is built as a stack of mostly-blank input boxes. Some tabs silently pre-fill from the server (Profile, CV, Filters), but two tabs — **API Key** and **Account** — show *nothing* about the user's current state, so the user can't tell whether a key is configured or even confirm which account they're signed into. Even the tabs that do load their values don't *frame* themselves as "here is what is saved," so it reads as a form you fill from scratch rather than a mirror of your stored config.

**Design principle for this task: Settings is a mirror of saved state first, an editor second.** Every tab should open by showing the user what is currently stored, then offer controls to change it. Saving should visibly update that mirror, not just flash a toast that disappears.

This addresses Yotam's report: values should stay visible after saving; CV viewable as file/text; filters visibly editable; API Key should signal present-vs-missing; Account should show name + email.

## Behaviour

### Cross-cutting

- Each tab renders a **"current state" header block** above its editor, derived from server data loaded on mount.
- After a successful save, the current-state block updates in place (re-fetch or optimistic update) so the change is reflected, not just announced by the transient `flash()` toast.
- Empty/unset values render an explicit muted placeholder ("None set", "No CV on file", "No API key") so "intentionally empty" is distinguishable from "not loaded yet".

### Profile tab

- Add a header: `Profile saved · v{profile_version}` when `profile_md` is non-empty, or `No profile yet` when blank.
- Keep the existing editable textarea as the mirror of `profile_md`.
- When empty, surface the "Regenerate with AI" prompt CTA more prominently (empty-state hint).

### CV tab

- Show the CV as **both file identity and text**:
  - Persist `cv_filename` and `cv_source` (`uploaded` | `pasted`) so the header can read e.g. `Uploaded resume.pdf · 12 Jun 2026` or `Pasted text · 12 Jun 2026`.
  - Show a character/word count next to the timestamp as a quick "the CV is really there" signal.
  - Provide a **"Download as .txt"** button that exports the stored `cv_text` — so the user can always retrieve what the system holds, even though the original binary isn't kept.
- Editable textarea remains the canonical mirror of `cv_text`.
- When no CV: `No CV on file yet — upload a file or paste text below.` (existing copy, kept).

### Filters tab

- Add a compact **"Active filters" summary** line at the top: counts per category (e.g. `Location: israel · 3 skip-titles · 1 keep-title · 2 excluded companies · 0 excluded industries`).
- Each empty TagInput shows a muted `None set` affordance inside the box rather than rendering an empty bordered area.
- Add/delete already works via `TagInput`; no behavioural change there, just clearer framing.

### API Key tab (biggest change)

- Backend `/user/me` returns `has_api_key: bool` (derived from `gemini_api_key_encrypted IS NOT NULL`). Optionally `api_key_last4` (last 4 chars of the decrypted key) for a masked hint — **never** the full key.
- Header status pill:
  - Configured → green `✓ Gemini key configured` (plus `AIza••••••••{last4}` if `api_key_last4` is returned).
  - Missing → amber `⚠ No API key — scoring is paused`.
- When missing, emphasise the setup steps (already present) and make "Add key" the primary action.
- After `saveKey` / `deleteKey`, re-fetch `/user/me` so the pill flips live.
- The current key is still never shown in full — only present/absent + optional last-4.

### Account tab

- Read-only **identity block** at the top, sourced client-side from the Supabase user object (`supabase.auth.getUser()` / session) — no backend change needed for these:
  - **Name** — `user_metadata.full_name ?? user_metadata.name ?? '—'`
  - **Email** — current email
  - **Sign-in method** — `Email` vs `Google` (from `app_metadata.provider` / identities)
  - **Member since** — `created_at` formatted
- Existing change-email / change-password / export / delete controls render below the identity block.

## Files to Touch

- `webapp/backend/routers/user.py`
  - `/me`: add `has_api_key` (bool) to the returned row; optionally `api_key_last4`. Requires selecting/deriving from `gemini_api_key_encrypted` (decrypt only to take last 4, or store/return null when absent).
  - `/cv` PATCH + `/parse-cv`: accept and persist optional `cv_filename` + `cv_source`; return them from `/me`.
- `webapp/frontend/app/settings/page.tsx`
  - Add current-state header blocks to all five tabs per the behaviour above.
  - API Key: status pill driven by `has_api_key`; refresh after save/delete.
  - Account: identity block from `supabase.auth.getUser()`.
  - CV: filename/source display + char count + "Download as .txt".
  - Filters: active-filters summary + "None set" placeholders.
- **Optional migration** (only if `cv_filename` / `cv_source` are added): add `cv_filename text` and `cv_source text` columns to the `users` table in Supabase. If the schema change is undesirable, ship CV tab with char-count + download only and skip filename persistence — the rest of the task is unaffected.

## Notes / relationship to other tasks

- The P7 epic `WEBAPP_APP_SHELL_ACCOUNT` covers global nav, sign-out, and auth recovery. Showing current identity *inside the Settings Account tab* is distinct and smaller; this task does not build the shell or sign-out — it only surfaces name/email/provider read-only.
- `has_api_key` from `/me` is reusable later by a getting-started checklist (P7) and onboarding key-test (P7).

## How to QA

1. **API key present:** with a key saved, open Settings → API Key — confirm green `✓ Gemini key configured` pill (and masked `AIza••••1234` if last-4 enabled).
2. **API key missing:** delete the key — confirm pill flips to amber `⚠ No API key — scoring is paused` without a page reload.
3. **Account identity:** open Account tab — confirm your name (or `—`), current email, sign-in method, and member-since date all display read-only above the change controls.
4. **Account email reflects change:** change email, confirm the identity block updates to the new address.
5. **CV file/text:** upload a PDF named `resume.pdf` — confirm header shows `Uploaded resume.pdf · <date>` and a char/word count; click "Download as .txt" and confirm the stored text downloads.
6. **CV pasted:** paste text and save — confirm header shows `Pasted text · <date>`.
7. **Filters visibility:** with some filters set, confirm the "Active filters" summary counts match; clear a category and confirm it shows `None set` rather than an empty box; reload the page and confirm all filters persist.
8. **Profile framing:** with a profile saved, confirm header shows `Profile saved · v{n}`; clear it and confirm `No profile yet` + AI-prompt CTA.
