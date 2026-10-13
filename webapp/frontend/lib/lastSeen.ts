// "New since your last visit" for the digest. last_seen_at lives in this
// browser only (per user id, not cross-device - no schema change). Every
// storage access is wrapped: blocked storage just disables the feature.

const KEY_PREFIX = 'cw.digest.lastSeen.v1:'

// Returns the PREVIOUS last_seen_at (ms) and stamps `now` in its place.
// null = first visit, no user, or storage unavailable -> nothing is "new".
// Call once per page visit.
export function takeLastSeen(userId: string | null | undefined, now: number = Date.now()): number | null {
  if (!userId) return null
  let prev: number | null = null
  try {
    const ls = window.localStorage
    const raw = Number(ls.getItem(KEY_PREFIX + userId))
    // Ignore missing/garbage/future values rather than badge everything.
    if (Number.isFinite(raw) && raw > 0 && raw <= now) prev = raw
    ls.setItem(KEY_PREFIX + userId, String(now))
  } catch {
    return null
  }
  return prev
}

export function isNewSince(scoredAt: string | null | undefined, prev: number | null): boolean {
  if (prev == null || !scoredAt) return false
  const t = Date.parse(scoredAt)
  return !isNaN(t) && t > prev
}
