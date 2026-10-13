'use client'

import { useEffect, useRef, useState } from 'react'
import { supabase } from '@/lib/supabaseClient'
import { readCache, writeCache } from '@/lib/swrCache'
import { takeLastSeen, isNewSince } from '@/lib/lastSeen'
import { SCORE_BANDS, bandFor } from '@/lib/scoreBands'
import { flagInfo } from '@/lib/flags'
import GettingStartedChecklist from '@/app/components/GettingStartedChecklist'
import { DetailPanel } from '@/app/components/DetailPanel'
import { type Job, timeAgo, ScoreBadge, JobCard } from '@/app/components/JobCard'

// Friendly "resets Monday" wording. If the backend gives us an ISO reset date,
// append it (e.g. "resets Monday, Jun 22"); otherwise fall back to bare copy.
function resetWording(iso: string | null): string {
  if (!iso) return 'resets Monday'
  const d = new Date(`${iso}T00:00:00`)
  if (isNaN(d.getTime())) return 'resets Monday'
  const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return `resets Monday, ${date}`
}

// Small native-title popover trigger matching the existing "How scoring works"
// / "What do these tags mean?" patterns in this file.
function ScoreNowHelp() {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative inline-block">
      <button
        onClick={() => setOpen(v => !v)}
        aria-label="What does scoring do?"
        className="text-muted hover:text-foreground text-sm w-5 h-5 rounded-full border border-border-subtle flex items-center justify-center"
      >
        ?
      </button>
      {open && (
        <div className="absolute z-10 mt-2 right-0 w-72 bg-surface border border-border-subtle rounded-lg p-3 space-y-2 shadow-lg text-xs text-left">
          <p className="text-muted">
            <span className="font-medium text-foreground">Score now</span> scores newly collected jobs against your profile using your Gemini key.
          </p>
          <p className="text-muted">
            It runs in the background - you can leave this page and come back. Jobs are scored 200 at a time, and the next batch starts by itself while this page is open. New jobs are also scored automatically after each Monday and Thursday collection.
          </p>
          <p className="text-muted">
            Limited to 2 runs per week, counted when a run finishes all waiting jobs. The limit resets Monday.
          </p>
        </div>
      )}
    </div>
  )
}

// "Oct 12, 19:22" in the viewer's local time zone; null for missing/invalid
// input so the header line is hidden instead of reading "Invalid Date".
function fmtDateTime(iso: string | null | undefined): string | null {
  if (!iso) return null
  const d = new Date(iso)
  if (isNaN(d.getTime())) return null
  const date = d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  const time = d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', hour12: false })
  return `${date}, ${time}`
}

// Collection runs Mon & Thu 07:00 UTC (.github/workflows/collect-and-score.yml).
// Returns the weekday of the next run in the viewer's local time, e.g. "Thu".
function nextCollectionDay(now: Date = new Date()): string {
  for (let i = 0; i < 8; i++) {
    const d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + i, 7, 0))
    const dow = d.getUTCDay()
    if ((dow === 1 || dow === 4) && d.getTime() > now.getTime()) {
      return d.toLocaleDateString(undefined, { weekday: 'short' })
    }
  }
  return 'Mon'
}

function ScoreLegend() {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex items-center gap-2 flex-wrap text-xs text-muted">
      <span className="cw-label text-subtle">Score key:</span>
      {SCORE_BANDS.map(b => (
        <span key={b.range} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface border border-border">
          <span className={`${b.color} w-2.5 h-2.5 rounded-full inline-block ring-1 ring-white/10`} />
          <span>{b.range} {b.label}</span>
        </span>
      ))}
      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-surface border border-border text-subtle">
        <span className="w-2.5 h-2.5 rounded-full inline-block border border-subtle" />
        <span>below 5 not surfaced</span>
      </span>
      <div className="relative">
        <button onClick={() => setOpen(v => !v)} className="text-muted hover:text-foreground underline underline-offset-2 transition-colors">
          How scoring works
        </button>
        {open && (
          <div className="absolute z-10 mt-2 right-0 w-72 bg-surface border border-border-subtle rounded-lg p-3 space-y-2 shadow-xl">
            {SCORE_BANDS.map(b => (
              <div key={b.range} className="flex gap-2">
                <span className={`${b.color} w-3 h-3 rounded-full inline-block flex-shrink-0 mt-1`} />
                <p className="text-muted"><span className="font-medium text-foreground">{b.range} ({b.label}):</span> {b.blurb}</p>
              </div>
            ))}
            <div className="flex gap-2">
              <span className="w-3 h-3 rounded-full inline-block border border-subtle flex-shrink-0 mt-1" />
              <p className="text-muted"><span className="font-medium text-foreground">below 5:</span> Not a fit - these are not surfaced on the digest.</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

type SortBy = 'score' | 'date' | 'company'
const SORT_OPTIONS: { value: SortBy, label: string }[] = [
  { value: 'score', label: 'Score (high to low)' },
  { value: 'date', label: 'Date scored (newest)' },
  { value: 'company', label: 'Company (A-Z)' },
]

// Digest view state (filters, sort, min score) persisted per browser so a
// returning user keeps their view. Storage may be unavailable (private mode,
// blocked site data) or hold a malformed value - both fall back to defaults.
const VIEW_KEY = 'cw.digest.view.v1'
const DEFAULT_VIEW = { minScore: 5, titleFilter: '', companyFilter: '', locationFilter: '', sortBy: 'score' as SortBy }
type DigestView = typeof DEFAULT_VIEW

function loadView(): DigestView {
  try {
    const raw = JSON.parse(window.localStorage.getItem(VIEW_KEY) ?? 'null')
    if (!raw || typeof raw !== 'object') return DEFAULT_VIEW
    const str = (v: unknown, d: string) => typeof v === 'string' ? v : d
    return {
      minScore: Number.isInteger(raw.minScore) && raw.minScore >= 0 && raw.minScore <= 10 ? raw.minScore : DEFAULT_VIEW.minScore,
      titleFilter: str(raw.titleFilter, ''),
      companyFilter: str(raw.companyFilter, ''),
      locationFilter: str(raw.locationFilter, ''),
      sortBy: SORT_OPTIONS.some(o => o.value === raw.sortBy) ? raw.sortBy : DEFAULT_VIEW.sortBy,
    }
  } catch {
    return DEFAULT_VIEW
  }
}

function saveView(view: DigestView) {
  try {
    window.localStorage.setItem(VIEW_KEY, JSON.stringify(view))
  } catch {
    /* storage unavailable - the view just won't persist */
  }
}

const scoredTime = (j: Job) => { const t = Date.parse(j.scored_at); return isNaN(t) ? 0 : t }

function compareJobs(sortBy: SortBy) {
  return (a: Job, b: Job) => {
    if (sortBy === 'date') return scoredTime(b) - scoredTime(a) || b.score - a.score
    if (sortBy === 'company') return a.company.localeCompare(b.company) || b.score - a.score
    return b.score - a.score || scoredTime(b) - scoredTime(a)
  }
}

function JobCardSkeleton() {
  return (
    <div className="bg-surface border border-border rounded-xl p-5 flex gap-4 motion-safe:animate-pulse">
      <div className="w-9 h-9 rounded-lg bg-surface-raised flex-shrink-0" />
      <div className="flex-1 min-w-0 space-y-3">
        <div className="h-4 bg-surface-raised rounded w-2/3" />
        <div className="h-3 bg-surface-raised rounded w-1/3" />
        <div className="h-3 bg-surface-raised rounded w-full" />
        <div className="flex gap-2 pt-1">
          <div className="h-8 bg-surface-raised rounded-lg w-24" />
          <div className="h-8 bg-surface-raised rounded-lg w-28" />
        </div>
      </div>
    </div>
  )
}

// Diagnostic empty state shown when there are no jobs to render. The variant is
// keyed on account state (profile, key) plus whether anything has been scored,
// so the copy points at the real blocker instead of always saying "Score now".
function EmptyState({
  hasProfile, hasApiKey, scoredAny, onResetFilters,
}: {
  hasProfile: boolean
  hasApiKey: boolean
  scoredAny: boolean
  onResetFilters: () => void
}) {
  if (!hasProfile) {
    return (
      <div className="text-center py-12 px-6 space-y-4 rounded-xl border border-dashed border-border-subtle bg-surface">
        <p className="text-muted">Add a profile in Settings to start scoring.</p>
        <a href="/settings" className="inline-block px-4 py-2 bg-accent hover:bg-accent-hover text-accent-foreground rounded-lg text-sm font-medium transition-colors">
          Go to Settings
        </a>
      </div>
    )
  }
  if (!hasApiKey) {
    return (
      <div className="text-center py-12 px-6 space-y-4 rounded-xl border border-dashed border-border-subtle bg-surface">
        <p className="text-muted">Add your Gemini key in Settings to start scoring.</p>
        <a href="/settings" className="inline-block px-4 py-2 bg-accent hover:bg-accent-hover text-accent-foreground rounded-lg text-sm font-medium transition-colors">
          Go to Settings
        </a>
      </div>
    )
  }
  if (!scoredAny) {
    return (
      <div className="text-center py-12 px-6 rounded-xl border border-dashed border-border-subtle bg-surface">
        <p className="text-muted">Run your first scan - click "Score now" above to score newly collected jobs.</p>
      </div>
    )
  }
  // Scored, but the current filters hide everything.
  return (
    <div className="text-center py-12 px-6 space-y-4 rounded-xl border border-dashed border-border-subtle bg-surface">
      <p className="text-muted">No jobs match your filters.</p>
      <button onClick={onResetFilters} className="inline-block px-4 py-2 bg-surface-raised hover:bg-border-subtle/50 border border-border-subtle rounded-lg text-sm font-medium transition-colors">
        Reset filters
      </button>
    </div>
  )
}

// Slide-over detail view: full reasoning, flags with glossary definitions,
// and the complete job description (fetched per-job - the list payload stays
// light). Closes on Esc, backdrop click, or the X button.
function JobDetailPanel({
  job, description, descLoading, onClose, onToggleApplied,
}: {
  job: Job
  description: string | null
  descLoading: boolean
  onClose: () => void
  onToggleApplied: (j: Job) => void
}) {
  const band = bandFor(job.score)

  return (
    <DetailPanel
      ariaLabel={`${job.company} - ${job.title}`}
      onClose={onClose}
      header={
        <>
          <ScoreBadge score={job.score} />
          <div className="min-w-0">
            <h2 className="font-semibold text-foreground leading-snug">{job.title}</h2>
            <p className="text-sm text-muted truncate">
              {job.company} · {job.location} · <span className="font-mono text-xs text-subtle">scored {timeAgo(job.scored_at)}</span>
            </p>
          </div>
        </>
      }
      actions={
        <>
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer"
            className="px-4 py-2 bg-accent hover:bg-accent-hover text-accent-foreground text-sm rounded-lg font-medium transition-colors">
            Apply →
          </a>
          <button onClick={() => onToggleApplied(job)}
            className="px-4 py-2 bg-surface-raised hover:bg-border-subtle/50 border border-border-subtle text-muted hover:text-foreground text-sm rounded-lg transition-colors">
            {job.applied ? 'Undo applied' : 'Mark applied'}
          </button>
        </>
      }
    >
      <div>
        <p className="cw-label text-subtle mb-2">Match assessment</p>
        <p className="text-sm text-muted mb-2">
          <span className={`${band.color} inline-block w-2.5 h-2.5 rounded-full mr-1.5 align-middle`} aria-hidden="true" />
          {job.score}/10 · {band.range} - {band.label}
        </p>
        {job.reasoning
          ? <p className="text-sm italic leading-relaxed text-foreground/80 border-l-2 border-accent/40 pl-3">"{job.reasoning}"</p>
          : <p className="text-sm text-subtle">No reasoning stored for this job.</p>}
      </div>

      {job.flags.length > 0 && (
        <div>
          <p className="cw-label text-subtle mb-2">Signals</p>
          <ul className="space-y-1.5">
            {job.flags.map(f => {
              const info = flagInfo(f)
              return (
                <li key={f} className="text-sm">
                  <span className="px-2 py-0.5 bg-surface-raised text-foreground/90 text-xs rounded-full border border-border mr-2">{info.label}</span>
                  <span className="text-muted">{info.definition}</span>
                </li>
              )
            })}
          </ul>
        </div>
      )}

      <div>
        <p className="cw-label text-subtle mb-2">Job description</p>
        {descLoading ? (
          <div className="space-y-2 motion-safe:animate-pulse" aria-label="Loading description">
            {[0, 1, 2, 3, 4].map(i => <div key={i} className="h-3 bg-surface-raised rounded" style={{ width: `${95 - i * 8}%` }} />)}
          </div>
        ) : description ? (
          <p className="text-sm text-muted leading-relaxed whitespace-pre-wrap">{description}</p>
        ) : (
          <p className="text-sm text-subtle">
            Full description unavailable - open the posting via{' '}
            <a href={job.apply_url} target="_blank" rel="noopener noreferrer" className="text-accent hover:text-accent-hover underline underline-offset-2 transition-colors">Apply</a>.
          </p>
        )}
      </div>
    </DetailPanel>
  )
}

function ClosedJobCard({ job }: { job: Job }) {
  return (
    <div className="cw-card-in bg-surface/50 border border-dashed border-border rounded-xl p-4 flex gap-4 opacity-60 saturate-50 transition-opacity duration-200 hover:opacity-80">
      <ScoreBadge score={job.score} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-muted line-through decoration-border-subtle">{job.company} - {job.title}</span>
          <span className="px-2 py-0.5 bg-danger/10 text-danger text-xs rounded-full border border-danger/25">
            Closed{job.closed_at ? ` ${job.closed_at}` : ''}
          </span>
        </div>
        <div className="text-sm text-subtle mt-1">{job.location}</div>
        {job.reasoning && <p className="text-sm italic text-subtle mt-1.5 line-clamp-1">"{job.reasoning}"</p>}
        {job.apply_url && (
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer"
            className="text-xs text-subtle hover:text-muted underline underline-offset-2 mt-2 inline-block transition-colors">
            View posting
          </a>
        )}
      </div>
    </div>
  )
}

// SWR cache for the /jobs list. Bump JOBS_CACHE_VERSION when the Job row shape
// changes. 4 days = the longest gap between collection runs (Thu -> Mon), so an
// older cache certainly predates the latest collection and is not worth painting.
const JOBS_CACHE_VERSION = 1
const JOBS_CACHE_MAX_AGE_MS = 4 * 24 * 60 * 60 * 1000

export default function DigestPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  // While a cached list is on screen: 'updating' = background refetch in flight,
  // 'failed' = refetch failed and the cached list stays. 'none' = live data.
  const [cacheState, setCacheState] = useState<'none' | 'updating' | 'failed'>('none')
  const [cacheUserId, setCacheUserId] = useState<string | null>(null)
  const [jobsSynced, setJobsSynced] = useState(false)
  const [scoring, setScoring] = useState(false)
  const [scoreMsg, setScoreMsg] = useState('')
  const [scoreProgress, setScoreProgress] = useState<{ scored: number; total: number } | null>(null)
  const [rescoreAvailable, setRescoreAvailable] = useState(0)
  // True once this tab has seen a run in progress, so a finished run from an
  // earlier visit never re-announces its result on page load.
  const watchingRun = useRef(false)
  const pollTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  // Set on unmount so an in-flight status fetch never re-arms the poll or
  // touches state after the user has left the page.
  const unmounted = useRef(false)
  const [runsUsed, setRunsUsed] = useState(0)
  const [runLimitResetsOn, setRunLimitResetsOn] = useState<string | null>(null)
  const [currentProfileVersion, setCurrentProfileVersion] = useState(1)
  const [hasProfile, setHasProfile] = useState(false)
  const [hasCv, setHasCv] = useState(false)
  const [hasApiKey, setHasApiKey] = useState(false)
  const [minScore, setMinScore] = useState(DEFAULT_VIEW.minScore)
  const [titleFilter, setTitleFilter] = useState(DEFAULT_VIEW.titleFilter)
  const [companyFilter, setCompanyFilter] = useState(DEFAULT_VIEW.companyFilter)
  const [locationFilter, setLocationFilter] = useState(DEFAULT_VIEW.locationFilter)
  const [sortBy, setSortBy] = useState<SortBy>(DEFAULT_VIEW.sortBy)
  // Saved view is read after mount (not in the initial state) to avoid an SSR
  // hydration mismatch; saving waits until it has been read so defaults never
  // overwrite it.
  const [viewLoaded, setViewLoaded] = useState(false)
  const [showApplied, setShowApplied] = useState(false)
  const [showOutside, setShowOutside] = useState(false)
  // PREVIOUS last_seen_at (ms), captured once per page visit before it is
  // stamped to now. null = first visit / storage blocked: no banner, no badges.
  const [prevSeenAt, setPrevSeenAt] = useState<number | null>(null)
  const lastSeenTaken = useRef(false)
  // Not persisted in the saved view: on the next visit nothing is new, so a
  // remembered "only new" would just show an empty list.
  const [onlyNew, setOnlyNew] = useState(false)
  const [detailJobId, setDetailJobId] = useState<string | null>(null)
  const [detailDescription, setDetailDescription] = useState<string | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [stats, setStats] = useState<{
    suitable: number
    collected: number | null
    last_collected_at?: string | null
    last_scored_at?: string | null
  } | null>(null)
  // The checklist renders only once /user/me has answered, so it never flashes
  // (or sticks on) all-unchecked for a user who has everything set up.
  const [userLoaded, setUserLoaded] = useState(false)

  async function getToken() {
    const { data: { session } } = await supabase.auth.getSession()
    return session?.access_token ?? ''
  }

  async function loadJobs() {
    try {
      const token = await getToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setJobs(await res.json())
      setJobsSynced(true)
      setCacheState('none')
    } catch {
      // Keep whatever is on screen (cached list or empty); only flag it if cached.
      setCacheState(s => (s === 'none' ? 'none' : 'failed'))
    } finally {
      setLoading(false)
    }
  }

  // Paint the last-seen list from the per-user cache, then revalidate.
  async function initialLoad() {
    try {
      const { data: { session } } = await supabase.auth.getSession()
      const userId = session?.user?.id ?? null
      setCacheUserId(userId)
      // Once per visit (ref also guards a StrictMode double effect), so the
      // cached paint and the revalidated list share the same baseline.
      if (!lastSeenTaken.current) {
        lastSeenTaken.current = true
        setPrevSeenAt(takeLastSeen(userId))
      }
      const cached = readCache<Job[]>('jobs', { userId, version: JOBS_CACHE_VERSION, maxAgeMs: JOBS_CACHE_MAX_AGE_MS })
      if (Array.isArray(cached) && cached.length > 0) {
        setJobs(cached)
        setCacheState('updating')
        setLoading(false)
      }
    } catch {
      /* no session / no cache - skeleton path */
    }
    await loadJobs()
  }

  function retryRefresh() {
    setCacheState('updating')
    loadJobs()
  }

  async function loadStats() {
    const token = await getToken()
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) setStats(await res.json())
      else setStats(null)
    } catch {
      setStats(null)
    }
  }

  async function loadUser() {
    try {
      const token = await getToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/user/me`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) return
      const d = await res.json()
      setRunsUsed(d.scoring_runs_this_week ?? 0)
      setRunLimitResetsOn(d.run_limit_resets_on ?? null)
      setCurrentProfileVersion(d.profile_version ?? 1)
      setHasProfile(d.setup?.profile === true)
      setHasCv(d.setup?.cv === true)
      setHasApiKey(d.setup?.api_key === true)
      setUserLoaded(true)
    } catch {
      /* network error - keep the checklist hidden rather than show it wrong */
    }
  }

  useEffect(() => { initialLoad(); loadUser(); loadStats() }, [])

  // Persist the list only once it is live, so a failed refresh never re-stamps
  // stale cached data as fresh. Also catches applied toggles and score reloads.
  useEffect(() => {
    if (jobsSynced) writeCache('jobs', jobs, { userId: cacheUserId, version: JOBS_CACHE_VERSION })
  }, [jobsSynced, jobs, cacheUserId])

  useEffect(() => {
    const v = loadView()
    setMinScore(v.minScore)
    setTitleFilter(v.titleFilter)
    setCompanyFilter(v.companyFilter)
    setLocationFilter(v.locationFilter)
    setSortBy(v.sortBy)
    setViewLoaded(true)
  }, [])

  useEffect(() => {
    if (viewLoaded) saveView({ minScore, titleFilter, companyFilter, locationFilter, sortBy })
  }, [viewLoaded, minScore, titleFilter, companyFilter, locationFilter, sortBy])

  type ScoreRun = {
    status: 'running' | 'done' | 'failed'
    mode: 'new' | 'rescore' | 'auto'
    total: number
    scored: number
    remaining?: number
    error?: string | null
    warning?: string | null
  }

  function finishedMessage(run: ScoreRun) {
    if (run.status === 'failed') return run.error ?? 'Scoring failed'
    const noun = run.mode === 'rescore' ? 're-scored' : run.mode === 'auto' ? 'scored automatically' : 'scored'
    let msg = `${run.scored} of ${run.total} jobs ${noun}`
    if (run.remaining) msg += ` - ${run.remaining} more waiting, press Score now to continue`
    if (run.warning) msg += ` - ${run.warning}`
    return msg
  }

  // Scoring runs in the background on the server; poll its progress every 3s,
  // refreshing the list as batches land.
  async function pollScoreStatus(tick = 0) {
    if (pollTimer.current) clearTimeout(pollTimer.current)
    try {
      const token = await getToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/score/status`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: { run: ScoreRun | null; rescore_available?: number } = await res.json()
      if (unmounted.current) return
      setRescoreAvailable(data.rescore_available ?? 0)
      const run = data.run
      if (run?.status === 'running') {
        watchingRun.current = true
        setScoring(true)
        setScoreProgress({ scored: run.scored, total: run.total })
        if (tick > 0 && tick % 5 === 0) loadJobs()
        pollTimer.current = setTimeout(() => pollScoreStatus(tick + 1), 3000)
        return
      }
      if (watchingRun.current && run) {
        watchingRun.current = false
        // A clean run that stopped at the per-run cap: start the next batch
        // straight away instead of asking for another click. Auto runs are
        // chained on the server.
        if (run.status === 'done' && run.remaining && run.scored === run.total && run.mode !== 'auto') {
          loadJobs()
          triggerScoring(run.mode)
          return
        }
        setScoreMsg(finishedMessage(run))
        await loadJobs()
        await loadUser()
        await loadStats()
      }
    } catch {
      if (unmounted.current) return
      if (watchingRun.current) {
        // Transient network blip while a run is going - keep polling.
        pollTimer.current = setTimeout(() => pollScoreStatus(tick + 1), 5000)
        return
      }
    }
    if (unmounted.current) return
    setScoring(false)
    setScoreProgress(null)
  }

  useEffect(() => {
    unmounted.current = false
    pollScoreStatus()
    return () => {
      unmounted.current = true
      if (pollTimer.current) clearTimeout(pollTimer.current)
    }
  }, [])

  async function triggerScoring(mode: 'new' | 'rescore' = 'new') {
    setScoring(true)
    setScoreMsg('')
    setScoreProgress(null)
    try {
      const token = await getToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/score/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      })
      const data = await res.json().catch(() => ({}))
      if (unmounted.current) return
      if (res.ok && data.started) {
        watchingRun.current = true
        setScoreProgress({ scored: 0, total: data.run?.total ?? 0 })
        pollTimer.current = setTimeout(() => pollScoreStatus(1), 3000)
        return
      }
      if (res.status === 409) {
        // Already running (e.g. started in another tab) - just follow it.
        watchingRun.current = true
        pollScoreStatus(1)
        return
      }
      setScoreMsg(res.ok
        ? (data.message ?? 'Nothing to score')
        : (typeof data.detail === 'string' ? data.detail : `Scoring failed (HTTP ${res.status})`))
    } catch {
      setScoreMsg('Could not reach the server - please try again in a minute')
    }
    setScoring(false)
  }

  async function openDetail(job: Job) {
    setDetailJobId(job.id)
    setDetailDescription(null)
    setDetailLoading(true)
    try {
      const token = await getToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${job.id}`, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (res.ok) {
        const d = await res.json()
        setDetailDescription(d.description ?? '')
      } else {
        setDetailDescription('')
      }
    } catch {
      setDetailDescription('')
    } finally {
      setDetailLoading(false)
    }
  }

  async function toggleApplied(job: Job) {
    const token = await getToken()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs/${job.id}/applied`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    })
    if (!res.ok) {
      setScoreMsg('Could not update applied status - try again')
      return
    }
    setJobs(prev => prev.map(j => j.id === job.id ? { ...j, applied: !j.applied } : j))
  }

  function matchesMultiFilter(value: string, filter: string): boolean {
    if (!filter.trim()) return true
    const terms = filter.split(';').map(t => t.trim()).filter(Boolean)
    return terms.some(t => value.toLowerCase().includes(t.toLowerCase()))
  }

  const filtered = jobs
    .filter(j => j.score >= minScore)
    .filter(j => matchesMultiFilter(j.title, titleFilter))
    .filter(j => matchesMultiFilter(j.company, companyFilter))
    .filter(j => matchesMultiFilter(j.location, locationFilter))
    .filter(j => !onlyNew || isNewSince(j.scored_at, prevSeenAt))
    .sort(compareJobs(sortBy))
  // Jobs outside the saved Settings filters (e.g. scored before a location filter
  // was set) stay hidden unless asked for. Applied ones always show.
  const hiddenByFilters = filtered.filter(j => j.outside_filters && !j.applied).length
  const visible = showOutside ? filtered : filtered.filter(j => !j.outside_filters || j.applied)

  // Below-5 scores fall outside every band (bandFor would lump them into 5-6).
  const tierCounts = SCORE_BANDS.map(b => ({
    band: b,
    count: visible.filter(j => j.score >= 5 && bandFor(j.score) === b).length,
  }))

  const openJobs = visible.filter(j => (j.status ?? 'open') !== 'closed')
  const closedJobs = visible.filter(j => j.status === 'closed')
  const active = openJobs.filter(j => !j.applied)
  const applied = openJobs.filter(j => j.applied)
  // /jobs returns every score, so honour the min-score slider (not the text
  // filters) to keep the count meaningful when "show only new" is applied.
  const newCount = jobs.filter(j => j.score >= minScore && j.status !== 'closed' && (showOutside || !j.outside_filters) && isNewSince(j.scored_at, prevSeenAt)).length

  function resetFilters() {
    setMinScore(5)
    setTitleFilter('')
    setCompanyFilter('')
    setLocationFilter('')
    setSortBy(DEFAULT_VIEW.sortBy)
    setOnlyNew(false)
  }

  const lastScoredIso = stats?.last_scored_at
    ?? (jobs.length > 0 ? jobs.reduce((a, b) => a.scored_at > b.scored_at ? a : b).scored_at : null)
  const lastScored = lastScoredIso && !isNaN(new Date(lastScoredIso).getTime()) ? timeAgo(lastScoredIso) : null
  const lastCollected = fmtDateTime(stats?.last_collected_at)

  return (
    <div>
      {/* Card mount animation - gated behind prefers-reduced-motion: no-preference
          so reduced-motion users get an instant render. `backwards` (not `both`)
          keeps the post-animation transform free for the hover translate. */}
      <style>{`
        @keyframes cwCardIn {
          from { opacity: 0; transform: translateY(6px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @media (prefers-reduced-motion: no-preference) {
          .cw-card-in { animation: cwCardIn 0.3s ease-out backwards; }
        }
      `}</style>
      {/* Digest toolbar */}
      <div className="border-b border-border px-6 py-3 flex items-center justify-between bg-surface">
        <div className="space-y-0.5">
          {lastScored && <div className="text-sm text-muted">Last scored: <span className="font-mono text-xs">{lastScored}</span></div>}
          {stats && stats.suitable > 0 && (
            <div className="text-xs text-subtle font-mono">
              {stats.collected != null
                ? `${stats.suitable.toLocaleString()} suitable roles out of ${stats.collected.toLocaleString()} collected`
                : `${stats.suitable.toLocaleString()} suitable roles`}
            </div>
          )}
          <div className="text-xs text-subtle font-mono">
            {lastCollected
              ? `Last collected ${lastCollected} · next run ${nextCollectionDay()}`
              : 'New jobs collected Mon & Thu'}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {scoring && (
            <span className="flex items-center gap-2 text-sm text-muted">
              <span className="w-3 h-3 rounded-full border-2 border-border-subtle border-t-accent animate-spin inline-block" />
              <span aria-live="polite">
                {scoreProgress && scoreProgress.total > 0
                  ? `Scoring ${scoreProgress.scored} of ${scoreProgress.total}...`
                  : 'Scoring your jobs...'}
              </span>
            </span>
          )}
          {!scoring && scoreMsg && <span className="text-sm text-muted">{scoreMsg}</span>}
          {!scoring && rescoreAvailable > 0 && (
            <button
              onClick={() => triggerScoring('rescore')}
              className="text-xs text-subtle underline underline-offset-2 hover:text-foreground transition-colors"
              title="These jobs were scored before their full job description was available. Re-scoring reads the description too. It doesn't count toward your weekly runs."
            >
              Re-score {rescoreAvailable} with full descriptions
            </button>
          )}
          {cacheState === 'updating' && (
            <span className="text-xs text-subtle" aria-live="polite">Updating...</span>
          )}
          {cacheState === 'failed' && (
            <span className="text-xs text-subtle" aria-live="polite">
              Couldn&apos;t refresh - showing saved results.{' '}
              <button onClick={retryRefresh} className="underline underline-offset-2 hover:text-foreground transition-colors">Retry</button>
            </span>
          )}
          {runsUsed >= 2 && (
            <span className="text-xs text-subtle" title="2 scoring runs per week. The limit resets at the start of the week (Monday).">
              Run limit reached - {resetWording(runLimitResetsOn)}
            </span>
          )}
          <ScoreNowHelp />
          <button
            onClick={() => triggerScoring('new')}
            disabled={scoring || runsUsed >= 2}
            title={
              runsUsed >= 2
                ? `2 of 2 weekly runs used - ${resetWording(runLimitResetsOn)}`
                : 'Scores newly collected jobs against your profile using your Gemini key. 2 runs per week, resets Monday.'
            }
            className="px-4 py-2 bg-accent hover:bg-accent-hover text-accent-foreground disabled:bg-surface-raised disabled:text-subtle rounded-lg text-sm font-medium transition-colors"
          >
            {scoring ? 'Scoring...' : runsUsed >= 2 ? 'Run limit reached' : 'Score now'}
          </button>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-4 py-6 space-y-4">
        {/* Getting started checklist */}
        {userLoaded && <GettingStartedChecklist
          profile={hasProfile}
          cv={hasCv}
          apiKey={hasApiKey}
          hasJobs={jobs.length > 0}
        />}

        {/* New since last visit (suppressed on first visit - see lib/lastSeen.ts) */}
        {!loading && newCount > 0 && (
          <div className="flex items-center justify-between gap-3 flex-wrap px-4 py-2.5 rounded-xl border border-accent/25 bg-accent/10 text-sm" aria-live="polite">
            <span className="text-foreground">
              {newCount.toLocaleString()} new since your last visit
            </span>
            <button onClick={() => setOnlyNew(v => !v)} aria-pressed={onlyNew}
              className="text-accent hover:text-accent-hover underline underline-offset-2 transition-colors">
              {onlyNew ? 'Show all' : 'Show only new'}
            </button>
          </div>
        )}

        {/* Score legend */}
        <ScoreLegend />

        {/* Filters */}
        <div className="space-y-2">
          <div className="flex items-center gap-x-4 gap-y-2 flex-wrap">
            <div className="flex items-center gap-2">
              <label className="text-sm text-muted">Min score:</label>
              <input type="range" min={0} max={10} value={minScore} onChange={e => setMinScore(+e.target.value)} className="w-24 accent-accent" />
              <span className="text-sm w-4 text-foreground font-medium tabular-nums">{minScore}</span>
            </div>
            <div className="flex items-center gap-2">
              <label htmlFor="digest-sort" className="text-sm text-muted">Sort:</label>
              <select id="digest-sort" value={sortBy} onChange={e => setSortBy(e.target.value as SortBy)}
                className="px-2 py-1 bg-surface-raised rounded-lg border border-border-subtle text-sm focus:outline-none focus:border-accent transition-colors">
                {SORT_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <input value={titleFilter} onChange={e => setTitleFilter(e.target.value)}
              placeholder="e.g. Data Scientist; Machine Learning; Applied Scientist"
              className="flex-1 min-w-[200px] px-3 py-1.5 bg-surface-raised rounded-lg border border-border-subtle text-sm placeholder:text-subtle focus:outline-none focus:border-accent transition-colors" />
            <input value={companyFilter} onChange={e => setCompanyFilter(e.target.value)}
              placeholder="e.g. Wiz; CrowdStrike; Palo Alto"
              className="flex-1 min-w-[160px] px-3 py-1.5 bg-surface-raised rounded-lg border border-border-subtle text-sm placeholder:text-subtle focus:outline-none focus:border-accent transition-colors" />
            <input value={locationFilter} onChange={e => setLocationFilter(e.target.value)}
              placeholder="e.g. Tel Aviv; Herzliya; Remote"
              className="flex-1 min-w-[160px] px-3 py-1.5 bg-surface-raised rounded-lg border border-border-subtle text-sm placeholder:text-subtle focus:outline-none focus:border-accent transition-colors" />
          </div>
        </div>

        {/* Result count + per-tier summary */}
        {!loading && jobs.length > 0 && (
          <div className="flex items-center gap-3 flex-wrap text-xs text-subtle font-mono" aria-live="polite">
            <span>Showing {visible.length.toLocaleString()} of {jobs.length.toLocaleString()}</span>
            {tierCounts.map(({ band, count }) => (
              <span key={band.range} className="inline-flex items-center gap-1.5">
                <span className={`${band.color} w-2 h-2 rounded-full inline-block`} aria-hidden="true" />
                {band.range}: {count}
              </span>
            ))}
          </div>
        )}

        {hiddenByFilters > 0 && (
          <p className="text-sm text-subtle">
            {showOutside
              ? `Showing ${hiddenByFilters} job${hiddenByFilters !== 1 ? 's' : ''} outside your saved filters. `
              : `${hiddenByFilters} job${hiddenByFilters !== 1 ? 's' : ''} hidden by your saved filters (Settings - Filters). `}
            <button onClick={() => setShowOutside(v => !v)} className="text-muted hover:text-foreground underline underline-offset-2 decoration-border-subtle transition-colors">
              {showOutside ? 'Hide them' : 'Show them'}
            </button>
          </p>
        )}

        {/* Job list */}
        {loading && (
          <div className="space-y-4">
            {[0, 1, 2].map(i => <JobCardSkeleton key={i} />)}
          </div>
        )}
        {!loading && active.length === 0 && (
          <EmptyState
            hasProfile={hasProfile}
            hasApiKey={hasApiKey}
            scoredAny={jobs.length > 0}
            onResetFilters={resetFilters}
          />
        )}
        {!loading && active.map(job => <JobCard key={job.id} job={job} onToggleApplied={toggleApplied} currentProfileVersion={currentProfileVersion} onOpen={openDetail} isNew={isNewSince(job.scored_at, prevSeenAt)} />)}

        {/* Applied section */}
        {applied.length > 0 && (
          <div>
            <button onClick={() => setShowApplied(v => !v)} className="text-sm text-muted hover:text-foreground py-2 underline underline-offset-2 decoration-border-subtle transition-colors">
              {showApplied ? `Hide ${applied.length} applied` : `Show ${applied.length} applied`}
            </button>
            {showApplied && applied.map(job => <JobCard key={job.id} job={job} onToggleApplied={toggleApplied} currentProfileVersion={currentProfileVersion} onOpen={openDetail} isNew={isNewSince(job.scored_at, prevSeenAt)} />)}
          </div>
        )}

        {/* Closed section */}
        {closedJobs.length > 0 && (
          <div className="pt-4 border-t border-border">
            <h2 className="cw-label text-subtle mb-3">Recently closed ({closedJobs.length})</h2>
            <div className="space-y-2">
              {closedJobs.map(job => <ClosedJobCard key={job.id} job={job} />)}
            </div>
          </div>
        )}
      </div>

      {/* Job detail slide-over. The job is re-read from list state so
          Mark applied inside the panel stays in sync with the cards. */}
      {(() => {
        if (!detailJobId) return null
        const detailJob = jobs.find(j => j.id === detailJobId)
        if (!detailJob) return null
        return (
          <JobDetailPanel
            job={detailJob}
            description={detailDescription}
            descLoading={detailLoading}
            onClose={() => setDetailJobId(null)}
            onToggleApplied={toggleApplied}
          />
        )
      })()}
    </div>
  )
}
