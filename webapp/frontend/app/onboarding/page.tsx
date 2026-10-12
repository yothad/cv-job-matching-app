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
  { section: '## Who I am', why: 'Sets seniority and specialization - the AI uses this to calibrate what "senior" means for you.' },
  { section: "## What I'm looking for", why: 'Priority-ordered targets - the AI uses this to rank title fit.' },
  { section: '## Location', why: 'Commute and hybrid preferences - prevents surfacing out-of-range roles.' },
  { section: '## Strong fit signals', why: 'Explicit boosts - the AI looks for these in the JD to raise the score.' },
  { section: '## Weak fit / skip', why: 'Explicit penalties - the AI lowers the score when these appear.' },
  { section: '## Dealbreakers', why: 'Hard zeroes - the AI scores these 0 regardless of everything else.' },
  { section: '## Notes for the matcher', why: 'Nuances that are easy to get wrong - e.g. partial signals that look like gaps.' },
  { section: '## Scoring rubric', why: 'Explicit score bands - without this the AI invents its own rubric, which is less reliable.' },
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
        {showGuide ? <ChevronDown className="w-3.5 h-3.5" aria-hidden="true" /> : <ChevronRight className="w-3.5 h-3.5" aria-hidden="true" />} Required sections guide
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
          Location filter <span title="Only score jobs whose location contains this text (e.g. 'israel')" className="text-subtle cursor-help">(?)</span>
        </label>
        <input value={locationInput} onChange={e => onLocationChange(e.target.value)} placeholder="e.g. israel (leave blank for no filter)"
          className="w-full bg-surface-raised text-foreground px-3 py-2 rounded-lg border border-subtle placeholder:text-subtle transition-colors focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Skip jobs whose title contains... <span title="Jobs with these words in the title are dropped before scoring (e.g. data engineer, analyst)" className="text-subtle cursor-help">(?)</span>
        </label>
        <p className="text-xs text-subtle mb-1">e.g. data engineer, analyst, bi developer</p>
        <TagInput tags={skipTitles} onChange={onSkipTitlesChange} placeholder="add term, press Enter" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Only score jobs whose title contains at least one of... <span title="Leave blank to score all titles. Add terms to score only matching titles (e.g. data scientist, ml engineer)" className="text-subtle cursor-help">(?)</span>
        </label>
        <p className="text-xs text-subtle mb-1">Leave blank to score all titles</p>
        <TagInput tags={keepTitles} onChange={onKeepTitlesChange} placeholder="add term, press Enter" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Skip these companies <span title="Jobs from these companies are dropped before scoring" className="text-subtle cursor-help">(?)</span>
        </label>
        <TagInput tags={skipCompanies} onChange={onSkipCompaniesChange} placeholder="company name, press Enter" />
      </div>
      <div>
        <label className="text-sm text-muted block mb-1">
          Skip these industries <span title="Jobs tagged with these industries are dropped before scoring" className="text-subtle cursor-help">(?)</span>
        </label>
        <p className="text-xs text-subtle mb-1">e.g. gaming, adtech, gambling</p>
        <TagInput tags={skipIndustries} onChange={onSkipIndustriesChange} placeholder="industry, press Enter" />
      </div>
      <div className="text-sm text-muted bg-surface-raised border border-subtle rounded-lg px-3 py-2">
        {previewLoading ? 'Calculating preview...' :
          preview === null ? '' :
          preview.empty ? 'No collected jobs yet - run the pipeline first.' :
          `With these filters, ${preview.passing} of today's ${preview.total} collected jobs will be sent for scoring.`
        }
      </div>
    </div>
  )
}

export default function OnboardingPage() {
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
      setKeyTestResult('Test failed - check your connection')
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
    setStep(2)
  }

  async function finish() {
    setSaving(true)
    setError('')
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const token = session?.access_token
      if (!token) throw new Error('Not authenticated')

      const effectiveFilters = {
        ...filters,
        location_terms: locationInput.trim() ? [locationInput.trim()] : [],
      }

      const r = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/user/setup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ profile_md: profileMd, cv_text: cvText, gemini_api_key: geminiKey, filters: effectiveFilters }),
      })
      if (!r.ok) throw new Error('Setup failed')

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
      <div className="relative flex items-center gap-2 sm:gap-3 mb-4" aria-label={`Step ${step} of ${steps.length}`}>
        {steps.map((label, i) => {
          const done = i + 1 < step
          const current = i + 1 === step
          return (
            <div key={label} className="flex items-center gap-2 sm:gap-3">
              {i > 0 && (
                <div className={`h-px w-4 sm:w-8 transition-colors duration-300 ${i + 1 <= step ? 'bg-accent' : 'bg-border-subtle'}`} />
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
      <p className="relative text-sm text-muted mb-6 text-center max-w-lg">
        Set up in 4 steps - Profile, CV, API key, and Filters - then we run your first scan and show you a ranked digest.
      </p>

      <div className="relative bg-surface border border-border rounded-2xl p-8 w-full max-w-2xl shadow-2xl shadow-black/20">

        {/* Step 1 */}
        {step === 1 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Set up your profile <span className="font-sans text-sm text-subtle">(optional)</span></h2>
              <p className="text-sm text-subtle mt-1">Your profile tells the AI what to look for - without it, scoring is generic.</p>
            </div>
            <p className="text-muted text-sm">Describe your target roles, domains, location, and dealbreakers. You can skip this and add it later in Settings.</p>

            <ProfileExampleGuidance />

            {/* Path A: Upload */}
            <div>
              <label className="text-sm text-muted block mb-1">Upload an existing profile (.md, .txt, .pdf, .docx, .doc)</label>
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
              <p className="text-sm font-medium text-foreground">Or generate one with AI</p>
              <p className="text-xs text-muted mb-2">Step 1 - Copy this prompt. Step 2 - Paste into ChatGPT, Claude, or any LLM and answer its questions. Step 3 - Paste the result below.</p>
              <div className="relative">
                <textarea readOnly value={PROFILE_PROMPT} rows={8} className="w-full bg-surface text-muted font-mono text-xs p-3 rounded-lg border border-border resize-none focus:outline-none" />
                <button onClick={copyPrompt} className="absolute top-2 right-2 px-2 py-1 bg-surface-raised border border-subtle hover:bg-border-subtle text-xs rounded-md transition-colors">
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <textarea value={profileMd} onChange={e => { setProfileMd(e.target.value); if (e.target.value.trim()) setProfileSkipWarned(false) }} rows={8}
              placeholder="Paste the LLM output here (or your profile.md content)..."
              className="w-full bg-surface-raised text-foreground p-3 rounded-lg border border-subtle placeholder:text-subtle transition-colors resize-none focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />

            {(() => {
              const missing = checkProfileCompleteness(profileMd)
              return missing.length > 0 && profileMd.trim() ? (
                <div className="text-xs text-warning bg-warning/10 border border-warning/30 rounded-lg p-2">
                  Missing sections: {missing.join(', ')}
                </div>
              ) : null
            })()}

            {profileSkipWarned && !profileMd.trim() && (
              <div className="bg-warning/10 border border-warning/40 rounded-lg p-3 text-warning text-sm">
                Without a profile the AI scores all jobs generically - you&apos;ll likely see an empty or irrelevant digest until you add one in Settings.
              </div>
            )}

            <div className="flex justify-end">
              <button onClick={handleStep1Next} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors rounded-lg font-medium">{profileMd.trim() ? 'Next ->' : 'Skip ->'}</button>
            </div>
          </div>
        )}

        {/* Step 2 */}
        {step === 2 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Upload your CV <span className="font-sans text-sm text-subtle">(optional)</span></h2>
              <p className="text-sm text-subtle mt-1">Your CV is the ground truth of what you&apos;ve done - it sharpens every score.</p>
            </div>
            <p className="text-muted text-sm">Your CV is used verbatim in scoring prompts. You can skip this and add it later in Settings.</p>
            <div>
              <label className="text-sm text-muted block mb-1">Upload CV (.md, .txt, .pdf, .docx, .doc)</label>
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
                    setPdfError(err instanceof Error ? err.message : 'Could not extract text - please paste manually')
                  } finally {
                    setPdfLoading(false)
                    e.target.value = ''
                  }
                }}
                className="block w-full text-sm text-muted cursor-pointer rounded-lg border border-dashed border-subtle bg-surface-raised px-3 py-3 transition-colors hover:border-accent file:mr-4 file:cursor-pointer file:rounded-md file:border-0 file:bg-accent file:text-accent-foreground file:text-sm file:font-medium file:px-4 file:py-1.5 file:transition-colors hover:file:bg-accent-hover"
              />
              {pdfLoading && <p className="text-sm text-muted mt-1">Extracting text...</p>}
              {pdfError && <p className="text-sm text-danger mt-1">{pdfError}</p>}
              <p className="text-xs text-subtle mt-1">Or paste text directly below</p>
            </div>
            <textarea value={cvText} onChange={e => setCvText(e.target.value)} rows={12} placeholder="Paste your CV text here..." className="w-full bg-surface-raised text-foreground p-3 rounded-lg border border-subtle placeholder:text-subtle transition-colors resize-none focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />
            {!cvText.trim() && (
              <p className="text-xs text-subtle">Scoring quality drops without a CV - the AI has less context about your background.</p>
            )}
            <div className="flex justify-between">
              <button onClick={() => setStep(1)} className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors rounded-lg">&lt;- Back</button>
              <button onClick={() => setStep(3)} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors rounded-lg font-medium">{cvText.trim() ? 'Next ->' : 'Skip ->'}</button>
            </div>
          </div>
        )}

        {/* Step 3 */}
        {step === 3 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Your Gemini API key</h2>
              <p className="text-sm text-subtle mt-1">Scoring runs on your own free Gemini quota - your data never leaves your key.</p>
            </div>
            <p className="text-muted text-sm">Used only for scoring. Never logged or shared.</p>
            <p className="text-sm text-accent">It&apos;s fully free - Google&apos;s Gemini API has a free tier that&apos;s plenty for scoring jobs. <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="underline">Get your free key here</a>.</p>
            <input type="password" value={geminiKey} onChange={e => { setGeminiKey(e.target.value); setKeyTestResult('') }} placeholder="Paste your Gemini API key" className="w-full bg-surface-raised text-foreground px-3 py-2 rounded-lg border border-subtle placeholder:text-subtle transition-colors focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent" />
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
                <li>Go to <a href="https://aistudio.google.com" target="_blank" rel="noopener noreferrer" className="text-accent underline">Google AI Studio</a></li>
                <li>Sign in with your Google account</li>
                <li>Click &quot;Get API key&quot; then &quot;Create API key&quot;</li>
                <li>Copy and paste the key here</li>
                <li>The free tier is enough to get started (quota resets daily)</li>
              </ol>
            )}
            <p className="text-xs text-subtle">We never score jobs without your key. If you delete it, scoring stops.</p>
            <div className="flex justify-between">
              <button onClick={() => setStep(2)} className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors rounded-lg">&lt;- Back</button>
              <button onClick={() => setStep(4)} disabled={!geminiKey.trim()} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors disabled:opacity-40 rounded-lg font-medium">Next -&gt;</button>
            </div>
          </div>
        )}

        {/* Step 4 */}
        {step === 4 && (
          <div className="space-y-4 onboarding-step-in">
            <div>
              <h2 className="font-display text-3xl">Configure filters</h2>
              <p className="text-sm text-subtle mt-1">Filters drop the noise before scoring - saves you reading irrelevant results.</p>
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
                <span aria-hidden="true" className="w-1.5 h-1.5 rounded-full bg-score-high" />
                <span className="text-score-high">Set</span>
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
                  ? 'Setup complete - taking you to your digest...'
                  : `Scored ${scoredCount} new jobs - taking you to your digest...`}
              </div>
            )}

            <div className="flex justify-between">
              <button onClick={() => setStep(3)} disabled={saving} className="px-6 py-2 border border-subtle text-muted hover:text-foreground hover:bg-surface-raised transition-colors disabled:opacity-40 rounded-lg">&lt;- Back</button>
              <button onClick={finish} disabled={saving} className="px-6 py-2 bg-accent hover:bg-accent-hover text-accent-foreground transition-colors disabled:opacity-40 rounded-lg font-medium">
                {scoringStage === 'scoring' ? 'Scoring...' : saving ? 'Starting...' : 'Start my first scan'}
              </button>
            </div>
            <p className="text-xs text-subtle text-right">Your first scan runs now - we will show the result before opening your digest.</p>
          </div>
        )}
      </div>
    </div>
  )
}
