'use client'

// Shared job card used by the digest page and the landing page's live preview.
// Extracted from app/(app)/digest/page.tsx so the landing "digest preview"
// cannot drift from the real card. No auth/data logic lives here - callers
// pass a Job plus handlers, so this is safe to render on public routes.

import { useState } from 'react'
import { FLAG_GLOSSARY, flagInfo } from '@/lib/flags'
import { bandFor } from '@/lib/scoreBands'

export type Job = {
  id: string
  company: string
  title: string
  location: string
  score: number
  reasoning: string
  flags: string[]
  scored_at: string
  applied: boolean
  apply_url: string
  profile_version?: number
  status?: 'open' | 'closed'
  closed_at?: string
}

export function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  const d = Math.floor(diff / 86_400_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${d}d ago`
}

export function ScoreBadge({ score }: { score: number }) {
  const band = bandFor(score)
  return (
    <span
      role="img"
      aria-label={`Score ${score} out of 10 - ${band.label}`}
      title={`${score}/10 - ${band.label}`}
      className={`${band.color} text-white font-mono text-sm font-semibold w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 shadow-md ring-1 ring-white/15 tabular-nums`}
    >
      <span aria-hidden="true">{score}</span>
    </span>
  )
}

export function FlagGlossary() {
  const [open, setOpen] = useState(false)
  return (
    <div className="relative inline-block">
      <button onClick={() => setOpen(v => !v)} className="text-muted hover:text-foreground underline underline-offset-2 text-xs transition-colors">
        What do these tags mean?
      </button>
      {open && (
        <div className="absolute z-10 mt-2 right-0 w-80 bg-surface border border-border-subtle rounded-lg p-3 space-y-2 shadow-xl text-xs">
          {Object.entries(FLAG_GLOSSARY).map(([slug, info]) => (
            <div key={slug}>
              <p className="text-muted"><span className="font-medium text-foreground">{info.label}:</span> {info.definition}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export function JobCard({ job, onToggleApplied, currentProfileVersion, onOpen, isNew }: { job: Job; onToggleApplied: (j: Job) => void; currentProfileVersion: number; onOpen?: (j: Job) => void; isNew?: boolean }) {
  const staleProfile = job.profile_version !== undefined && job.profile_version < currentProfileVersion
  return (
    <div
      onClick={onOpen ? e => {
        // Inner controls (Apply, Mark applied, glossary) keep their own
        // behavior - only clicks on the card body open the detail view.
        if ((e.target as HTMLElement).closest('a,button')) return
        onOpen(job)
      } : undefined}
      className={`cw-card-in bg-surface border border-border rounded-xl p-5 flex gap-4 transition-[transform,border-color,box-shadow] duration-200 hover:border-accent/30 hover:shadow-lg hover:shadow-black/10 motion-safe:hover:-translate-y-0.5 ${job.applied ? 'opacity-50' : ''} ${onOpen ? 'cursor-pointer' : ''}`}>
      <ScoreBadge score={job.score} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-semibold text-foreground text-base leading-snug">{job.title}</span>
          {isNew && <span className="px-2 py-0.5 bg-accent/10 text-accent text-xs rounded-full border border-accent/25">New</span>}
          {staleProfile && <span className="px-2 py-0.5 bg-surface-raised text-subtle text-xs rounded-full border border-border-subtle">scored with an older profile</span>}
        </div>
        <div className="text-sm mt-1 flex items-center gap-x-1.5 gap-y-0.5 flex-wrap">
          <span className="font-medium text-muted">{job.company}</span>
          <span className="text-subtle" aria-hidden="true">·</span>
          <span className="text-muted">{job.location}</span>
          <span className="text-subtle" aria-hidden="true">·</span>
          <span className="text-subtle font-mono text-xs">scored {timeAgo(job.scored_at)}</span>
        </div>
        {job.reasoning && <p className="text-sm italic leading-relaxed text-foreground/80 mt-2.5 line-clamp-2 border-l-2 border-accent/40 pl-3">"{job.reasoning}"</p>}
        {job.flags.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 mt-2.5">
            {job.flags.map(f => {
              const info = flagInfo(f)
              return (
                <span key={f} title={info.definition} className="px-2 py-0.5 bg-surface-raised text-muted text-xs rounded-full border border-border">
                  {info.label}
                </span>
              )
            })}
            <FlagGlossary />
          </div>
        )}
        <div className="flex gap-2 mt-4">
          <a href={job.apply_url} target="_blank" rel="noopener noreferrer"
            className="px-3.5 py-1.5 bg-accent hover:bg-accent-hover text-accent-foreground text-sm rounded-lg font-medium transition-colors">
            Apply →
          </a>
          <button onClick={() => onToggleApplied(job)}
            className="px-3.5 py-1.5 bg-surface-raised hover:bg-border-subtle/50 border border-border-subtle text-muted hover:text-foreground text-sm rounded-lg transition-colors">
            {job.applied ? 'Undo applied' : 'Mark applied'}
          </button>
          {onOpen && (
            <button onClick={() => onOpen(job)}
              className="px-3.5 py-1.5 text-muted hover:text-foreground text-sm rounded-lg transition-colors underline underline-offset-2 decoration-border-subtle">
              Details
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
