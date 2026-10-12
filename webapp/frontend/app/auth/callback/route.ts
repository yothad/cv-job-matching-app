import { createRouteHandlerClient } from '@supabase/auth-helpers-nextjs'
import { cookies } from 'next/headers'
import { NextResponse } from 'next/server'

// Where to land after sign-in: /onboarding while setup is incomplete, else
// /digest. Any failure (no session, backend down or cold) falls back to /digest
// so a user is never stranded on an error.
async function landingPath(accessToken: string | undefined): Promise<string> {
  if (!accessToken) return '/digest'
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/user/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    })
    if (!r.ok) return '/digest'
    const d = await r.json()
    return d?.setup?.complete === false ? '/onboarding' : '/digest'
  } catch {
    return '/digest'
  }
}

// Also reached without a ?code after an email/password sign-in, using the
// session already stored in cookies.
export async function GET(request: Request) {
  const requestUrl = new URL(request.url)
  const code = requestUrl.searchParams.get('code')
  const supabase = createRouteHandlerClient({ cookies })
  let path = '/digest'
  try {
    if (code) await supabase.auth.exchangeCodeForSession(code)
    const { data: { session } } = await supabase.auth.getSession()
    path = await landingPath(session?.access_token)
  } catch {
    /* keep /digest - middleware sends a signed-out user to /auth */
  }
  // Behind Render's proxy requestUrl.origin resolves to the internal
  // localhost:10000, so build the redirect from the forwarded public host.
  const forwardedHost = request.headers.get('x-forwarded-host')
  const forwardedProto = request.headers.get('x-forwarded-proto') ?? 'https'
  const origin = forwardedHost ? `${forwardedProto}://${forwardedHost}` : requestUrl.origin
  return NextResponse.redirect(`${origin}${path}`)
}
