'use client'

import Link from 'next/link'
import { useEffect, useRef, useState } from 'react'
import { JobCard, type Job } from '@/app/components/JobCard'
import { ThemeToggle } from '@/app/components/ThemeToggle'

const FAQ_ITEMS = [
  {
    q: 'How often are jobs updated?',
    a: 'New postings are pulled straight from each company\'s ATS twice a week, on Monday and Thursday mornings (UTC). Each fresh batch is then scored automatically with your key, and you can also start a scoring run from your digest up to twice a week.',
  },
  {
    q: 'Which companies are tracked?',
    a: 'Over 100 Israeli cyber, fraud and fintech companies: the portfolios of VCs like YL Ventures, Team8, Glilot and Cyberstarts, plus established players such as Palo Alto Networks, CrowdStrike and Wiz. Coverage is Israel-first. Global roles at these companies may show up, but they are not the target.',
  },
  {
    q: 'Is it really free?',
    a: 'Yes. CareerWatch is free and open source. You bring your own Google Gemini API key, and its free tier is enough to run scoring.',
  },
  {
    q: 'Do you store my CV or API key?',
    a: 'Both live in your account and nowhere else. The API key is encrypted before it is saved. Your CV and profile go to Gemini for two things: scoring your jobs, and the gap analysis that runs when you open the Gaps page. CareerWatch never logs them, never trains anything on them, and never hands them to anyone else. You can export or delete everything from Settings > Account.',
  },
  {
    q: 'Can I use it if I\'m not a data scientist?',
    a: 'The company list and scoring rubric are tuned for data scientists, ML engineers and security engineers in Israel. In another role or another country you can still use it, but expect thinner coverage and rougher scores.',
  },
  {
    q: 'What\'s the catch?',
    a: 'There is none. It is an open-source side project, built for one person\'s job search and shared as is. You bring your own Gemini key, so the only compute cost is yours, and it is free-tier. No business model, no ads, no upsell.',
  },
]

// Static sample fed to the real JobCard so the landing preview can never
// drift from the digest's actual card. The far-future scored_at is a fixed
// constant chosen so timeAgo() deterministically renders "just now" on both
// the prerender and the client - a past date would drift as real time
// advances and cause a hydration mismatch.
const SAMPLE_JOB: Job = {
  id: 'sample-preview',
  company: 'Cybereason',
  title: 'Lead Data Scientist - Threat Detection',
  location: 'Tel Aviv, Israel',
  score: 8,
  reasoning: 'Strong match - fraud domain, team lead scope, Israel location. Minor gap: role leans endpoint telemetry rather than pure fintech fraud.',
  flags: ['tier1-vc', 'lead-path-implied', 'fraud-domain'],
  scored_at: '2099-01-01T00:00:00Z',
  applied: false,
  apply_url: '/auth',
}

// Fade/slide a section's content in the first time it scrolls into view.
// Reduced-motion users (and environments without IntersectionObserver) get
// an instant, static render.
function Reveal({ children, className = '', delay = 0 }: { children: React.ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (
      typeof IntersectionObserver === 'undefined' ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      setVisible(true)
      return
    }
    const obs = new IntersectionObserver(
      entries => {
        if (entries[0]?.isIntersecting) {
          setVisible(true)
          obs.disconnect()
        }
      },
      { threshold: 0.15, rootMargin: '0px 0px -40px 0px' }
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <div
      ref={ref}
      style={{ transitionDelay: `${delay}ms` }}
      className={`${className} transition-[opacity,transform] duration-700 ease-out motion-reduce:transition-none ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
      }`}
    >
      {children}
    </div>
  )
}

function FaqAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(null)

  return (
    <div className="divide-y divide-border border border-border rounded-xl overflow-hidden bg-background shadow-lg">
      {FAQ_ITEMS.map((item, i) => {
        const open = openIndex === i
        return (
          <div key={i}>
            <button
              className="w-full text-left px-6 py-5 flex justify-between items-center gap-4 hover:bg-surface transition-colors"
              onClick={() => setOpenIndex(open ? null : i)}
              aria-expanded={open}
            >
              <span className={`font-medium transition-colors ${open ? 'text-accent' : 'text-foreground'}`}>{item.q}</span>
              <span
                aria-hidden="true"
                className={`ml-auto flex-shrink-0 text-muted font-mono text-xl leading-none select-none transition-transform duration-300 ease-out motion-reduce:transition-none ${
                  open ? 'rotate-45 text-accent' : ''
                }`}
              >
                +
              </span>
            </button>
            {/* grid-rows 0fr -> 1fr gives a smooth height animation without
                measuring content; motion-reduce collapses it to an instant
                toggle. */}
            <div
              className={`grid transition-[grid-template-rows,opacity] duration-300 ease-out motion-reduce:transition-none ${
                open ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'
              }`}
            >
              <div className="overflow-hidden">
                <div className="px-6 pb-5 text-muted text-sm leading-relaxed">
                  {item.a}
                </div>
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Hero mount + job-card mount animations, both gated behind
          prefers-reduced-motion: no-preference. cwCardIn matches the digest
          page's definition so the shared JobCard animates identically here.
          cwDrift is the hero's slow signal-glow breathing. */}
      <style>{`
        @keyframes cwCardIn {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cwRise {
          from { opacity: 0; transform: translateY(14px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes cwDrift {
          0%, 100% { transform: translate(-50%, 0) scale(1); }
          50% { transform: translate(-44%, 5%) scale(1.08); }
        }
        @media (prefers-reduced-motion: no-preference) {
          .cw-card-in { animation: cwCardIn 0.3s ease-out backwards; }
          .cw-rise { animation: cwRise 0.7s cubic-bezier(0.22, 1, 0.36, 1) backwards; }
          .cw-drift { animation: cwDrift 14s ease-in-out infinite; }
        }
      `}</style>

      {/* Top bar - wordmark + theme toggle */}
      <header className="absolute top-0 inset-x-0 z-10 flex items-center justify-between px-5 sm:px-8 py-4">
        <span className="font-display text-xl tracking-tight select-none">
          Career<em className="not-italic font-display italic text-accent">Watch</em>
        </span>
        <ThemeToggle />
      </header>

      {/* Hero */}
      <main className="relative flex-1 flex flex-col items-center justify-center px-4 text-center py-28 sm:py-36 overflow-hidden">
        {/* Signal backdrop: instrument grid + drifting amber glows + grain,
            purely decorative */}
        <div aria-hidden="true" className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 cw-grid [mask-image:radial-gradient(ellipse_75%_70%_at_50%_35%,black,transparent)]" />
          <div className="cw-drift absolute left-1/2 top-[-16rem] w-[56rem] h-[38rem] rounded-full bg-accent/[0.13] blur-3xl" />
          <div className="absolute left-[12%] bottom-[-10rem] w-[30rem] h-[24rem] rounded-full bg-accent/[0.05] blur-3xl" />
          <div className="absolute inset-0 cw-grain opacity-[0.06]" />
          <div className="absolute inset-x-0 bottom-0 h-px bg-gradient-to-r from-transparent via-accent/30 to-transparent" />
        </div>

        <h1 className="cw-rise relative font-display font-normal text-6xl sm:text-7xl md:text-8xl mb-6 tracking-tight leading-none">
          Career<em className="italic text-accent">Watch</em>
        </h1>
        <p className="cw-rise relative text-xl sm:text-2xl text-foreground/85 mb-3 max-w-xl leading-snug" style={{ animationDelay: '80ms' }}>
          The right roles, found for you. AI-scored job matching for tech professionals in Israel.
        </p>
        <p className="cw-rise relative text-base text-muted mb-10 max-w-xl" style={{ animationDelay: '160ms' }}>
          Tracks 100+ Israeli cyber, fraud and fintech companies and scores every open role against your profile, so you read only what fits.
        </p>
        <div className="cw-rise relative flex gap-4 flex-wrap justify-center" style={{ animationDelay: '240ms' }}>
          <Link
            href="/auth"
            className="px-6 py-3 bg-accent hover:bg-accent-hover text-accent-foreground rounded-lg font-semibold shadow-lg shadow-accent/25 hover:shadow-accent/35 transition-[background-color,box-shadow,transform] motion-safe:hover:-translate-y-0.5"
          >
            Get started free
          </Link>
          <a
            href="https://github.com/Omer-Hedvat/careers-watch"
            target="_blank"
            rel="noopener noreferrer"
            className="px-6 py-3 bg-surface hover:bg-surface-raised border border-border-subtle rounded-lg font-semibold transition-[background-color,transform] motion-safe:hover:-translate-y-0.5"
          >
            View on GitHub
          </a>
        </div>
      </main>

      {/* How it works */}
      <section className="py-20 sm:py-24 px-4 bg-surface border-y border-border">
        <div className="max-w-4xl mx-auto">
          <Reveal>
            <h2 className="font-display text-4xl sm:text-5xl text-center tracking-tight mb-14">How it works</h2>
          </Reveal>
          <div className="relative grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-8">
            {/* Hairline connecting the three steps on desktop */}
            <div aria-hidden="true" className="hidden md:block absolute top-6 left-[16%] right-[16%] h-px bg-gradient-to-r from-transparent via-border-subtle to-transparent" />
            {[
              {
                n: '01',
                title: 'Set up your profile',
                body: 'Tell CareerWatch what you want and what you will not accept. An AI assistant helps you write it in minutes.',
              },
              {
                n: '02',
                title: 'We watch the market',
                body: 'Twice a week, CareerWatch pulls every open position straight from the ATS of 100+ Israeli cyber, fraud and fintech companies.',
              },
              {
                n: '03',
                title: 'You get a ranked digest',
                body: 'Every job is scored 0-10 against your profile, with a one-line reason. You read only what fits.',
              },
            ].map((step, i) => (
              <Reveal key={step.n} delay={i * 120}>
                <div className="relative flex flex-col items-center text-center">
                  <div className="w-12 h-12 rounded-lg bg-background border border-accent/40 text-accent font-mono font-medium text-sm flex items-center justify-center mb-5 shadow-lg shadow-accent/10">
                    {step.n}
                  </div>
                  <h3 className="font-semibold text-lg mb-2">{step.title}</h3>
                  <p className="text-muted text-sm leading-relaxed max-w-[17rem]">{step.body}</p>
                </div>
              </Reveal>
            ))}
          </div>
        </div>
      </section>

      {/* Bring your own key */}
      <section className="py-16 sm:py-20 px-4 bg-background">
        <Reveal className="max-w-2xl mx-auto">
          <div className="relative text-center bg-surface border border-border rounded-2xl px-6 py-10 sm:px-10 shadow-lg overflow-hidden">
            <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/40 to-transparent" />
            <h2 className="font-display text-3xl sm:text-4xl tracking-tight mb-4">Bring your own free AI key</h2>
            <p className="text-muted text-sm leading-relaxed mb-3">
              Scoring runs on Google Gemini, whose free tier covers everything CareerWatch does.
              During onboarding you paste your own API key. It is encrypted, kept in your account, and used for two things: scoring jobs for you, and the gap analysis on the Gaps page.
            </p>
            <p className="text-muted text-sm leading-relaxed">
              Your CV, your key, your quota. CareerWatch never trains anything on your data.
            </p>
            <div className="mt-6">
              <a
                href="https://aistudio.google.com/app/apikey"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:text-accent-hover text-sm underline underline-offset-2 transition-colors"
              >
                Get a free Gemini API key at Google AI Studio
              </a>
            </div>
          </div>
        </Reveal>
      </section>

      {/* Digest preview - renders the real JobCard with static sample data,
          so the preview and the digest can never drift apart. */}
      <section className="py-20 sm:py-24 px-4 bg-surface border-y border-border">
        <div className="max-w-2xl mx-auto">
          <Reveal>
            <h2 className="font-display text-4xl sm:text-5xl text-center tracking-tight mb-4">What your digest looks like</h2>
            <p className="text-muted text-center text-sm mb-10">The real digest card, with sample data. Yours is built around your profile.</p>
          </Reveal>
          <Reveal delay={120}>
            <div className="rounded-2xl border border-border bg-background shadow-2xl shadow-black/25 overflow-hidden">
              {/* Decorative app-window chrome */}
              <div aria-hidden="true" className="flex items-center gap-1.5 px-4 py-3 border-b border-border bg-surface/60">
                <span className="w-2.5 h-2.5 rounded-full bg-surface-raised" />
                <span className="w-2.5 h-2.5 rounded-full bg-surface-raised" />
                <span className="w-2.5 h-2.5 rounded-full bg-accent/50" />
              </div>
              <div className="p-4 sm:p-6">
                <JobCard job={SAMPLE_JOB} onToggleApplied={() => {}} currentProfileVersion={1} />
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* Who it's for */}
      <section className="py-16 sm:py-20 px-4 bg-background">
        <Reveal className="max-w-2xl mx-auto text-center">
          <h2 className="font-display text-3xl sm:text-4xl tracking-tight mb-6">Who it is for</h2>
          <p className="text-muted text-sm leading-relaxed mb-4">
            CareerWatch is for senior technical job seekers in Israel: data scientists, ML engineers, applied researchers, and security or fraud engineers who want signal, not volume.
          </p>
          <p className="text-muted text-sm leading-relaxed">
            The company list and scoring rubric are tuned for the Israeli cyber, fraud and fintech ecosystem.
            If you are outside Israel or hunting in other domains you can still use it, but coverage and score accuracy will be lower.
            Companies outside Israel are out of scope for now.
          </p>
        </Reveal>
      </section>

      {/* FAQ */}
      <section className="py-20 sm:py-24 px-4 bg-surface border-t border-border">
        <div className="max-w-2xl mx-auto">
          <Reveal>
            <h2 className="font-display text-4xl sm:text-5xl text-center tracking-tight mb-10">Frequently asked questions</h2>
          </Reveal>
          <Reveal delay={120}>
            <FaqAccordion />
          </Reveal>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-8 px-4 border-t border-border bg-background text-center text-subtle text-sm">
        CareerWatch &middot; Built by Omer Hedvat &middot;{' '}
        <a href="https://github.com/Omer-Hedvat/careers-watch" target="_blank" rel="noopener noreferrer" className="hover:text-foreground transition-colors">
          GitHub
        </a>
      </footer>
    </div>
  )
}
