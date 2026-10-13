// Tiny stale-while-revalidate cache in localStorage. Pages paint the last-seen
// list instantly from here, then refetch in the background and overwrite it.
//
// Stored as `cw:swr:<name>:<userId>` -> { v, savedAt, userId, data }. Bump a
// page's version whenever its row shape changes so an old deploy's cache is
// dropped instead of rendered with missing fields. Every access is wrapped in
// try/catch: private mode, quota errors or a corrupt entry must never crash a
// page - they just mean "no cache" (skeleton path).

export const SWR_PREFIX = 'cw:swr:'

type Entry<T> = { v: number; savedAt: number; userId: string; data: T }

function storage(): Storage | null {
  try {
    return typeof window === 'undefined' ? null : window.localStorage
  } catch {
    return null
  }
}

function keyFor(name: string, userId: string): string {
  return `${SWR_PREFIX}${name}:${userId}`
}

export function readCache<T>(
  name: string,
  opts: { userId: string | null | undefined; version: number; maxAgeMs: number },
): T | null {
  const ls = storage()
  if (!ls || !opts.userId) return null
  const key = keyFor(name, opts.userId)
  try {
    const raw = ls.getItem(key)
    if (!raw) return null
    const e = JSON.parse(raw) as Partial<Entry<T>> | null
    const age = Date.now() - Number(e?.savedAt)
    if (
      e && e.v === opts.version && e.userId === opts.userId &&
      typeof e.savedAt === 'number' && age >= 0 && age <= opts.maxAgeMs &&
      e.data !== undefined
    ) {
      return e.data as T
    }
  } catch {
    /* corrupt JSON - fall through and drop it */
  }
  try { ls.removeItem(key) } catch { /* ignore */ }
  return null
}

export function writeCache<T>(
  name: string,
  data: T,
  opts: { userId: string | null | undefined; version: number },
): void {
  const ls = storage()
  if (!ls || !opts.userId) return
  const key = keyFor(name, opts.userId)
  const entry: Entry<T> = { v: opts.version, savedAt: Date.now(), userId: opts.userId, data }
  try {
    ls.setItem(key, JSON.stringify(entry))
  } catch {
    // Quota exceeded etc. - drop the old entry so it can't go stale silently.
    try { ls.removeItem(key) } catch { /* ignore */ }
  }
}

// Called on sign-out so a shared browser keeps no cached lists for the next person.
export function clearSwrCache(): void {
  const ls = storage()
  if (!ls) return
  try {
    const keys: string[] = []
    for (let i = 0; i < ls.length; i++) {
      const k = ls.key(i)
      if (k && k.startsWith(SWR_PREFIX)) keys.push(k)
    }
    keys.forEach(k => ls.removeItem(k))
  } catch {
    /* ignore */
  }
}
