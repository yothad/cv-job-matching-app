# Spec: webapp_deploy

**Slug:** webapp_deploy  
**Epic:** Web App v1  
**Effort:** S  
**Depends on:** webapp_scaffold ✅

---

## Goal

Add Render.com deployment configuration so both the FastAPI backend and Next.js frontend can be deployed with a single `render.yaml` blueprint. No actual deploy happens as part of this task — just the config files.

---

## Files to create

### `render.yaml` (repo root)

Render.com [blueprint spec](https://render.com/docs/blueprint-spec).

```yaml
services:
  # FastAPI backend
  - type: web
    name: careerwatch-api
    env: python
    region: oregon
    plan: free
    rootDir: webapp/backend
    buildCommand: pip install uv && uv sync
    startCommand: uv run uvicorn main:app --host 0.0.0.0 --port $PORT
    disk:
      name: data
      mountPath: /data
      sizeGB: 1
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: FERNET_KEY
        sync: false
      - key: JOBS_PATH
        value: /data/new_jobs.json
      - key: COMPANIES_PATH
        value: /data/companies.json

  # Next.js frontend
  - type: web
    name: careerwatch-frontend
    env: node
    region: oregon
    plan: free
    rootDir: webapp/frontend
    buildCommand: npm install && npm run build
    startCommand: npm run start
    envVars:
      - key: NEXT_PUBLIC_SUPABASE_URL
        sync: false
      - key: NEXT_PUBLIC_SUPABASE_ANON_KEY
        sync: false
      - key: NEXT_PUBLIC_API_URL
        sync: false
```

### `webapp/backend/DEPLOY.md`

Deployment runbook (brief):

```markdown
# Backend Deployment Notes

## Render.com setup

1. Connect repo to Render, select "Blueprint" deployment — it reads `render.yaml`
2. Set env vars in the Render dashboard (marked `sync: false` in render.yaml):
   - `SUPABASE_URL` — from Supabase project settings
   - `SUPABASE_SERVICE_ROLE_KEY` — from Supabase API settings (service_role key, NOT anon)
   - `FERNET_KEY` — generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. The persistent disk mounts at `/data`. On first deploy, copy `new_jobs.json` and `companies.json` there.
   GitHub Actions commits these files to the repo; a sync script or manual copy seeds the disk.

## Local development

```bash
cd webapp/backend
cp .env.example .env   # fill in values
uv sync
uv run uvicorn main:app --reload
```

## Fernet key generation

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```
```

### `webapp/frontend/DEPLOY.md`

```markdown
# Frontend Deployment Notes

## Render.com setup

Set these env vars in the Render dashboard:
- `NEXT_PUBLIC_SUPABASE_URL` — from Supabase project settings
- `NEXT_PUBLIC_SUPABASE_ANON_KEY` — from Supabase API settings (anon key)
- `NEXT_PUBLIC_API_URL` — URL of the deployed FastAPI backend (e.g. https://careerwatch-api.onrender.com)

## Local development

```bash
cd webapp/frontend
cp .env.local.example .env.local   # fill in values
npm install
npm run dev
```
```

---

## Notes on persistent disk

Render free tier allows one persistent disk per service. The backend mounts it at `/data`. The GitHub Actions workflow commits `new_jobs.json` to the repo — a separate sync step (out of scope for v1) would copy from repo to disk. For now, manual seeding is acceptable.

---

## Touches

- `render.yaml` (new, repo root)
- `webapp/backend/DEPLOY.md` (new)
- `webapp/frontend/DEPLOY.md` (new)

---

## Exit gate

```bash
# Files exist
ls C:/repos/cv-job-matching-app/render.yaml
ls C:/repos/cv-job-matching-app/webapp/backend/DEPLOY.md
ls C:/repos/cv-job-matching-app/webapp/frontend/DEPLOY.md

# render.yaml is valid YAML
python3 -c "import yaml; yaml.safe_load(open('C:/repos/cv-job-matching-app/render.yaml')); print('valid YAML')"

# Python pipeline unaffected
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
