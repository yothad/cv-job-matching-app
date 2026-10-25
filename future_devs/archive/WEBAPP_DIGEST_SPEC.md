# Spec: webapp_digest

**Slug:** webapp_digest  
**Epic:** Web App v1  
**Effort:** M  
**Depends on:** webapp_onboarding ✅

---

## Goal

Build the main digest view — ranked job cards, "Score now" button, applied toggle, and a collapsible filter sidebar.

---

## File: `webapp/frontend/app/digest/page.tsx`

Replace the `<h1>Digest</h1>` stub with the full digest view.

Client component (`'use client'`). Fetches scored jobs from the backend on mount. Polling is not required — a manual refresh button is enough.

### Data fetching

```ts
// On mount, fetch /jobs (GET) to load scored_jobs for this user
const [jobs, setJobs] = useState<Job[]>([])
const [loading, setLoading] = useState(true)
const [scoring, setScoring] = useState(false)
const [runsUsed, setRunsUsed] = useState(0)
const [minScore, setMinScore] = useState(5)
const [search, setSearch] = useState('')
const [showApplied, setShowApplied] = useState(false)
```

### Types

```ts
type Job = {
  id: string
  company: string
  title: string
  location: string
  score: number
  reasoning: string
  flags: string[]
  scored_at: string
  applied: boolean
  apply_url: string
}
```

### Backend endpoints needed (add to backend)

**GET /jobs** — returns all scored_jobs for the authenticated user, ordered by score desc

**POST /jobs/{id}/applied** — toggles the `applied` field for a job

**GET /user/me** — returns `{ scoring_runs_this_week: number, last_week_reset: string }`

These three are simple CRUD endpoints — add them to `webapp/backend/routers/jobs.py`.

### Header bar

```
CareerWatch                    [Settings ⚙]
Last scored: <relative time>   Score now [2 of 2 used] or [Score now →]
```

- "Score now" calls POST /score/, then refreshes jobs list
- Button disabled + shows "2 of 2 runs used" when runsUsed >= 2
- Settings icon is a Link to /settings

### Job cards

Sort: score desc, then scored_at desc.

```
┌─────────────────────────────────────────────────────┐
│ [9]  Cato Networks — Research Team Lead              │
│      Tel Aviv  •  scored 2h ago                      │
│      "Strong fit for security ML lead..."            │
│      [threat-detection] [team-lead]                  │
│                          [Apply →]  [Mark applied ✓] │
└─────────────────────────────────────────────────────┘
```

Score badge colors:
- 9-10: `bg-green-600`
- 7-8: `bg-blue-600`
- 5-6: `bg-gray-600`
- below 5: don't show (filtered by minScore default of 5)

"Apply →" opens apply_url in new tab.

"Mark applied" / "Undo applied" calls POST /jobs/{id}/applied. Applied cards become visually dimmed (`opacity-50`).

Applied jobs: collapsed into a `"Show X applied"` toggle at the bottom. When `showApplied` is true, they render after active jobs.

### Filter sidebar (collapsible, right side or inline on mobile)

```
Score: show ≥ [slider 0-10, default 5]
Search: [text input — filters by company or title client-side]
```

No server round-trip for filters — filter client-side over the jobs array.

### Empty states

- No jobs at all: "No jobs scored yet. Click Score now to run your first scoring."
- All jobs filtered out: "No jobs match your current filters."

### Full component skeleton

```tsx
'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { supabase } from '@/lib/supabaseClient'

// ... types and helpers ...

export default function DigestPage() {
  // ... state ...

  useEffect(() => {
    loadJobs()
    loadUser()
  }, [])

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token
  }

  async function loadJobs() {
    const token = await getToken()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await res.json()
    setJobs(data)
    setLoading(false)
  }

  async function loadUser() {
    const token = await getToken()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/user/me`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await res.json()
    setRunsUsed(data.scoring_runs_this_week ?? 0)
  }

  async function triggerScoring() {
    setScoring(true)
    const token = await getToken()
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/score/`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    await loadJobs()
    await loadUser()
    setScoring(false)
  }

  async function toggleApplied(job: Job) {
    const token = await getToken()
    await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${job.id}/applied`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    setJobs(prev => prev.map(j => j.id === job.id ? { ...j, applied: !j.applied } : j))
  }

  const filtered = jobs
    .filter(j => j.score >= minScore)
    .filter(j => !search || j.company.toLowerCase().includes(search.toLowerCase()) || j.title.toLowerCase().includes(search.toLowerCase()))

  const active = filtered.filter(j => !j.applied)
  const applied = filtered.filter(j => j.applied)

  // render header + filter bar + cards
  return ( /* ... JSX ... */ )
}
```

Fill in the full JSX — header bar, filter controls, job cards, applied section. Keep it clean and functional; no need for animations.

---

## Backend: `webapp/backend/routers/jobs.py`

```python
from fastapi import APIRouter, HTTPException, Header
from db.supabase_client import supabase

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _get_user(authorization: str) -> str:
    token = authorization.removeprefix("Bearer ")
    resp = supabase.auth.get_user(token)
    if not resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return resp.user.id


@router.get("/")
def list_jobs(authorization: str = Header(...)):
    user_id = _get_user(authorization)
    rows = (
        supabase.table("scored_jobs")
        .select("*")
        .eq("user_id", user_id)
        .order("score", desc=True)
        .order("scored_at", desc=True)
        .execute()
        .data
    )
    return rows


@router.post("/{job_id}/applied")
def toggle_applied(job_id: str, authorization: str = Header(...)):
    user_id = _get_user(authorization)
    row = (
        supabase.table("scored_jobs")
        .select("applied")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .maybe_single()
        .execute()
        .data
    )
    if not row:
        raise HTTPException(status_code=404, detail="Job not found")
    new_val = not row["applied"]
    supabase.table("scored_jobs").update({"applied": new_val}).eq("id", job_id).execute()
    return {"applied": new_val}
```

Also add GET /user/me to `webapp/backend/routers/user.py`:

```python
@router.get("/me")
def get_me(authorization: str = Header(...)):
    token = authorization.removeprefix("Bearer ")
    auth_resp = supabase.auth.get_user(token)
    if not auth_resp.user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    user_id = auth_resp.user.id
    row = supabase.table("users").select("scoring_runs_this_week,last_week_reset").eq("id", user_id).maybe_single().execute().data
    return row or {}
```

Register jobs router in main.py:

```python
from routers.jobs import router as jobs_router
app.include_router(jobs_router)
```

---

## Touches

- `webapp/frontend/app/digest/page.tsx` (replace stub)
- `webapp/backend/routers/jobs.py` (new)
- `webapp/backend/routers/user.py` (add GET /user/me)
- `webapp/backend/main.py` (add jobs router)

---

## Exit gate

```bash
ls C:/repos/cv-job-matching-app/webapp/frontend/app/digest/page.tsx
ls C:/repos/cv-job-matching-app/webapp/backend/routers/jobs.py
grep "use client" C:/repos/cv-job-matching-app/webapp/frontend/app/digest/page.tsx
grep "jobs_router" C:/repos/cv-job-matching-app/webapp/backend/main.py
python3 -c "import ast; ast.parse(open('C:/repos/cv-job-matching-app/webapp/backend/routers/jobs.py').read()); print('syntax OK')"
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
