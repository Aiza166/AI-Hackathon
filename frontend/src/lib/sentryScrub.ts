// Scrubber for Sentry events sent from the browser. Mirrors backend/app/core/monitoring.py:
// request bodies and cookies are dropped, the user block keeps only the role, secret-looking keys
// become "[Filtered]", and CNICs, IBANs, phone numbers, PINs, JWTs, bearer tokens and API keys are
// masked in every string. Pure functions with no Sentry import, so they stay out of the main bundle
// path and run under `npm run test:unit`.

export const FILTERED = '[Filtered]'
const MAX_DEPTH = 12
const SENSITIVE_KEY_PARTS = [
  'pin', 'password', 'passwd', 'secret', 'token', 'authorization', 'auth', 'cookie', 'api_key', 'apikey',
  'api-key', 'session', 'refresh', 'otp', 'iban', 'cnic', 'phone', 'idempotency', 'dsn',
]
// Sentry bookkeeping: ids and timestamps are long digit runs that must not be rewritten.
const KEEP_KEYS = new Set(['event_id', 'trace_id', 'span_id', 'parent_span_id', 'timestamp', 'start_timestamp',
  'release', 'sdk', 'platform', 'level', 'lineno', 'colno', 'type'])

const JWT = /eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]*/g
const BEARER = /\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+/gi
const API_KEY = /\bsk_[A-Za-z0-9_-]{8,}/g
const PIN = /\b(pin|password|passcode|otp)(\W{1,4})(\d{4,8})\b/gi
const CNIC = /(?<![0-9A-Za-z])(\d{5}-?\d{7}-?\d)(?![0-9A-Za-z])/g
const IBAN = /(?<![0-9A-Za-z])([A-Z]{2}\d{2}[A-Z0-9]{10,30})(?![0-9A-Za-z])/g
// 10-15 digits with an optional + and dashes or spaces inside (03xx-xxxxxxx, +92 3xx xxxxxxx, demo phones).
const PHONE = /(?<![\w*])(\+?\d(?:[ -]?\d){9,14})(?![\w*])/g

type Json = unknown
type Dict = Record<string, Json>

function keepLast(value: string, keep: number): string {
  return '*'.repeat(Math.max(value.length - keep, 0)) + value.slice(-keep)
}

export function scrubText(value: string): string {
  return value
    .replace(JWT, '[token]')
    .replace(BEARER, (_m, scheme: string) => `${scheme} ${FILTERED}`)
    .replace(API_KEY, '[api-key]')
    .replace(PIN, (_m, word: string, sep: string) => `${word}${sep}****`)
    .replace(CNIC, (_m, v: string) => keepLast(v, 4))
    .replace(IBAN, (_m, v: string) => keepLast(v, 4))
    .replace(PHONE, (_m, v: string) => keepLast(v.replace(/\D/g, ''), 2))
}

function isSensitiveKey(key: string): boolean {
  const lowered = key.toLowerCase()
  return SENSITIVE_KEY_PARTS.some((part) => lowered.includes(part))
}

function isEmpty(value: Json): boolean {
  if (value === null || value === undefined || value === '') return true
  if (Array.isArray(value)) return value.length === 0
  return typeof value === 'object' && Object.keys(value as Dict).length === 0
}

/** Scrubbed deep copy. Never mutates the input. */
export function scrub(value: Json, depth = 0): Json {
  if (depth > MAX_DEPTH) return FILTERED
  if (typeof value === 'string') return scrubText(value)
  if (Array.isArray(value)) {
    if (value.length === 2 && typeof value[0] === 'string' && isSensitiveKey(value[0])) return [value[0], FILTERED]
    return value.map((item) => scrub(item, depth + 1))
  }
  if (value && typeof value === 'object') {
    const out: Dict = {}
    for (const [key, item] of Object.entries(value as Dict)) {
      if (KEEP_KEYS.has(key)) out[key] = item
      else if (isSensitiveKey(key) && !isEmpty(item)) out[key] = FILTERED
      else out[key] = scrub(item, depth + 1)
    }
    return out
  }
  return value
}

export function scrubQuery(query: string): string {
  return query
    .split('&')
    .filter(Boolean)
    .map((pair) => {
      const [rawKey, ...rest] = pair.split('=')
      const key = rawKey ?? ''
      const value = rest.join('=')
      if (isSensitiveKey(safeDecode(key))) return `${key}=${FILTERED}`
      return `${key}=${encodeURIComponent(scrubText(safeDecode(value)))}`
    })
    .join('&')
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value.replace(/\+/g, ' '))
  } catch {
    return value
  }
}

export function scrubUrl(url: string): string {
  const [base, ...rest] = url.split('?')
  const query = rest.join('?')
  return scrubText(base ?? '') + (query ? `?${scrubQuery(query)}` : '')
}

function scrubRequest(request: Dict): Dict {
  const kept: Dict = {}
  for (const [key, value] of Object.entries(request)) {
    if (key === 'data' || key === 'cookies' || key === 'env') continue
    kept[key] = value
  }
  if (typeof kept.url === 'string') kept.url = scrubUrl(kept.url)
  if (typeof kept.query_string === 'string') kept.query_string = scrubQuery(kept.query_string)
  return scrub(kept) as Dict
}

/** beforeSend: returns a scrubbed copy. `role` is the only user field ever sent. */
export function scrubEvent<T extends object>(event: T, role?: string | null): T {
  const source = event as Dict
  const out: Dict = {}
  for (const [key, value] of Object.entries(source)) {
    if (key === 'request' || key === 'user') continue
    out[key] = scrub(value)
  }
  if (source.request && typeof source.request === 'object') out.request = scrubRequest(source.request as Dict)
  out.user = role ? { role } : {}
  return out as T
}

/** beforeBreadcrumb: masks message and data, drops captured bodies. */
export function scrubBreadcrumb<T extends object>(crumb: T): T {
  const source = crumb as Dict
  const out: Dict = {}
  for (const [key, value] of Object.entries(source)) {
    if (key !== 'data') out[key] = scrub(value)
  }
  if (source.data && typeof source.data === 'object') {
    const data: Dict = {}
    for (const [key, value] of Object.entries(source.data as Dict)) {
      if (key === 'body' || key === 'request_body' || key === 'response_body') continue
      data[key] = key === 'url' && typeof value === 'string' ? scrubUrl(value) : value
    }
    out.data = scrub(data)
  }
  return out as T
}
