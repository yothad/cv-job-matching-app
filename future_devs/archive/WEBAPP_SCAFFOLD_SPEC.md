# Spec: webapp_scaffold

**Slug:** webapp_scaffold  
**Epic:** Web App v1  
**Effort:** M  
**Depends on:** —

---

## Goal

Create the complete project scaffold for the CareerWatch web app. This is Wave 1 — everything else builds on top of it.

---

## Directory structure to create

```
webapp/
├── frontend/          # Next.js 14 App Router project
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx           # redirects to /landing or /digest
│   │   ├── (auth)/
│   │   │   └── auth/
│   │   │       └── page.tsx   # placeholder
│   │   ├── digest/
│   │   │   └── page.tsx       # placeholder
│   │   ├── onboarding/
│   │   │   └── page.tsx       # placeholder
│   │   └── settings/
│   │       └── page.tsx       # placeholder
│   ├── components/
│   │   └── ui/                # shadcn/ui components (button, card, input, label, textarea, tabs, badge, slider)
│   ├── lib/
│   │   ├── supabaseClient.ts  # createClient() from @supabase/supabase-js
│   │   └── utils.ts           # cn() from shadcn
│   ├── public/
│   ├── package.json
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── next.config.mjs
│   └── .env.local.example     # NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
│
├── backend/           # FastAPI project
│   ├── main.py        # FastAPI app entrypoint
│   ├── routers/
│   │   └── __init__.py
│   ├── models/
│   │   └── __init__.py
│   ├── db/
│   │   └── supabase_client.py  # supabase-py client init
│   ├── pyproject.toml          # fastapi, uvicorn, supabase, cryptography, httpx, python-dotenv, google-genai
│   └── .env.example            # SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, FERNET_KEY
│
└── supabase/
    └── migrations/
        └── 001_initial_schema.sql   # full schema (see below)
```

---

## Supabase schema (001_initial_schema.sql)

```sql
-- users table
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  email text unique not null,
  password_hash text,
  created_at timestamptz default now(),
  gemini_api_key_encrypted text,
  profile_md text,
  cv_text text,
  scoring_runs_this_week int default 0,
  last_week_reset date default current_date
);

-- score_configs table
create table if not exists score_configs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  location_terms text[] default '{}',
  skip_title_terms text[] default '{}',
  keep_title_terms text[] default '{}',
  skip_companies text[] default '{}',
  skip_industries text[] default '{}',
  lead_title_terms text[] default '{}',
  cv_lead_path text,
  cv_default_path text,
  updated_at timestamptz default now()
);

-- scored_jobs table
create table if not exists scored_jobs (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  apply_url text not null,
  company text,
  title text,
  location text,
  score int,
  reasoning text,
  flags text[] default '{}',
  scored_at timestamptz default now(),
  applied boolean default false,
  unique (user_id, apply_url)
);

-- row-level security
alter table users enable row level security;
alter table score_configs enable row level security;
alter table scored_jobs enable row level security;

create policy "users can read own row" on users for select using (auth.uid() = id);
create policy "users can update own row" on users for update using (auth.uid() = id);
create policy "users can read own score_config" on score_configs for all using (auth.uid() = user_id);
create policy "users can read own scored_jobs" on scored_jobs for all using (auth.uid() = user_id);
```

---

## Frontend requirements

1. Init Next.js 14 with App Router, TypeScript, Tailwind CSS:
   ```
   npx create-next-app@14 frontend --typescript --tailwind --app --no-src-dir --import-alias "@/*"
   ```
2. Install shadcn/ui and initialize:
   ```
   npx shadcn-ui@latest init
   ```
3. Add these shadcn components: `button card input label textarea tabs badge slider`
4. Install Supabase client:
   ```
   npm install @supabase/supabase-js @supabase/auth-helpers-nextjs
   ```
5. Create `lib/supabaseClient.ts` using `createClient` from `@supabase/supabase-js`
6. Stub out all 4 route files (auth, digest, onboarding, settings) as placeholder pages that render a single `<h1>` with the page name

## Backend requirements

1. Create `backend/pyproject.toml` with dependencies:
   - `fastapi>=0.110`, `uvicorn[standard]>=0.29`, `supabase>=2.0`, `cryptography>=42`, `httpx>=0.27`, `python-dotenv>=1.0`, `google-genai>=0.7`
2. Create `backend/main.py`:
   ```python
   from fastapi import FastAPI
   from fastapi.middleware.cors import CORSMiddleware

   app = FastAPI(title="CareerWatch API")

   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:3000"],
       allow_credentials=True,
       allow_methods=["*"],
       allow_headers=["*"],
   )

   @app.get("/health")
   def health():
       return {"status": "ok"}
   ```
3. Create `backend/db/supabase_client.py` that initializes a supabase-py client from env vars

---

## Touches

- `webapp/` (new directory tree — all files listed above)
- `ROADMAP.md` (status: not-started → in-progress during start, in-progress → completed after implementation)

---

## Exit gate

```bash
# Frontend builds without errors
cd webapp/frontend && npm install && npm run build

# Backend imports without errors
cd webapp/backend && uv run python -c "from main import app; print('OK')"

# Project-level tests still pass
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
