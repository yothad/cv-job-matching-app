# Spec: webapp_auth

**Slug:** webapp_auth  
**Epic:** Web App v1  
**Effort:** S  
**Depends on:** webapp_scaffold ✅

---

## Goal

Wire up Supabase Auth for email/password sign-up and log-in. Replace the `/auth` stub page with a real form. Add a middleware guard so unauthenticated users are redirected to `/auth`.

---

## What Supabase Auth provides (don't re-implement)

- Email/password registration + login via `supabase.auth.signUp` / `signInWithPassword`
- JWT session management and refresh
- Google OAuth via `supabase.auth.signInWithOAuth` (requires Google credentials configured in Supabase dashboard — out of scope here, just wire the button)
- `supabase.auth.getSession()` / `onAuthStateChange` for session reads

---

## Files to create / modify

### `webapp/frontend/app/auth/page.tsx`

Replace the `<h1>Auth</h1>` stub with a real auth form:

- Two tabs: **Log in** | **Sign up**
- Email field + password field (masked)
- Submit button — calls Supabase auth
- "Continue with Google" button — calls `signInWithOAuth({ provider: 'google' })`
- Error message shown inline if auth fails
- On success: redirect to `/onboarding` (new user) or `/digest` (returning user)
  - Detect new user: check if `profile_md` is null in `users` table after sign-in
- No styling beyond Tailwind utilities; clean, minimal

Use `@supabase/supabase-js` client from `lib/supabaseClient.ts`.

**Component structure:**
```tsx
'use client'
// state: tab ('login' | 'signup'), email, password, error, loading
// signInWithEmail() — calls supabase.auth.signInWithPassword
// signUpWithEmail() — calls supabase.auth.signUp
// signInWithGoogle() — calls supabase.auth.signInWithOAuth({ provider: 'google', options: { redirectTo: window.location.origin + '/auth/callback' } })
// render: two-tab form
```

### `webapp/frontend/app/auth/callback/route.ts`

OAuth callback handler using `@supabase/auth-helpers-nextjs`:

```ts
import { createRouteHandlerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  if (code) {
    const supabase = createRouteHandlerClient({ cookies })
    await supabase.auth.exchangeCodeForSession(code)
  }
  return NextResponse.redirect(requestUrl.origin + '/digest')
}
```

### `webapp/frontend/middleware.ts`

Protect `/digest`, `/onboarding`, `/settings` — redirect unauthenticated users to `/auth`:

```ts
import { createMiddlewareClient } from '@supabase/auth-helpers-nextjs'
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export async function middleware(req: NextRequest) {
  const res = NextResponse.next()
  const supabase = createMiddlewareClient({ req, res })
  const { data: { session } } = await supabase.auth.getSession()

  const protectedPaths = ['/digest', '/onboarding', '/settings']
  const isProtected = protectedPaths.some(p => req.nextUrl.pathname.startsWith(p))

  if (isProtected && !session) {
    return NextResponse.redirect(new URL('/auth', req.url))
  }
  return res
}

export const config = {
  matcher: ['/digest/:path*', '/onboarding/:path*', '/settings/:path*'],
}
```

### `webapp/frontend/app/page.tsx`

Update root redirect: authenticated → `/digest`, unauthenticated → `/auth`. Since this runs server-side, use a server component that reads the session:

```tsx
import { createServerComponentClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

export default async function Home() {
  const supabase = createServerComponentClient({ cookies })
  const { data: { session } } = await supabase.auth.getSession()
  redirect(session ? '/digest' : '/auth')
}
```

---

## Dependencies to add to frontend package.json

Add to `dependencies`:
```json
"@supabase/auth-helpers-nextjs": "^0.10.0"
```
(Already listed in package.json from scaffold — confirm it's there, no change needed if so.)

---

## Touches

- `webapp/frontend/app/auth/page.tsx` (replace stub)
- `webapp/frontend/app/auth/callback/route.ts` (new)
- `webapp/frontend/middleware.ts` (new)
- `webapp/frontend/app/page.tsx` (update redirect logic)

---

## Exit gate

```bash
# All new files exist
ls C:/repos/cv-job-matching-app/webapp/frontend/app/auth/page.tsx
ls C:/repos/cv-job-matching-app/webapp/frontend/app/auth/callback/route.ts
ls C:/repos/cv-job-matching-app/webapp/frontend/middleware.ts

# TypeScript compiles (no tsc binary available — check for obvious syntax errors via grep)
grep -n "export default" C:/repos/cv-job-matching-app/webapp/frontend/app/auth/page.tsx
grep -n "export async function middleware" C:/repos/cv-job-matching-app/webapp/frontend/middleware.ts

# Python pipeline unaffected
cd C:/repos/cv-job-matching-app && uv run python3 -m pytest tests/ -v
uv run python score.py --dry-run
```
