import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { SCORE_BANDS } from '@/lib/scoreBands'

// Derived from the shared SCORE_BANDS so the numbers/labels here can't drift
// from the digest legend and badge tooltips.
const scoreBandsSummary =
  `Score bands: ${SCORE_BANDS.map(b => `${b.range} - ${b.blurb}`).join(' ')} Jobs scoring below 5 never reach your digest.`

const sections = [
  {
    id: 'how-it-works',
    heading: 'How it works',
    content: [
      'CareerWatch pulls new postings straight from the ATS of each tracked Israeli cyber, fraud and fintech company. When you run a scoring pass, Gemini reads every new posting next to your CV and profile and produces a ranked digest.',
      'Three stages, three cadences: the company list is refreshed weekly (new companies discovered, stale entries re-verified), jobs are collected twice a week (Monday and Thursday), and scoring runs when you click "Score now", up to twice a week. Your Digest always shows the latest scored batch.',
    ],
  },
  {
    id: 'scoring',
    heading: 'How scoring works',
    content: [
      'Gemini scores each job from 0 to 10 for how well it fits your profile and CV. It reads the full job description next to your background, your stated preferences, and every dealbreaker you listed.',
      scoreBandsSummary,
      'Scores are relative to your profile, not absolute. A 7 for you means something different from a 7 for someone with a different background. The more specific your profile, the sharper the scores.',
    ],
  },
  {
    id: 'flags',
    heading: 'What the flags mean',
    content: [
      'Flags are short tags on each scored job that explain why the score landed where it did. "Lead path implied" means the posting hints at a route to a lead role; "Management gap" means it asks for more people-management than your profile shows; "Out of commute range" means the office sits outside the radius you set.',
      'Positive flags reinforce the score. Caution flags name the gap or trade-off. Reading them takes a few seconds and tells you whether a 7 is worth your time today. Hover any flag, or open "What do these tags mean?", for the full list.',
    ],
  },
  {
    id: 'cadence',
    heading: 'Collection cadence and run limits',
    content: [
      'Jobs are collected twice a week, on Monday and Thursday mornings (UTC). Scoring runs up to twice a week per user, which keeps the load on your free Gemini quota small. So a fresh digest can trail the very newest postings by a few days.',
      'Collection runs on our side; there is nothing for you to trigger. Scoring is yours to start: open your Digest and click "Score now" after a collection to score what is new.',
    ],
  },
  {
    id: 'data-privacy',
    heading: 'Data and privacy',
    content: [
      'Your Gemini API key is encrypted before it is stored in Supabase; your CV and profile sit in your account alongside it. None of it goes to any third party except Gemini, and only to score jobs and to run the gap analysis on the Gaps page. CareerWatch does not sell, share, or reuse your data for anything but running your matches.',
      'Your key is used for scoring calls, for the gap analysis that runs when you open the Gaps page, and for the key check you trigger from Settings. A scoring call sends your CV, your profile, and a batch of job descriptions to Gemini and gets scores back; a gap call sends your CV and profile, plus your top-scoring jobs, and gets back where they diverge. Nothing else.',
      'You can export or permanently delete all your data at any time from Settings > Account. Deletion removes your CV, profile, API key, and every stored score.',
    ],
  },
  {
    id: 'improve',
    heading: 'How to improve your results',
    content: [
      'The single highest-leverage change is sharpening your profile. A vague profile produces vague scores. A profile that names your exact target role, lists your dealbreakers, and describes what a 9/10 looks like for you produces scores you can act on.',
      'Concretely: state the seniority you want (e.g. "Team Lead, not IC"), name the domains you want to stay in (e.g. "fraud detection or cloud security ML"), and list at least one or two hard dealbreakers (e.g. "no consulting", "no pure infra roles"). The more the model knows what you will say no to, the better it surfaces the yeses.',
      'Update your profile in Settings > Profile. Changes apply on your next scoring run.',
    ],
  },
]

export default function HelpPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <div className="max-w-2xl mx-auto px-4 py-10">
        {/* Back link */}
        <Link
          href="/digest"
          className="inline-flex items-center gap-1 text-sm text-muted hover:text-foreground mb-8 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" aria-hidden="true" />
          Digest
        </Link>

        {/* Page title */}
        <h1 className="font-display text-4xl tracking-tight text-foreground mb-2">Help & FAQ</h1>
        <p className="text-muted mb-10 text-sm">
          Everything you need to get the most out of CareerWatch.
        </p>

        {/* Quick-jump links */}
        <nav className="mb-10 p-4 bg-surface rounded-xl border border-border">
          <p className="cw-label text-subtle mb-3">Jump to</p>
          <ul className="space-y-1">
            {sections.map(s => (
              <li key={s.id}>
                <a
                  href={`#${s.id}`}
                  className="text-sm text-muted hover:text-accent transition-colors"
                >
                  {s.heading}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        {/* Sections */}
        <div className="space-y-12">
          {sections.map(s => (
            <section key={s.id} id={s.id} className="scroll-mt-20">
              <h2 className="font-display text-2xl text-accent mb-3">{s.heading}</h2>
              <div className="space-y-3">
                {s.content.map((para, i) => (
                  <p key={i} className="text-muted text-sm leading-relaxed">
                    {para}
                  </p>
                ))}
              </div>
            </section>
          ))}
        </div>

        {/* Footer nudge */}
        <div className="mt-16 pt-8 border-t border-border text-center">
          <p className="text-subtle text-sm">
            Still have questions?{' '}
            <a
              href="mailto:omer.hedvat@gmail.com"
              className="text-accent hover:text-accent-hover transition-colors"
            >
              Get in touch
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  )
}
