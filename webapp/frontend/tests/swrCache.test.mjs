// Run: node --test webapp/frontend/tests/swrCache.test.mjs (Node 22.6+ strips the .ts types natively).
import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'

class MemStorage {
  constructor() { this.m = new Map() }
  get length() { return this.m.size }
  key(i) { return [...this.m.keys()][i] ?? null }
  getItem(k) { return this.m.has(k) ? this.m.get(k) : null }
  setItem(k, v) { this.m.set(k, String(v)) }
  removeItem(k) { this.m.delete(k) }
}
globalThis.window = { localStorage: new MemStorage() }
const ls = () => globalThis.window.localStorage
const { readCache, writeCache, clearSwrCache } = await import('../lib/swrCache.ts')

const OPTS = { userId: 'a', version: 1, maxAgeMs: 60_000 }
beforeEach(() => { globalThis.window.localStorage = new MemStorage() })

test('round trip', () => {
  writeCache('jobs', [{ id: 1 }], OPTS)
  assert.deepEqual(readCache('jobs', OPTS), [{ id: 1 }])
})

test('other user never sees the entry', () => {
  writeCache('jobs', [1], OPTS)
  assert.equal(readCache('jobs', { ...OPTS, userId: 'b' }), null)
  assert.equal(readCache('jobs', { ...OPTS, userId: null }), null)
})

test('userId mismatch inside payload is dropped', () => {
  ls().setItem('cw:swr:jobs:a', JSON.stringify({ v: 1, savedAt: Date.now(), userId: 'b', data: [1] }))
  assert.equal(readCache('jobs', OPTS), null)
  assert.equal(ls().getItem('cw:swr:jobs:a'), null)
})

test('version mismatch is dropped', () => {
  writeCache('jobs', [1], OPTS)
  assert.equal(readCache('jobs', { ...OPTS, version: 2 }), null)
  assert.equal(ls().length, 0)
})

test('too old or future savedAt is dropped', () => {
  ls().setItem('cw:swr:jobs:a', JSON.stringify({ v: 1, savedAt: Date.now() - 120_000, userId: 'a', data: [1] }))
  assert.equal(readCache('jobs', OPTS), null)
  ls().setItem('cw:swr:jobs:a', JSON.stringify({ v: 1, savedAt: Date.now() + 120_000, userId: 'a', data: [1] }))
  assert.equal(readCache('jobs', OPTS), null)
})

test('corrupt / legacy entries do not throw', () => {
  for (const raw of ['{not json', 'null', '42', '"x"', '{}', '[]']) {
    ls().setItem('cw:swr:jobs:a', raw)
    assert.equal(readCache('jobs', OPTS), null)
  }
})

test('throwing storage is survived', () => {
  globalThis.window.localStorage = {
    getItem() { throw new Error('denied') }, setItem() { throw new Error('quota') },
    removeItem() { throw new Error('denied') }, key() { throw new Error('denied') }, length: 1,
  }
  assert.equal(readCache('jobs', OPTS), null)
  writeCache('jobs', [1], OPTS)
  clearSwrCache()
})

test('clearSwrCache removes only cw:swr: keys', () => {
  writeCache('jobs', [1], OPTS)
  writeCache('positions', [1], { ...OPTS, userId: 'b' })
  ls().setItem('cw-theme', 'dark')
  clearSwrCache()
  assert.equal(ls().length, 1)
  assert.equal(ls().getItem('cw-theme'), 'dark')
})
