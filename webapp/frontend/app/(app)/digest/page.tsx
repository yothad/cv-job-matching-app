'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabaseClient'
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
            Limited to 2 runs per week. The limit resets Monday.
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

export default function DigestPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)
  const [scoring, setScoring] = useState(false)
  const [scoreMsg, setScoreMsg] = useState('')
  const [runsUsed, setRunsUsed] = useState(0)
  const [runLimitResetsOn, setRunLimitResetsOn] = useState<string | null>(null)
  const [currentProfileVersion, setCurrentProfileVersion] = useState(1)
  const [hasProfile, setHasProfile] = useState(false)
  const [hasCv, setHasCv] = useState(false)
  const [hasApiKey, setHasApiKey] = useState(false)
  const [minScore, setMinScore] = useState(5)
  const [titleFilter, setTitleFilter] = useState('')
  const [companyFilter, setCompanyFilter] = useState('')
  const [locationFilter, setLocationFilter] = useState('')
  const [showApplied, setShowApplied] = useState(false)
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
    const token = await getToken()
    const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/jobs`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (res.ok) setJobs(await res.json())
    setLoading(false)
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
      setHasProfile(!!(d.profile_md && String(d.profile_md).trim()))
      setHasCv(!!(d.cv_text && String(d.cv_text).trim()))
      setHasApiKey(d.has_api_key === true)
      setUserLoaded(true)
    } catch {
      /* network error - keep the checklist hidden rather than show it wrong */
    }
  }

  useEffect(() => { loadJobs(); loadUser(); loadStats() }, [])

  async function triggerScoring() {
    setScoring(true)
    setScoreMsg('')
    try {
      const token = await getToken()
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/score/`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      })
      const data = await res.json().catch(() => ({}))
      if (res.ok) {
        const base = data.message ?? `Scored ${data.scored ?? 0} new jobs`
        setScoreMsg(data.warning ? `${base} - ${data.warning}` : base)
      } else {
        setScoreMsg(typeof data.detail === 'string' ? data.detail : `Scoring failed (HTTP ${res.status})`)
      }
    } catch {
      setScoreMsg('Could not reach the server - please try again in a minute')
    }
    await loadJobs()
    await loadUser()
    await loadStats()
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

  const openJobs = filtered.filter(j => (j.status ?? 'open') !== 'closed')
  const closedJobs = filtered.filter(j => j.status === 'closed')
  const active = openJobs.filter(j => !j.applied)
  const applied = openJobs.filter(j => j.applied)

  function resetFilters() {
    setMinScore(5)
    setTitleFilter('')
    setCompanyFilter('')
    setLocationFilter('')
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
              Scoring your jobs...
            </span>
          )}
          {!scoring && scoreMsg && <span className="text-sm text-muted">{scoreMsg}</span>}
          {runsUsed >= 2 && (
            <span className="text-xs text-subtle" title="2 scoring runs per week. The limit resets at the start of the week (Monday).">
              Run limit reached - {resetWording(runLimitResetsOn)}
            </span>
          )}
          <ScoreNowHelp />
          <button
            onClick={triggerScoring}
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

        {/* Score legend */}
        <ScoreLegend />

        {/* Filters */}
        <div className="space-y-2">
          <div className="flex items-center gap-2">
            <label className="text-sm text-muted">Min score:</label>
            <input type="range" min={0} max={10} value={minScore} onChange={e => setMinScore(+e.target.value)} className="w-24 accent-accent" />
            <span className="text-sm w-4 text-foreground font-medium tabular-nums">{minScore}</span>
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
        {!loading && active.map(job => <JobCard key={job.id} job={job} onToggleApplied={toggleApplied} currentProfileVersion={currentProfileVersion} onOpen={openDetail} />)}

        {/* Applied section */}
        {applied.length > 0 && (
          <div>
            <button onClick={() => setShowApplied(v => !v)} className="text-sm text-muted hover:text-foreground py-2 underline underline-offset-2 decoration-border-subtle transition-colors">
              {showApplied ? `Hide ${applied.length} applied` : `Show ${applied.length} applied`}
            </button>
            {showApplied && applied.map(job => <JobCard key={job.id} job={job} onToggleApplied={toggleApplied} currentProfileVersion={currentProfileVersion} onOpen={openDetail} />)}
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
