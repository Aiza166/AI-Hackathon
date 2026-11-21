// Unit tests for the offline "who am I" cache (bug B4). Run: npm run test:unit
import assert from 'node:assert/strict'
import { beforeEach, test } from 'node:test'
import { clearMe, loadMe, saveMe } from '../src/lib/meCache.ts'

class MemoryStorage {
  private items = new Map<string, string>()
  getItem(key: string): string | null { return this.items.get(key) ?? null }
  setItem(key: string, value: string): void { this.items.set(key, value) }
  removeItem(key: string): void { this.items.delete(key) }
  raw(): string { return [...this.items.values()].join('') }
}

let store: MemoryStorage
const ZAINAB = { id: 'u-1', role: 'citizen' as const, name: 'Zainab Bibi', person: { id: 'p-1', cnic: '9000000000022', name: 'Zainab Bibi' } }

beforeEach(() => {
  store = new MemoryStorage()
  Object.defineProperty(globalThis, 'sessionStorage', { value: store, configurable: true })
})

test('returns the cached profile to the same user after a reload', () => {
  saveMe('u-1', ZAINAB)
  assert.deepEqual(loadMe('u-1'), ZAINAB)
})

test('never returns one user\'s profile to another user on a shared phone', () => {
  saveMe('u-1', ZAINAB)
  assert.equal(loadMe('u-2'), null)
})

test('refuses to cache a profile that is not the signed-in user', () => {
  saveMe('u-2', ZAINAB)
  assert.equal(loadMe('u-2'), null)
})

test('keeps only the fields the home screen needs', () => {
  saveMe('u-1', { ...ZAINAB, phone: '00000000001', token: 'secret' } as typeof ZAINAB)
  assert.ok(!store.raw().includes('secret'))
  assert.ok(!store.raw().includes('00000000001'))
})

test('ignores corrupted or tampered entries', () => {
  store.setItem('sahara.me.v1', '{not json')
  assert.equal(loadMe('u-1'), null)
  store.setItem('sahara.me.v1', JSON.stringify({ userId: 'u-1', me: { id: 'u-1', role: 'citizen', person: { cnic: 5 } } }))
  assert.equal(loadMe('u-1'), null)
})

test('sign-out clears the cache', () => {
  saveMe('u-1', ZAINAB)
  clearMe()
  assert.equal(loadMe('u-1'), null)
})

test('works (returns nothing) when storage is blocked', () => {
  Object.defineProperty(globalThis, 'sessionStorage', { get() { throw new Error('blocked') }, configurable: true })
  saveMe('u-1', ZAINAB)
  assert.equal(loadMe('u-1'), null)
})
