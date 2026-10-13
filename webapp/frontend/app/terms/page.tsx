'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { ThemeToggle } from '@/app/components/ThemeToggle'

export default function TermsPage() {
  return (
    <div className="relative min-h-screen bg-background py-16 px-4">
      <ThemeToggle className="absolute top-4 right-4" />
      <div className="max-w-2xl mx-auto">
        <Link href="/auth" className="text-muted hover:text-foreground text-sm inline-flex items-center gap-1 mb-8 transition-colors">
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Back
        </Link>

        <p className="cw-label text-accent mb-2">CareerWatch</p>
        <h1 className="font-display text-4xl sm:text-5xl text-foreground mb-10">Terms of Service</h1>

        <div className="space-y-6 text-muted text-sm leading-relaxed">
          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Personal-use software</h2>
            <p>
              CareerWatch is personal-use software designed to help you track job opportunities.
              It is provided as-is, without warranties of any kind. Use it at your own discretion.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Data you provide</h2>
            <p>
              You may upload your CV and provide a Gemini API key to enable job scoring.
              These are stored securely in our database (Supabase) and are used solely to
              power the features you explicitly invoke - scoring job listings against your
              profile and the gap analysis on the Gaps page. We do not use your CV or API key for any other purpose.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Third-party services</h2>
            <p>
              CareerWatch integrates with Google Gemini (for AI-based job scoring) using the
              API key you supply. Requests to Gemini are made on your behalf and are governed
              by Google&apos;s terms of service. CareerWatch does not store responses beyond
              what is needed to display your digest.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Your rights</h2>
            <p>
              You can export or delete your data at any time from the Settings page.
              Deleting your account removes all stored data including your CV and API key.
            </p>
          </section>

          <section>
            <h2 className="text-foreground font-semibold text-base mb-2">Changes</h2>
            <p>
              These terms may be updated over time. Continued use of CareerWatch after
              changes constitutes acceptance of the updated terms.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
