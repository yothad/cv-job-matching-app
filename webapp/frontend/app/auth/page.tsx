'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeft, Mail } from 'lucide-react'
import { supabase } from '@/lib/supabaseClient'
import { ThemeToggle } from '@/app/components/ThemeToggle'

type View = 'login' | 'signup' | 'forgot' | 'check-email'

// Shared page chrome: instrument-grid backdrop + amber signal glow behind a
// single centered card, so every auth view feels like one surface.
function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen flex items-center justify-center bg-background px-4 py-12 overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 cw-grid [mask-image:radial-gradient(ellipse_60%_60%_at_50%_40%,black,transparent)]" />
        <div className="absolute left-1/2 top-[-16rem] -translate-x-1/2 w-[46rem] h-[32rem] rounded-full bg-accent/10 blur-3xl" />
        <div className="absolute inset-0 cw-grain opacity-[0.05]" />
      </div>
      <ThemeToggle className="absolute top-4 right-4 z-10" />
      <div className="relative w-full max-w-md bg-surface border border-border rounded-2xl p-8 shadow-2xl shadow-black/20">
        {children}
      </div>
    </div>
  )
}

export default function AuthPage() {
  const router = useRouter()
  const [view, setView] = useState<View>('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function signInWithEmail() {
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) { setError(error.message); setLoading(false); return }
    // Full navigation (route handler): lands on /onboarding while setup is incomplete, else /digest.
    window.location.assign('/auth/callback')
  }

  async function signUpWithEmail() {
    setLoading(true)
    setError('')
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) { setError(error.message); setLoading(false); return }
    if (!data.session) {
      // Email confirmation required
      setLoading(false)
      setView('check-email')
      return
    }
    router.push('/onboarding')
  }

  async function sendResetEmail() {
    setLoading(true)
    setError('')
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + '/auth/reset',
    })
    if (error) { setError(error.message); setLoading(false); return }
    setLoading(false)
    setView('check-email')
  }

  async function signInWithGoogle() {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.origin + '/auth/callback' },
    })
  }

  const inputClass =
    'w-full px-3.5 py-2.5 bg-surface-raised text-foreground placeholder:text-subtle rounded-lg border border-border focus:outline-none focus:border-accent transition-colors'

  const primaryBtnClass =
    'w-full py-2.5 bg-accent hover:bg-accent-hover text-accent-foreground rounded-lg font-semibold disabled:opacity-50 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface'

  // --- Check-email confirmation screen ---
  if (view === 'check-email') {
    return (
      <AuthShell>
        <div className="text-center">
          <div className="w-14 h-14 mx-auto mb-5 rounded-xl bg-accent/10 border border-accent/25 flex items-center justify-center">
            <Mail className="w-6 h-6 text-accent" aria-hidden="true" />
          </div>
          <h1 className="font-display text-3xl text-foreground mb-3">Check your email</h1>
          <p className="text-muted text-sm mb-6 leading-relaxed">
            We sent a link to <span className="text-foreground font-medium">{email}</span>.
            Click it to confirm your account and continue.
          </p>
          <button
            onClick={() => { setView('login'); setError('') }}
            className="text-accent hover:text-accent-hover text-sm underline underline-offset-2 transition-colors"
          >
            Back to log in
          </button>
        </div>
      </AuthShell>
    )
  }

  // --- Forgot password screen ---
  if (view === 'forgot') {
    return (
      <AuthShell>
        <Link href="/" className="text-muted hover:text-foreground text-sm inline-flex items-center gap-1 mb-6 transition-colors">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Back to landing
        </Link>
        <h1 className="font-display text-3xl text-foreground mb-2">Reset password</h1>
        <p className="text-muted text-sm mb-6">
          Enter your email and we&apos;ll send you a reset link.
        </p>
        <div className="space-y-4">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className={inputClass}
          />
          {error && <p className="text-danger text-sm">{error}</p>}
          <button onClick={sendResetEmail} disabled={loading} className={primaryBtnClass}>
            {loading ? 'Sending...' : 'Send reset email'}
          </button>
          <button
            onClick={() => { setView('login'); setError('') }}
            className="w-full py-2 text-muted hover:text-foreground text-sm transition-colors"
          >
            Back to log in
          </button>
        </div>
      </AuthShell>
    )
  }

  // --- Main login / signup screen ---
  return (
    <AuthShell>
      <Link href="/" className="text-muted hover:text-foreground text-sm inline-flex items-center gap-1 mb-6 transition-colors">
        <ArrowLeft className="w-4 h-4" aria-hidden="true" />
        Back to landing
      </Link>

      <p className="cw-label text-accent mb-1">Job market terminal</p>
      <h1 className="font-display text-4xl text-foreground mb-6">CareerWatch</h1>

      <div className="flex mb-6 border-b border-border">
        {(['login', 'signup'] as const).map(t => (
          <button
            key={t}
            onClick={() => { setView(t); setError('') }}
            className={`px-4 py-2 text-sm font-medium capitalize -mb-px transition-colors ${
              view === t
                ? 'text-foreground border-b-2 border-accent'
                : 'text-muted hover:text-foreground border-b-2 border-transparent'
            }`}
          >
            {t === 'login' ? 'Log in' : 'Sign up'}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className={inputClass}
        />
        <div>
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className={inputClass}
          />
          {view === 'signup' && (
            <p className="text-subtle text-xs mt-1 ml-1">At least 6 characters</p>
          )}
        </div>

        {view === 'login' && (
          <div className="text-right">
            <button
              onClick={() => { setView('forgot'); setError('') }}
              className="text-muted hover:text-accent text-sm transition-colors"
            >
              Forgot password?
            </button>
          </div>
        )}

        {error && (
          <div className="bg-danger/10 border border-danger/30 rounded-lg px-3 py-2">
            <p className="text-danger text-sm">{error}</p>
          </div>
        )}

        <button
          onClick={view === 'login' ? signInWithEmail : signUpWithEmail}
          disabled={loading}
          className={primaryBtnClass}
        >
          {loading ? 'Loading...' : view === 'login' ? 'Log in' : 'Sign up'}
        </button>

        <div className="flex items-center gap-3 my-2">
          <div className="flex-1 h-px bg-border" />
          <span className="cw-label text-subtle">or</span>
          <div className="flex-1 h-px bg-border" />
        </div>

        <button
          onClick={signInWithGoogle}
          className="w-full py-2.5 bg-surface-raised hover:bg-border-subtle/40 border border-border text-foreground rounded-lg font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
        >
          Continue with Google
        </button>

        {view === 'signup' && (
          <p className="text-subtle text-xs text-center mt-4">
            By signing up you agree to our{' '}
            <Link href="/terms" className="text-accent hover:text-accent-hover underline transition-colors">
              Terms
            </Link>{' '}
            and{' '}
            <Link href="/privacy" className="text-accent hover:text-accent-hover underline transition-colors">
              Privacy Policy
            </Link>
            .
          </p>
        )}
      </div>
    </AuthShell>
  )
}
