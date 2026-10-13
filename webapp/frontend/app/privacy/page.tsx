'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { ThemeToggle } from '@/app/components/ThemeToggle'

export default function PrivacyPage() {
  return (
    <div className="relative min-h-screen bg-background py-16 px-4">
      <ThemeToggle className="absolute top-4 right-4" />
      <div className="max-w-2xl mx-auto">
        <Link href="/auth" className="text-muted hover:text-foreground text-sm inline-flex items-center gap-1 mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Back
        </Link>

        <p className="cw-label text-accent mb-2">CareerWatch</p>
        <h1 className="font-display text-4xl sm:text-5xl text-foreground mb-10">Privacy Policy</h1>

        <div className="space-y-6 text-muted text-sm leading-relaxed">
          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">What we store</h2>
            <p>
              CareerWatch stores your email address (for authentication), your CV text or file
              (if you upload one), and your Gemini API key (if you provide one). All data is
              stored in Supabase with encryption at rest.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">How we use your data</h2>
            <p>
              Your CV and API key are used only to score job listings on your behalf and to
              run the gap analysis on the Gaps page. Your CV and profile are sent to the Gemini
              API (using your own key) during scoring runs - including the automatic one after each Monday and Thursday collection - and when you open the Gaps page.
              We do not sell, share, or otherwise transfer your data to any third party
              beyond the Gemini API calls described above.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Data retention</h2>
            <p>
              Your data is retained as long as your account is active. You can delete your
              account at any time from the Settings page, which will permanently remove all
              stored data including your CV and API key.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Export</h2>
            <p>
              You can export your scored jobs at any time from the Settings page. Your CV,
              profile and filters stay visible and editable in Settings.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Cookies and tracking</h2>
            <p>
              CareerWatch uses session cookies only for authentication. We do not use
              analytics trackers or advertising cookies.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Contact</h2>
            <p>
              Questions about your data? Reach out via the email you used to sign up.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
