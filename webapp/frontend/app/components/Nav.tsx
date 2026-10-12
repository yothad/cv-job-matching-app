'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { Menu, X } from 'lucide-react'
import { supabase } from '@/lib/supabaseClient'
import { clearSwrCache } from '@/lib/swrCache'
import { ThemeToggle } from '@/app/components/ThemeToggle'

const NAV_LINKS = [
  { href: '/digest', label: 'Digest' },
  { href: '/positions', label: 'Positions' },
  { href: '/companies', label: 'Companies' },
  { href: '/gaps', label: 'Gaps' },
  { href: '/settings', label: 'Settings' },
  { href: '/help', label: 'Help' },
]

export default function Nav() {
  const router = useRouter()
  const pathname = usePathname()
  const [email, setEmail] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      setEmail(data.user?.email ?? null)
    })
  }, [])

  async function handleSignOut() {
    await supabase.auth.signOut()
    clearSwrCache()
    router.push('/landing')
  }

  return (
    <header className="border-b border-border bg-background/85 backdrop-blur-md sticky top-0 z-50">
      <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        {/* Brand */}
        <Link href="/digest" className="font-display text-xl tracking-tight text-foreground shrink-0">
          Career<em className="italic text-accent">Watch</em>
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-1 flex-1">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  active
                    ? 'text-accent bg-surface-raised'
                    : 'text-muted hover:text-foreground hover:bg-surface-raised'
                }`}
              >
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Desktop right side */}
        <div className="hidden md:flex items-center gap-3 shrink-0">
          {email && (
            <span className="text-xs text-subtle max-w-[180px] truncate">
              {email}
            </span>
          )}
          <ThemeToggle className="w-8 h-8" />
          <button
            onClick={handleSignOut}
            className="px-3 py-1.5 text-sm text-muted hover:text-foreground border border-subtle hover:border-muted rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            Sign out
          </button>
        </div>

        {/* Mobile hamburger */}
        <div className="md:hidden flex items-center gap-2">
        <ThemeToggle className="w-8 h-8" />
        <button
          className="p-2 text-muted hover:text-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent rounded-md"
          onClick={() => setMenuOpen(o => !o)}
          aria-label="Toggle menu"
          aria-expanded={menuOpen}
        >
          {menuOpen ? (
            <X className="w-5 h-5" aria-hidden="true" />
          ) : (
            <Menu className="w-5 h-5" aria-hidden="true" />
          )}
        </button>
        </div>
      </div>

      {/* Mobile menu */}
      {menuOpen && (
        <div className="md:hidden border-t border-border bg-background px-4 py-3 space-y-1">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname.startsWith(href)
            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`block px-3 py-2 rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent ${
                  active
                    ? 'text-accent bg-surface-raised'
                    : 'text-muted hover:text-foreground hover:bg-surface-raised'
                }`}
              >
                {label}
              </Link>
            )
          })}
          <div className="pt-2 border-t border-border mt-2">
            {email && (
              <p className="text-xs text-subtle px-3 py-1 truncate">Signed in as {email}</p>
            )}
            <button
              onClick={() => { setMenuOpen(false); handleSignOut() }}
              className="w-full text-left px-3 py-2 text-sm text-muted hover:text-foreground rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
            >
              Sign out
            </button>
          </div>
        </div>
      )}
    </header>
  )
}
