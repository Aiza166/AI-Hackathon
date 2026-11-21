// Unit tests for the citizen language choice (Urdu default, Sindhi, Punjabi). Run: npm run test:unit
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'
import pa from '../src/i18n/pa.ts'
import sd from '../src/i18n/sd.ts'
import { LANG_STORAGE_KEY, LANGS, localText, parseLang, readStoredLang, storeLang, tagFor } from '../src/lib/lang.ts'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const EXPLANATIONS = path.resolve(HERE, '../../backend/app/decision/explanations.py')

class MemoryStorage {
  private items = new Map<string, string>()
  getItem(key: string): string | null { return this.items.get(key) ?? null }
  setItem(key: string, value: string): void { this.items.set(key, value) }
}

class BrokenStorage {
  getItem(): string | null { throw new Error('blocked') }
  setItem(): void { throw new Error('blocked') }
}

test('Urdu is the default and anything unknown falls back to it', () => {
  assert.equal(parseLang(null), 'ur')
  assert.equal(parseLang('en'), 'ur')
  assert.equal(parseLang('sd'), 'sd')
  assert.equal(parseLang('pa'), 'pa')
  assert.equal(LANGS[0].id, 'ur')
})

test('the choice is remembered on the phone', () => {
  const store = new MemoryStorage()
  assert.equal(readStoredLang(store), 'ur')
  storeLang('sd', store)
  assert.equal(store.getItem(LANG_STORAGE_KEY), 'sd')
  assert.equal(readStoredLang(store), 'sd')
})

test('blocked storage (private mode) never breaks the screen: Urdu, not remembered', () => {
  const broken = new BrokenStorage()
  assert.equal(readStoredLang(broken), 'ur')
  assert.doesNotThrow(() => storeLang('pa', broken))
})

test('a missing line shows the Urdu text with an Urdu lang tag', () => {
  assert.deepEqual(localText('sd', sd, 'no.such.key', 'اردو متن'), { text: 'اردو متن', tag: 'ur' })
  assert.deepEqual(localText('sd', null, 'prompt_dob', 'اردو'), { text: 'اردو', tag: 'ur' })
  assert.deepEqual(localText('ur', sd, 'prompt_dob', 'اردو'), { text: 'اردو', tag: 'ur' })
})

test('a translated line carries its own lang tag (Sindhi sd, Punjabi pa-Arab)', () => {
  assert.deepEqual(localText('sd', sd, 'prompt_dob', 'x'), { text: sd.prompt_dob, tag: 'sd' })
  assert.deepEqual(localText('pa', pa, 'prompt_dob', 'x'), { text: pa.prompt_dob, tag: 'pa-Arab' })
  assert.equal(tagFor('ur'), 'ur')
})

test('Sindhi and Punjabi packs have exactly the same keys', () => {
  assert.deepEqual(Object.keys(pa).sort(), Object.keys(sd).sort())
})

test('every reason code the backend can send has a Sindhi and a Punjabi line', () => {
  const src = fs.readFileSync(EXPLANATIONS, 'utf8')
  const codes = [...src.matchAll(/ReasonCode\.([A-Z_]+):\s*\(/g)].map((m) => m[1])
  assert.ok(codes.length >= 20, `expected the reason table, found ${codes.length} codes`)
  for (const code of codes) {
    assert.ok(sd[`reason.${code}`], `Sindhi is missing reason.${code}`)
    assert.ok(pa[`reason.${code}`], `Punjabi is missing reason.${code}`)
  }
})

test('every line is non-empty Arabic-script text and never says "fake" or "forged"', () => {
  const arabic = /[؀-ۿ]/
  for (const [name, pack] of [['sd', sd], ['pa', pa]] as const) {
    for (const [key, value] of Object.entries(pack)) {
      assert.ok(value.trim().length > 0, `${name} ${key} is empty`)
      assert.ok(arabic.test(value), `${name} ${key} is not in Arabic script`)
      assert.doesNotMatch(value, /fake|forged/i, `${name} ${key}`)
    }
  }
})

test('Sindhi uses its own letters, so it is not just Urdu copied', () => {
  const sindhiOnly = /[ڪٿڄڏٻڌڇڃڙڳڱ]/
  const withSindhiLetters = Object.values(sd).filter((v) => sindhiOnly.test(v)).length
  assert.ok(withSindhiLetters >= Object.keys(sd).length / 2, `only ${withSindhiLetters} Sindhi lines use Sindhi letters`)
})
