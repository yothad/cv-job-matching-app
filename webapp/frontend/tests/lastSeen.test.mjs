// Run: node --test webapp/frontend/tests/lastSeen.test.mjs (Node 22.6+ strips the .ts types natively).
import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

class MemStorage {
  constructor() { this.m = new Map() }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null }
  setItem(k, v) { this.m.set(k, String(v)) }
}
globalThis.window = { localStorage: new MemStorage() }
const { takeLastSeen, isNewSince } = await import('../lib/lastSeen.ts')

beforeEach(() => { globalThis.window.localStorage = new MemStorage() })

test('first visit returns null, next visit returns the previous stamp', () => {
  assert.equal(takeLastSeen('a', 1000), null)
  assert.equal(takeLastSeen('a', 2000), 1000)
  assert.equal(takeLastSeen('a', 3000), 2000)
})

test('per user id', () => {
  takeLastSeen('a', 1000)
  assert.equal(takeLastSeen('b', 2000), null)
  assert.equal(takeLastSeen(null, 2000), null)
})

test('garbage or future stored value counts as first visit', () => {
  for (const raw of ['x', '-5', '', '99999']) {
    globalThis.window.localStorage.setItem('cw.digest.lastSeen.v1:a', raw)
    assert.equal(takeLastSeen('a', 5000), null)
  }
})

test('throwing storage disables the feature', () => {
  globalThis.window.localStorage = { getItem() { throw new Error('denied') }, setItem() { throw new Error('denied') } }
  assert.equal(takeLastSeen('a', 1000), null)
})

test('isNewSince', () => {
  const prev = Date.parse('2026-10-12T10:00:00Z')
  assert.equal(isNewSince('2026-10-12T11:00:00Z', prev), true)
  assert.equal(isNewSince('2026-10-12T10:00:00Z', prev), false)
  assert.equal(isNewSince('2026-10-12T09:00:00Z', prev), false)
  assert.equal(isNewSince('2026-10-12T11:00:00Z', null), false)
  assert.equal(isNewSince('bad', prev), false)
  assert.equal(isNewSince(null, prev), false)
})
