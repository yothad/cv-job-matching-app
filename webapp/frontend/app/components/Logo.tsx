'use client'

import { useId } from 'react'

/*
  CV-Job Matching brand.
  Mark: two overlapping rings (your CV, the job) on a violet -> pink -> amber
  tile; the shared lens is the match. Wordmark: "CV-Job" in the text colour,
  "Matching" in a violet -> pink gradient that holds contrast in both themes.
*/

export const BRAND_NAME = 'CV-Job Matching'

export function LogoMark({ size = 32, className = '' }: { size?: number; className?: string }) {
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const g = `${id}-grad`
  const s = `${id}-shine`
  const c = `${id}-clip`
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      aria-hidden="true"
      className={`shrink-0 ${className}`}
    >
      <defs>
        <linearGradient id={g} x1="4" y1="2" x2="46" y2="46" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#6D28D9" />
          <stop offset="0.5" stopColor="#DB2777" />
          <stop offset="1" stopColor="#F59E0B" />
        </linearGradient>
        <linearGradient id={s} x1="24" y1="2" x2="24" y2="26" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#FFFFFF" stopOpacity="0.28" />
          <stop offset="1" stopColor="#FFFFFF" stopOpacity="0" />
        </linearGradient>
        <clipPath id={c}>
          <circle cx="19" cy="24" r="9.5" />
        </clipPath>
      </defs>
      <rect x="2" y="2" width="44" height="44" rx="12" fill={`url(#${g})`} />
      <rect x="2" y="2" width="44" height="44" rx="12" fill={`url(#${s})`} />
      <circle cx="29" cy="24" r="9.5" fill="#FFFFFF" clipPath={`url(#${c})`} />
      <circle cx="19" cy="24" r="9.5" stroke="#FFFFFF" strokeWidth="3" />
      <circle cx="29" cy="24" r="9.5" stroke="#FFFFFF" strokeWidth="3" />
    </svg>
  )
}

export function Wordmark({ className = '' }: { className?: string }) {
  return (
    <span className={`font-sans font-semibold tracking-tight leading-none text-foreground whitespace-nowrap ${className}`}>
      CV-Job{' '}
      <span className="bg-gradient-to-r from-violet-500 to-pink-500 bg-clip-text text-transparent">Matching</span>
    </span>
  )
}

type Size = 'sm' | 'md' | 'lg'
const MARK: Record<Size, number> = { sm: 28, md: 32, lg: 44 }
const TEXT: Record<Size, string> = { sm: 'text-lg', md: 'text-xl', lg: 'text-3xl' }

export function Logo({ size = 'md', className = '' }: { size?: Size; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <LogoMark size={MARK[size]} />
      <Wordmark className={TEXT[size]} />
    </span>
  )
}
