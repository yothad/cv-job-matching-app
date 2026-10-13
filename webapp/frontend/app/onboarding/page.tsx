'use client'

import { useState, useEffect } from 'react'
import { Check, ChevronDown, ChevronRight } from 'lucide-react'
import { supabase } from '@/lib/supabaseClient'
import { ACCEPT_ATTR, extractUploadText } from '@/lib/uploadFormats'
import { ThemeToggle } from '@/app/components/ThemeToggle'

const EXAMPLE_PROFILE = `# Candidate Profile

## Who I am, in one paragraph
Senior data scientist with 8 years experience, specialized in adversarial ML and anomaly detection. Background spans fraud detection at a fintech and threat hunting at a cybersecurity company. I prefer applied roles over pure research, and I thrive in small teams where I can own models end to end.

## What I'm looking for, in priority order
1. Team Lead DS or Lead Data Scientist - managing 2-4 people while staying hands-on
2. Senior DS / Senior ML Engineer in cyber or fraud domain
3. Staff-level applied science roles at late-stage startups

## Location
Tel Aviv metro area. Commute up to 60 minutes. Open to hybrid (2-3 days office). Not open to relocation or fully remote.

## Strong fit signals (boost the score)
- Fraud detection, anomaly detection, or threat intelligence ML
- Team lead scope or technical lead mentioned in the JD
- Stack: Python, XGBoost/LightGBM, Spark, Kafka, real-time inference
- Company stage: Series B-D, 50-300 people
- Domain: cybersecurity, fintech, fraud-as-a-service

## Weak fit / skip (drop the score)
- Pure MLOps or platform engineering (no modeling)
- Consumer/e-commerce without fraud angle
- Roles requiring US/EU relocation
- Big tech (FAANG) - culture mismatch

## Dealbreakers (score = 0, do not surface)
- Gaming, adtech, gambling, crypto
- Pure data engineering or BI roles
- Companies with active legal/regulatory issues

## Notes for the matcher
- I have informal team lead experience (mentored 2 juniors) but no formal "manager" title - treat partial leadership as a positive signal, not a gap
- Titles like "ML Engineer" are fine if the JD shows model ownership; titles like "Data Scientist" are fine if there is a leadership component
- Hebrew job descriptions are fine - score them as-is

## Scoring rubric for the matcher
9-10: Fraud/cyber domain + team lead or senior scope + Israel location + Python/ML stack
7-8: Cyber-adjacent or fintech domain + senior IC scope + Israel + missing one strong signal
5-6: Interesting domain but weak fit on scope or location; or right scope but wrong domain
0-2: Dealbreaker domain, pure data engineering, relocation required, or no ML in the role`

const PROFILE_SECTIONS_GUIDE = [
  { section: '## Who I am', why: 'Your seniority and specialty. This is how the AI learns what "senior" means for you.' },
  { section: "## What I'm looking for", why: 'Your targets in priority order. The AI ranks title fit against this list.' },
  { section: '## Location', why: 'Commute and hybrid limits, so out-of-range roles score low and stay out of your digest.' },
  { section: '## Strong fit signals', why: 'Explicit boosts. When the AI sees these in a posting, the score goes up.' },
  { section: '## Weak fit / skip', why: 'Explicit penalties. When these appear, the score goes down.' },
  { section: '## Dealbreakers', why: 'Hard zeroes. A job that hits one scores 0, whatever else it offers.' },
  { section: '## Notes for the matcher', why: 'Nuances that are easy to misread, like partial experience that looks like a gap.' },
  { section: '## Scoring rubric', why: 'Your own score bands. Without them the AI invents its own, and those drift from run to run.' },
]

function checkProfileCompleteness(md: string): string[] {
  const required = ['## Who I am', "## What I'm looking for", '## Location', '## Strong fit', '## Weak fit', '## Dealbreakers', '## Notes for the matcher', '## Scoring rubric']
  return required.filter(h => !md.toLowerCase().includes(h.toLowerCase()))
}

function ProfileExampleGuidance() {
  const [showExample, setShowExample] = useState(false)
  const [showGuide, setShowGuide] = useState(false)
  return (
    <div className="space-y-2">
      <button type="button" aria-expanded={showExample} onClick={() => setShowExample(v => !v)} className="inline-flex items-center gap-1 text-sm text-accent hover:text-accent-hover transition-colors">
        {showExample ? <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />} See an example profile
      </button>
      {showExample && (
        <div className="bg-surface-raised rounded-lg p-4 border border-subtle">
          <pre className="text-xs text-muted whitespace-pre-wrap font-mono overflow-auto max-h-64">{EXAMPLE_PROFILE}</pre>
        </div>
      )}
      <button type="button" aria-expanded={showGuide} onClick={() => setShowGuide(v => !v)} className="inline-flex items-center gap-1 text-sm text-accent hover:text-accent-hover transition-colors">
        {showGuide ? <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />} What each section does
      </button>
      {showGuide && (
        <div className="bg-surface-raised rounded-lg p-4 border border-subtle space-y-2">
          {PROFILE_SECTIONS_GUIDE.map(({ section, why }) => (
            <div key={section}>
              <span className="text-xs font-mono text-foreground">{section}</span>
              <span className="text-xs text-muted ml-2">- {why}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

const PROFILE_PROMPT = `You are helping me create a job-matching profile file. I will answer your questions and you will produce a structured Markdown document called profile.md that a job-scoring AI will use to evaluate job postings for me.

Ask me the following questions one at a time (or ask them all at once and I will answer):

1. What is your current title and how many years of experience do you have?
2. What is your primary specialization - the area where you are stronger than most people at your level?
3. What job titles are you targeting, in priority order? (e.g. "Team Lead DS first, Senior DS second")
4. What domains do you want to work in? (e.g. cyber security, fraud, fintech, healthcare, general SaaS). Which are required vs. preferred?
5. Where are you located and what is your maximum commute time? Are you open to hybrid, fully remote, or relocation?
6. What are your absolute dealbreakers - roles or companies you will not consider no matter how good the title looks?
7. What specific technologies, methodologies, or company stages are a strong signal that a role is right for you?
8. What kinds of roles look good on paper but are actually wrong for you? (e.g. "MLOps-heavy roles", "pure research", "customer-facing")
9. What nuances should the scorer know that are easy to get wrong? (e.g. "I have military leadership but no formal DS manager title - treat it as a partial fit, not a miss")
10. What does a 9-10 role look like for you? What does a 5-6 look like?

After I answer, produce a profile.md with these exact sections:
- # Candidate Profile
- ## Who I am, in one paragraph
- ## What I'm looking for, in priority order
- ## Location
- ## Strong fit signals (boost the score)
- ## Weak fit / skip (drop the score)
- ## Dealbreakers (score = 0, do not surface)
- ## Notes for the matcher
- ## Scoring rubric for the matcher

Write the scoring rubric as explicit score bands: what a 9-10 looks like, what a 7-8 looks like, what a 5-6 looks like, and what 0-2 means. Be specific - reference the role types and signals I described.`

type Filters = {
  location_terms: string[]
  skip_title_terms: string[]
  keep_title_terms: string[]
  skip_companies: string[]
  skip_industries: string[]
}

function TagInput({ tags, onChange, placeholder }: { tags: string[]; onChange: (t: string[]) => void; placeholder?: string }) {
  const [input, setInput] = useState('')
  function addTag(val: string) {
    const trimmed = val.trim().replace(/,$/, '')
    if (trimmed && !tags.includes(trimmed)) onChange([...tags, trimmed])
    setInput('')
  }
  return (
    <div className="flex flex-wrap gap-1.5 p-2 bg-surface-raised rounded-lg border border-subtle min-h-[42px] transition-colors focus-within:border-accent focus-within:ring-1 focus-within:ring-accent">
      {tags.map(t => (
        <span key={t} className="flex items-center gap-1.5 pl-2.5 pr-1.5 py-0.5 bg-surface border border-border rounded-full text-sm text-foreground">
          {t}
          <button onClick={() => onChange(tags.filter(x => x !== t))} aria-label={`Remove ${t}`} className="w-4 h-4 flex items-center justify-center rounded-full text-muted hover:text-foreground hover:bg-surface-raised transition-colors">&times;</button>
        </span>
      ))}
      <input
        value={input}
        placeholder={placeholder}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => {
          if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); addTag(input) }
        }}
        onBlur={() => input && addTag(input)}
        className="flex-1 min-w-[120px] bg-transparent text-foreground text-sm outline-none placeholder:text-subtle"
      />
    </div>
  )
}

type FilterPanelProps = {
  locationInput: string
  onLocationChange: (v: string) => void
  skipTitles: string[]
  onSkipTitlesChange: (v: string[]) => void
  keepTitles: string[]
  onKeepTitlesChange: (v: string[]) => void
  skipCompanies: string[]
  onSkipCompaniesChange: (v: string[]) => void
  skipIndustries: string[]
  onSkipIndustriesChange: (v: string[]) => void
  preview: { passing: number; total: number; empty: boolean } | null
  previewLoading: boolean
}

function FilterPanel({ locationInput, onLocationChange, skipTitles, onSkipTitlesChange, keepTitles, onKeepTitlesChange, skipCompanies, onSkipCompaniesChange, skipIndustries, onSkipIndustriesChange, preview, previewLoading }: FilterPanelProps) {
  return (
    <div className="space-y-4">
      <div>
        <label className="text-sm text-muted block mb-1">
          Location filter <span title="Only jobs whose location contains this text get scored (e.g. 'israel'). Leave blank to score every location." className="text-subtle cursor-help">(?)</span>
        </label>
        <input value={locationInput} onChange={e => onLocationChange(e.target.value)} placeholder="e.g. israel - leave blank to score every location"
          className="w-full bg-surface-raised text-foreground px-3 py-2 rounded-lg border border-subtle placeholder:text-subtle transition-colors focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Skip jobs whose title contains... <span title="Jobs with any of these words in the title are dropped before scoring, so they never spend your quota or your attention (e.g. data engineer, analyst)" className="text-subtle cursor-help">(?)</span>
        </label>
        <p className="text-xs text-subtle mb-1">e.g. data engineer, analyst, bi developer</p>
        <TagInput tags={skipTitles} onChange={onSkipTitlesChange} placeholder="Type a term, press Enter" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Only score jobs whose title contains at least one of... <span title="Leave blank to score every title. Add terms and only titles containing one of them get scored (e.g. data scientist, ml engineer)" className="text-subtle cursor-help">(?)</span>
        </label>
        <p className="text-xs text-subtle mb-1">Leave blank to score every title</p>
        <TagInput tags={keepTitles} onChange={onKeepTitlesChange} placeholder="Type a term, press Enter" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Skip these companies <span title="Jobs from these companies are dropped before scoring - useful for your current employer or places you have already ruled out" className="text-subtle cursor-help">(?)</span>
        </label>
        <TagInput tags={skipCompanies} onChange={onSkipCompaniesChange} placeholder="Company name, press Enter" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Skip these industries <span title="Jobs whose description or company name contains any of these terms are dropped before scoring" className="text-subtle cursor-help">(?)</span>
        </label>
        <p className="text-xs text-subtle mb-1">e.g. gaming, adtech, gambling</p>
        <TagInput tags={skipIndustries} onChange={onSkipIndustriesChange} placeholder="Industry, press Enter" />
      </div>
      <div className="text-sm text-muted bg-surface-raised border border-subtle rounded-lg px-3 py-2">
        {previewLoading ? 'Calculating preview...' :
          preview === null ? '' :
          preview.empty ? 'No jobs collected yet - the preview will work after the next collection run.' :
          `With these filters, ${preview.passing} of the ${preview.total} jobs collected so far will be sent for scoring.`
        }
      </div>
    </div>
  )
}

const WELCOMED_KEY = 'cw.onboarding.welcomed.v1'
const STEP_KEYS = ['profile', 'cv', 'api_key', 'filters_seen'] as const
type Setup = Record<(typeof STEP_KEYS)[number], boolean>

async function authedFetch(path: string, init: RequestInit = {}) {
  const { data: { session } } = await supabase.auth.getSession()
  const token = session?.access_token
  if (!token) throw new Error('Not authenticated')
  return fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}`, ...init.headers },
  })
}

export default function OnboardingPage() {
  // 'loading' until /user/me answers; a failed lookup still opens the wizard.
  const [phase, setPhase] = useState<'loading' | 'welcome' | 'wizard' | 'allset'>('loading')
  const [setup, setSetup] = useState<Setup>({ profile: false, cv: false, api_key: false, filters_seen: false })
  const [savedProfileMd, setSavedProfileMd] = useState('')
  const [savedCvText, setSavedCvText] = useState('')
  const [stepSaving, setStepSaving] = useState(false)
  const [stepError, setStepError] = useState('')
  const [step, setStep] = useState(1)
  const [profileMd, setProfileMd] = useState('')
  const [cvText, setCvText] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [locationInput, setLocationInput] = useState('')
  const [filters, setFilters] = useState<Filters>({
    location_terms: [],
    skip_title_terms: ['data engineer', 'analyst', 'data analyst', 'bi developer', 'bi analyst'],
    keep_title_terms: [],
    skip_companies: [],
    skip_industries: ['gaming', 'adtech', 'gambling', 'crypto'],
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [pdfLoading, setPdfLoading] = useState(false)
  const [pdfError, setPdfError] = useState('')
  const [showKeyHelp, setShowKeyHelp] = useState(false)
  const [copied, setCopied] = useState(false)
  const [mdUploadError, setMdUploadError] = useState('')
  const [profileSkipWarned, setProfileSkipWarned] = useState(false)
  const [keyTestResult, setKeyTestResult] = useState('')
  const [keyTesting, setKeyTesting] = useState(false)
  const [filterPreview, setFilterPreview] = useState<{ passing: number; total: number; empty: boolean } | null>(null)
  const [filterPreviewLoading, setFilterPreviewLoading] = useState(false)
  const [scoringStage, setScoringStage] = useState<'idle' | 'scoring' | 'done'>('idle')
  const [scoredCount, setScoredCount] = useState<number | null>(null)

  useEffect(() => {
    async function load() {
      // ?step=N comes from the Digest checklist and skips the welcome.
      const requested = Number(new URLSearchParams(window.location.search).get('step'))
      let welcomed = false
      try { welcomed = localStorage.getItem(WELCOMED_KEY) === '1' } catch { /* storage blocked */ }
      let s = setup
      try {
        const r = await authedFetch('/user/me')
        if (r.ok) {
          const d = await r.json()
          if (d.setup) s = { profile: !!d.setup.profile, cv: !!d.setup.cv, api_key: !!d.setup.api_key, filters_seen: !!d.setup.filters_seen }
          if (d.setup?.complete) { setSetup(s); setPhase('allset'); return }
          if (typeof d.profile_md === 'string') { setProfileMd(d.profile_md); setSavedProfileMd(d.profile_md) }
          if (typeof d.cv_text === 'string') { setCvText(d.cv_text); setSavedCvText(d.cv_text) }
        }
        if (s.filters_seen) {
          const fr = await authedFetch('/user/filters')
          const f = fr.ok ? await fr.json() : null
          if (f && f.user_id) {
            setFilters({
              location_terms: f.location_terms ?? [],
              skip_title_terms: f.skip_title_terms ?? [],
              keep_title_terms: f.keep_title_terms ?? [],
              skip_companies: f.skip_companies ?? [],
              skip_industries: f.skip_industries ?? [],
            })
            setLocationInput((f.location_terms ?? [])[0] ?? '')
          }
        }
      } catch { /* backend unreachable - start fresh, never block */ }
      setSetup(s)
      const firstIncomplete = STEP_KEYS.findIndex(k => !s[k]) + 1
      setStep(requested >= 1 && requested <= 4 ? requested : firstIncomplete || 4)
      setPhase(welcomed || requested ? 'wizard' : 'welcome')
    }
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function startJourney() {
    try { localStorage.setItem(WELCOMED_KEY, '1') } catch { /* storage blocked */ }
    setPhase('wizard')
  }

  // Each step saves on Next, so closing the tab mid-way loses nothing.
  async function saveAndGo(next: number, save?: () => Promise<Partial<Setup> | void>) {
    setStepError('')
    if (save) {
      setStepSaving(true)
      try {
        const marked = await save()
        if (marked) setSetup(s => ({ ...s, ...marked }))
      } catch {
        setStepError('Could not save this step - check your connection and try again.')
        setStepSaving(false)
        return
      }
      setStepSaving(false)
    }
    setStep(next)
  }

  async function patch(path: string, body: unknown) {
    const r = await authedFetch(path, { method: 'PATCH', body: JSON.stringify(body) })
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
  }

  function saveProfile() {
    return saveAndGo(2, profileMd.trim() && profileMd !== savedProfileMd
      ? async () => { await patch('/user/profile', { profile_md: profileMd }); setSavedProfileMd(profileMd); return { profile: true } }
      : undefined)
  }

  function saveCv() {
    return saveAndGo(3, cvText.trim() && cvText !== savedCvText
      ? async () => { await patch('/user/cv', { cv_text: cvText }); setSavedCvText(cvText); return { cv: true } }
      : undefined)
  }

  function saveKey() {
    return saveAndGo(4, geminiKey.trim()
      ? async () => { await patch('/user/apikey', { gemini_api_key: geminiKey.trim() }); setGeminiKey(''); return { api_key: true } }
      : undefined)
  }

  async function fetchFilterPreview(loc: string, st: string[], kt: string[], sc: string[], si: string[]) {
    setFilterPreviewLoading(true)
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''
      const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/filter-preview`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          location_terms: loc.trim() ? [loc.trim()] : [],
          skip_title_terms: st,
          keep_title_terms: kt,
          skip_companies: sc,
          skip_industries: si,
        }),
      })
      if (r.ok) setFilterPreview(await r.json())
    } catch { /* silent */ } finally {
      setFilterPreviewLoading(false)
    }
  }

  useEffect(() => {
    if (step !== 4) return
    const t = setTimeout(() => fetchFilterPreview(locationInput, filters.skip_title_terms, filters.keep_title_terms, filters.skip_companies, filters.skip_industries), 400)
    return () => clearTimeout(t)
  }, [step, locationInput, filters.skip_title_terms, filters.keep_title_terms, filters.skip_companies, filters.skip_industries])

  async function testKeyInline() {
    setKeyTesting(true)
    setKeyTestResult('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''
      const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/user/test-key-inline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ gemini_api_key: geminiKey.trim() }),
      })
      const d = await r.json()
      setKeyTestResult(r.ok ? 'Key works!' : (d.detail ?? 'Test failed'))
    } catch {
      setKeyTestResult('Test failed - check your connection and try again.')
    } finally {
      setKeyTesting(false)
    }
  }

  function copyPrompt() {
    navigator.clipboard.writeText(PROFILE_PROMPT)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  async function uploadMdFile(file: File) {
    setMdUploadError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token ?? ''
      const text = await extractUploadText(file, token, process.env.NEXT_PUBLIC_API_URL!)
      setProfileMd(text)
    } catch (err: unknown) {
      setMdUploadError(err instanceof Error ? err.message : 'Could not read file')
    }
  }

  function handleStep1Next() {
    if (!profileMd.trim() && !profileSkipWarned) {
      setProfileSkipWarned(true)
      return
    }
    saveProfile()
  }

  async function finish() {
    setSaving(true)
    setError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token
      if (!token) throw new Error('Not authenticated')

      // Profile, CV and key were already saved step by step; only filters remain.
      const r = await authedFetch('/user/filters', {
        method: 'PATCH',
        body: JSON.stringify({ ...filters, location_terms: locationInput.trim() ? [locationInput.trim()] : [] }),
      })
      if (!r.ok) throw new Error('Could not save your filters')
      setSetup(s => ({ ...s, filters_seen: true }))

      // Trigger the first scan and wait for the result so we can show a count
      // instead of redirecting silently.
      setScoringStage('scoring')
      try {
        const scoreRes = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/score/`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
        const scoreData = await scoreRes.json().catch(() => ({}))
        setScoredCount(scoreRes.ok ? (scoreData.scored ?? 0) : null)
      } catch {
        setScoredCount(null)
      }
      setScoringStage('done')
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Something went wrong')
      setSaving(false)
      setScoringStage('idle')
      return
    }
    // Brief pause so the result count is visible before navigating.
    setTimeout(() => { window.location.href = '/digest' }, 1500)
  }

  const steps = ['Profile', 'CV', 'API Key', 'Filters']
  const doneCount = STEP_KEYS.filter(k => setup[k]).length

  if (phase === 'loading') {
    return <div className="min-h-screen bg-background" aria-busy="true" />
  }

  if (phase === 'welcome' || phase === 'allset') {
    return (
      <div className="relative min-h-screen bg-background text-foreground font-sans flex flex-col items-center justify-center px-4 py-12">
        <ThemeToggle className="absolute top-4 right-4 z-10" />
        <div className="bg-surface border border-border rounded-2xl p-8 w-full max-w-xl shadow-2xl shadow-black/20 space-y-5">
          {phase === 'welcome' ? (
            <>
              <h1 className="font-display text-3xl">Welcome to CareerWatch</h1>
              <ul className="space-y-2 text-sm text-muted list-disc list-inside">
                <li>CareerWatch tracks open roles at 100+ Israeli cyber, fraud and fintech companies and scores every one of them against your profile - not a generic keyword list.</li>
                <li>Scoring needs three things from you: a profile (what you want), your CV (what you have done) and a free Gemini API key, so scoring runs on your own quota at no cost.</li>
                <li>Setup takes about five minutes. Every step saves as you go, so you can close the tab and pick up exactly where you left off.</li>
              </ul>
              <div className="flex justify-end">
                <button onClick={startJourney} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors rounded-lg font-medium">Get started</button>
              </div>
            </>
          ) : (
            <>
              <h1 className="font-display text-3xl">You&apos;re all set</h1>
              <p className="text-sm text-muted">Your profile and Gemini key are saved{setup.cv ? '' : ' - add your CV in Settings and every score gets sharper'}. You can change anything in Settings.</p>
              <div className="flex flex-wrap gap-3 justify-end">
                <a href="/settings" className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors rounded-lg">Open Settings</a>
                <a href="/digest" className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors rounded-lg font-medium">Go to my digest</a>
              </div>
            </>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="relative min-h-screen bg-background text-foreground font-sans flex flex-col items-center justify-center px-4 py-12 overflow-hidden">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 cw-grid [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,black,transparent)]" />
        <div className="absolute left-1/2 top-[-18rem] -translate-x-1/2 w-[50rem] h-[32rem] rounded-full bg-accent/[0.08] blur-3xl" />
      </div>
      <ThemeToggle className="absolute top-4 right-4 z-10" />
      <style>{`
        @keyframes onboarding-step-in {
          from { opacity: 0; transform: translateY(10px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .onboarding-step-in { animation: onboarding-step-in 0.3s ease-out both; }
        @media (prefers-reduced-motion: reduce) {
          .onboarding-step-in { animation: none; }
        }
      `}</style>
      {/* Progress */}
      <div className="relative flex items-center gap-2 sm:gap-3 mb-4" aria-label={`Step ${step} of ${steps.length}, ${doneCount} of ${steps.length} done`}>
        {steps.map((label, i) => {
          const done = setup[STEP_KEYS[i]] && i + 1 !== step
          const current = i + 1 === step
          return (
            <div key={label} className="flex items-center gap-2 sm:gap-3">
              {i > 0 && (
                <div className={`h-px w-4 sm:w-8 transition-colors duration-300 ${setup[STEP_KEYS[i - 1]] ? 'bg-accent' : 'bg-border-subtle'}`} />
              )}
              <div className="flex items-center gap-2">
                <div
                  aria-current={current ? 'step' : undefined}
                  className={`w-8 h-8 rounded-lg flex items-center justify-center font-mono text-sm font-medium transition-all duration-300 ${
                    done
                      ? 'bg-accent text-accent-foreground'
                      : current
                        ? 'bg-accent text-accent-foreground ring-2 ring-accent ring-offset-2 ring-offset-background'
                        : 'bg-surface-raised text-subtle border border-border-subtle'
                  }`}
                >
                  {done ? <Check className="w-4 h-4" aria-hidden="true" /> : i + 1}
                </div>
                <span className={`text-sm hidden sm:block transition-colors duration-300 ${current ? 'text-foreground font-medium' : done ? 'text-muted' : 'text-subtle'}`}>{label}</span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Orientation intro */}
      <p className="relative font-mono text-xs text-subtle mb-2">{doneCount} of {steps.length} done</p>
      <p className="relative text-sm text-muted mb-6 text-center max-w-lg">
        Four steps - Profile, CV, API key, Filters - then we run your first scan and open your ranked digest. Profile and API key are required; CV and filters make the scores sharper. Each step saves when you click Next.
      </p>

      <div className="relative bg-surface border border-border rounded-2xl p-8 w-full max-w-2xl shadow-2xl shadow-black/20">
        {stepError && <p role="alert" className="text-danger text-sm mb-4">{stepError}</p>}

        {/* Step 1 */}
        {step === 1 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Set up your profile</h2>
              <p className="text-sm text-subtle mt-1">Your profile tells the AI what a great role looks like for you. Without it, every score is a guess.</p>
            </div>
            <p className="text-muted text-sm">Describe the roles you want, the domains you care about, where you can work, and what you will never accept. You can skip for now and finish in Settings, but scoring will not run until a profile exists.</p>

            <ProfileExampleGuidance />

            {/* Path A: Upload */}
            <div>
              <label className="text-sm text-muted block mb-1">Upload a profile you already have (.md, .txt, .pdf, .docx, .doc)</label>
              <input
                type="file"
                accept={ACCEPT_ATTR}
                onChange={e => { const f = e.target.files?.[0]; if (f) uploadMdFile(f); e.target.value = '' }}
                className="block w-full text-sm text-muted cursor-pointer rounded-lg border border-dashed border-subtle bg-surface-raised px-3 py-3 transition-colors hover:border-accent file:mr-4 file:cursor-pointer file:rounded-md file:border-0 file:bg-accent file:text-accent-foreground file:text-sm file:font-medium file:px-4 file:py-1.5 file:transition-colors hover:file:bg-accent-hover"
              />
              {mdUploadError && <p className="text-sm text-danger mt-1">{mdUploadError}</p>}
            </div>

            {/* Path B: Generate with AI */}
            <div className="space-y-2 bg-surface-raised rounded-xl p-4 border border-subtle">
              <p className="text-sm font-medium text-foreground">Or build one with an AI assistant</p>
              <p className="text-xs text-muted mb-2">1. Copy this prompt. 2. Paste it into ChatGPT, Claude or any chatbot and answer its questions. 3. Paste the finished profile below.</p>
              <div className="relative">
                <textarea readOnly value={PROFILE_PROMPT} rows={8} className="w-full bg-surface text-muted font-mono text-xs p-3 rounded-lg border border-border resize-none focus:outline-none" />
                <button onClick={copyPrompt} className="absolute top-2 right-2 px-2 py-1 bg-surface-raised border border-subtle hover:bg-border-subtle text-xs rounded-md transition-colors">
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <textarea value={profileMd} onChange={e => { setProfileMd(e.target.value); if (e.target.value.trim()) setProfileSkipWarned(false) }} rows={8}
              placeholder="Paste the generated profile here, or write your own in Markdown..."
              className="w-full bg-surface-raised text-foreground p-3 rounded-lg border border-subtle placeholder:text-subtle transition-colors resize-none focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />

            {(() => {
              const missing = checkProfileCompleteness(profileMd)
              return missing.length > 0 && profileMd.trim() ? (
                <div className="text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg p-2">
                  Missing sections: {missing.join(', ')} - the AI scores best when all eight are present.
                </div>
              ) : null
            })()}

            {profileSkipWarned && !profileMd.trim() && (
              <div className="bg-warning/10 border border-warning/40 rounded-lg p-3 text-warning text-sm">
                Without a profile the AI has nothing to match against, and scoring will not run until you add one in Settings. Click Skip again to continue anyway.
              </div>
            )}

            <div className="flex justify-end">
              <button onClick={handleStep1Next} disabled={stepSaving} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors disabled:opacity-40 rounded-lg font-medium">{stepSaving ? 'Saving...' : profileMd.trim() ? 'Next ->' : 'Skip ->'}</button>
            </div>
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Upload your CV <span className="font-sans text-sm text-subtle">(optional)</span></h2>
              <p className="text-sm text-subtle mt-1">Your CV is the ground truth for what you have actually done. It turns a hopeful score into an honest one.</p>
            </div>
            <p className="text-muted text-sm">The AI reads your CV, word for word, next to every job it scores. Skip for now if you like and add it later in Settings.</p>
            <div>
              <label className="text-sm text-muted block mb-1">Upload your CV (.md, .txt, .pdf, .docx, .doc)</label>
              <input
                type="file"
                accept={ACCEPT_ATTR}
                onChange={async (e) => {
                  const file = e.target.files?.[0]
                  if (!file) return
                  setPdfLoading(true)
                  setPdfError('')
                  try {
                    const { data: { session } } = await supabase.auth.getSession()
                    const token = session?.access_token ?? ''
                    const text = await extractUploadText(file, token, process.env.NEXT_PUBLIC_API_URL!)
                    setCvText(text)
                  } catch (err: unknown) {
                    setPdfError(err instanceof Error ? err.message : 'Could not extract text - paste it below instead.')
                  } finally {
                    setPdfLoading(false)
                    e.target.value = ''
                  }
                }}
                className="block w-full text-sm text-muted cursor-pointer rounded-lg border border-dashed border-subtle bg-surface-raised px-3 py-3 transition-colors hover:border-accent file:mr-4 file:cursor-pointer file:rounded-md file:border-0 file:bg-accent file:text-accent-foreground file:text-sm file:font-medium file:px-4 file:py-1.5 file:transition-colors hover:file:bg-accent-hover"
              />
              {pdfLoading && <p className="text-sm text-muted mt-1">Extracting text...</p>}
              {pdfError && <p className="text-sm text-danger mt-1">{pdfError}</p>}
              <p className="text-xs text-subtle mt-1">Or paste the text below</p>
            </div>
            <textarea value={cvText} onChange={e => setCvText(e.target.value)} rows={12} placeholder="Paste your CV text here..." className="w-full bg-surface-raised text-foreground p-3 rounded-lg border border-subtle placeholder:text-subtle transition-colors resize-none focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />
            {!cvText.trim() && (
              <p className="text-xs text-subtle">Without a CV the AI knows what you want but not what you have done, so scores lean on your profile alone.</p>
            )}
            <div className="flex justify-between">
              <button onClick={() => setStep(1)} className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors rounded-lg">&lt;- Back</button>
              <button onClick={saveCv} disabled={stepSaving} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors disabled:opacity-40 rounded-lg font-medium">{stepSaving ? 'Saving...' : cvText.trim() ? 'Next ->' : 'Skip ->'}</button>
            </div>
          </div>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Your Gemini API key</h2>
              <p className="text-sm text-subtle mt-1">Scoring runs on your own free Gemini quota. Your key, your calls, nothing to pay.</p>
            </div>
            <p className="text-muted text-sm">The key is encrypted before it is stored and used for two things: scoring jobs for you, and the gap analysis on the Gaps page. It is never logged or shared.</p>
            <p className="text-sm text-accent">It costs nothing - Google&apos;s Gemini API has a free tier, and that is all CareerWatch needs. <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="underline">Get your free key here</a>.</p>
            <input type="password" value={geminiKey} onChange={e => { setGeminiKey(e.target.value); setKeyTestResult('') }} placeholder={setup.api_key ? 'A key is already saved - paste a new one to replace it' : 'Paste your Gemini API key'} className="w-full bg-surface-raised text-foreground px-3 py-2 rounded-lg border border-subtle placeholder:text-subtle transition-colors focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />
            <div className="flex items-center gap-3">
              <button onClick={testKeyInline} disabled={!geminiKey.trim() || keyTesting}
                className="px-4 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors disabled:opacity-40 rounded-lg text-sm">
                {keyTesting ? 'Testing...' : 'Test key'}
              </button>
              {keyTestResult && (
                <span className={`text-sm ${keyTestResult === 'Key works!' ? 'text-score-high' : 'text-danger'}`}>
                  {keyTestResult}
                </span>
              )}
            </div>
            <button type="button" aria-expanded={showKeyHelp} onClick={() => setShowKeyHelp(!showKeyHelp)} className="inline-flex items-center gap-1 text-sm text-accent hover:text-accent-hover transition-colors">
              {showKeyHelp ? <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />} How to get a key
            </button>
            {showKeyHelp && (
              <ol className="text-sm text-muted space-y-1 list-decimal list-inside bg-surface-raised border border-subtle p-4 rounded-lg">
                <li>Open <a href="https://aistudio.google.com" target="_blank" rel="noopener noreferrer" className="text-accent underline">Google AI Studio</a></li>
                <li>Sign in with your Google account</li>
                <li>Click &quot;Get API key&quot;, then &quot;Create API key&quot;</li>
                <li>Copy the key and paste it above</li>
                <li>The free tier is enough to get started, and the quota resets daily</li>
              </ol>
            )}
            <p className="text-xs text-subtle">Scoring only ever runs with your key. Delete it in Settings and scoring stops.</p>
            <div className="flex justify-between">
              <button onClick={() => setStep(2)} className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors rounded-lg">&lt;- Back</button>
              <button onClick={saveKey} disabled={(!geminiKey.trim() && !setup.api_key) || stepSaving} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors disabled:opacity-40 rounded-lg font-medium">{stepSaving ? 'Saving...' : 'Next ->'}</button>
            </div>
          </div>
        )}

        {/* Step 4 */}
        {step === 4 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Set your filters</h2>
              <p className="text-sm text-subtle mt-1">Filters drop the obvious misses before scoring, so your quota and your attention go to jobs that could actually fit.</p>
            </div>

            <FilterPanel
              locationInput={locationInput}
              onLocationChange={v => setLocationInput(v)}
              skipTitles={filters.skip_title_terms}
              onSkipTitlesChange={v => setFilters(f => ({ ...f, skip_title_terms: v }))}
              keepTitles={filters.keep_title_terms}
              onKeepTitlesChange={v => setFilters(f => ({ ...f, keep_title_terms: v }))}
              skipCompanies={filters.skip_companies}
              onSkipCompaniesChange={v => setFilters(f => ({ ...f, skip_companies: v }))}
              skipIndustries={filters.skip_industries}
              onSkipIndustriesChange={v => setFilters(f => ({ ...f, skip_industries: v }))}
              preview={filterPreview}
              previewLoading={filterPreviewLoading}
            />

            {/* Setup summary */}
            <div className="bg-surface-raised border border-subtle rounded-lg p-4 text-sm space-y-2">
              <p className="cw-label text-subtle mb-2">Setup summary</p>
              <div className="flex items-center gap-2">
                <span className="text-muted w-16">Profile</span>
                <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full ${profileMd.trim() ? 'bg-score-high' : 'bg-warning'}`} />
                <span className={profileMd.trim() ? 'text-score-high' : 'text-warning'}>{profileMd.trim() ? 'Added' : 'Skipped'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted w-16">CV</span>
                <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full ${cvText.trim() ? 'bg-score-high' : 'bg-warning'}`} />
                <span className={cvText.trim() ? 'text-score-high' : 'text-warning'}>{cvText.trim() ? 'Added' : 'Skipped'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted w-16">Key</span>
                <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full ${setup.api_key ? 'bg-score-high' : 'bg-warning'}`} />
                <span className={setup.api_key ? 'text-score-high' : 'text-warning'}>{setup.api_key ? 'Set' : 'Missing - required'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted w-16">Location</span>
                <span className="text-foreground">{locationInput.trim() || 'none'}</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-muted w-16">Denylist</span>
                <span className="text-foreground">{filters.skip_title_terms.length} terms</span>
              </div>
            </div>

            {error && <p className="text-danger text-sm">{error}</p>}

            {scoringStage === 'scoring' && (
              <div className="flex items-center gap-2 text-sm text-muted bg-surface-raised border border-subtle rounded-lg px-3 py-2">
                <span className="w-4 h-4 rounded-full border-2 border-subtle border-t-accent animate-spin inline-block" />
                Scoring your first batch of jobs...
              </div>
            )}
            {scoringStage === 'done' && (
              <div className="flex items-center gap-2 text-sm text-score-high bg-score-high/10 border border-score-high/30 rounded-lg px-3 py-2">
                {scoredCount === null
                  ? 'Setup complete - opening your digest...'
                  : `Scored ${scoredCount} jobs - opening your digest...`}
              </div>
            )}

            <div className="flex justify-between">
              <button onClick={() => setStep(3)} disabled={saving} className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors disabled:opacity-40 rounded-lg">&lt;- Back</button>
              <button onClick={finish} disabled={saving || !setup.api_key} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors disabled:opacity-40 rounded-lg font-medium">
                {scoringStage === 'scoring' ? 'Scoring...' : saving ? 'Starting...' : 'Start my first scan'}
              </button>
            </div>
            <p className="text-xs text-subtle text-right">Your first scan runs right now. You will see the result before your digest opens.</p>
          </div>
        )}
      </div>
    </div>
  )
}
