# Backend Deployment Notes

## Render.com setup

1. Connect repo to Render, select "Blueprint" deployment - it reads `render.yaml`
2. Set env vars in the Render dashboard (marked `sync: false` in render.yaml):
   - `SUPABASE_URL` - from Supabase project settings
   - `SUPABASE_SERVICE_ROLE_KEY` - from Supabase API settings (service_role key, NOT anon)
   - `FERNET_KEY` - generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. No disk needed. Jobs come from the shared Supabase `positions` table, which the
   collect-and-score workflow fills via `scripts/sync_positions.py` (new_jobs.json is
   gitignored and never on Render). `companies.json` is committed and read from the
   repo checkout (`COMPANIES_PATH`).
4. Apply every file in `webapp/supabase/migrations/` (in order) in the Supabase SQL
   editor - the code expects all of them, incl. `008_positions_description.sql`.

## Tests

```bash
cd webapp/backend
uv run --with pytest python -m pytest tests -q
```

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
