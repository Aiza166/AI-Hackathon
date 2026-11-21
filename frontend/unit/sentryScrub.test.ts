// Unit tests for the browser Sentry scrubber (mirrors backend tests/test_monitoring.py). Run: npm run test:unit
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { FILTERED, scrubBreadcrumb, scrubEvent, scrubQuery, scrubText, scrubUrl } from '../src/lib/sentryScrub.ts'

const CNIC = '9000000000022'
const CNIC_DASHED = '90000-0000001-1'
const IBAN = 'PK00MOCK0000000000000001'
const PHONE = '00000000001'
const JWT = 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0.c2lnbmF0dXJlLXZhbHVl'
const API_KEY = 'sk_' + 'A1b2C3d4E5f6G7h8I9j0K1l2'
const SECRETS = [CNIC, CNIC_DASHED, IBAN, PHONE, JWT, API_KEY, '1234']

function leaks(payload: unknown): string[] {
  const text = JSON.stringify(payload)
  return SECRETS.filter((s) => text.includes(s))
}

function sampleEvent() {
  return {
    event_id: 'a'.repeat(32),
    timestamp: 1763712000.123,
    message: `claim for ${CNIC} paid to ${IBAN}, phone ${PHONE}, pin 1234`,
    exception: { values: [{ type: 'TypeError', value: `bad cnic ${CNIC_DASHED} token ${JWT}` }] },
    request: {
      url: `https://app.example/claim/${CNIC}?cnic=${CNIC}&step=2`,
      query_string: `cnic=${CNIC}&token=${JWT}`,
      headers: { Authorization: `Bearer ${JWT}`, 'User-Agent': 'test' },
      data: { pin: '1234', claimant_cnic: CNIC },
      cookies: { session: 'abc' },
    },
    user: { id: 'u-1', name: 'Zainab Bibi', ip_address: '10.0.0.1', role: 'citizen' },
    extra: { note: `api key ${API_KEY}`, nested: [{ phone: PHONE }, `Bearer ${JWT}`] },
    breadcrumbs: [{ message: `fetch /api/v1/mock/${CNIC}`, data: { url: `/x?iban=${IBAN}` } }],
  }
}

test('scrubbed event carries no CNIC, IBAN, PIN, phone or token', () => {
  assert.deepEqual(leaks(scrubEvent(sampleEvent(), 'citizen')), [])
})

test('request body and cookies are dropped, auth header filtered', () => {
  const request = scrubEvent(sampleEvent()).request as Record<string, unknown>
  assert.equal('data' in request, false)
  assert.equal('cookies' in request, false)
  const headers = request.headers as Record<string, string>
  assert.equal(headers.Authorization, FILTERED)
  assert.equal(headers['User-Agent'], 'test')
})

test('user fields except role are dropped', () => {
  assert.deepEqual(scrubEvent(sampleEvent(), 'citizen').user, { role: 'citizen' })
  assert.deepEqual(scrubEvent(sampleEvent(), null).user, {})
})

test('ids and timestamps are kept as they are', () => {
  const out = scrubEvent(sampleEvent())
  assert.equal(out.event_id, 'a'.repeat(32))
  assert.equal(out.timestamp, 1763712000.123)
})

test('input event is not mutated', () => {
  const event = sampleEvent()
  const before = JSON.stringify(event)
  scrubEvent(event, 'citizen')
  assert.equal(JSON.stringify(event), before)
})

test('each identifier is masked in free text', () => {
  const samples = [`cnic ${CNIC}`, `cnic ${CNIC_DASHED}`, `iban ${IBAN}`, `call ${PHONE}`, 'call 0300-1234567',
    'call +92 300 1234567', 'PIN: 1234', 'password=987654', `Authorization: Bearer ${JWT}`, `key ${API_KEY}`]
  for (const raw of samples) {
    const out = scrubText(raw)
    assert.ok(out.replace(/\D/g, '').length <= 4, `${raw} -> ${out}`)
    assert.ok(!out.includes(JWT) && !out.includes(API_KEY), out)
  }
})

test('ordinary text is left alone', () => {
  assert.equal(scrubText('Rule v1 decided ASK_PROOF in 120 ms'), 'Rule v1 decided ASK_PROOF in 120 ms')
})

test('query strings keep keys and mask values', () => {
  const query = scrubQuery(`cnic=${CNIC}&token=${JWT}&step=2`)
  assert.ok(query.includes('step=2'))
  assert.deepEqual(leaks(query), [])
  assert.deepEqual(leaks(scrubUrl(`/claim/${CNIC}?iban=${IBAN}`)), [])
})

test('breadcrumbs drop bodies and mask url and message', () => {
  const crumb = scrubBreadcrumb({ message: `lookup ${CNIC}`, category: 'fetch',
    data: { url: `https://x/mock/${CNIC}?iban=${IBAN}`, body: 'pin=1234', method: 'GET' } })
  assert.deepEqual(leaks(crumb), [])
  const data = crumb.data as Record<string, unknown>
  assert.equal('body' in data, false)
  assert.equal(data.method, 'GET')
})
