import { api, ApiError } from '../api/client'
import type { OutboxRow, SavedDraft } from './outboxDb'

// Offline-first sending (Challenge 7: weak internet).
// 1. Each claim step is saved on the phone as a draft, so a reload resumes from the same step.
// 2. "Send" stores the request in the outbox under a UUID made when the user taps Send, and
//    tries to send it at once. The same UUID goes out as the Idempotency-Key header on every
//    attempt, so a resend can never file the claim twice.
// 3. With no signal it stays queued and is sent on app open, on reconnect or with "Send now".
// Server side, POST /api/v1/cases honours Idempotency-Key (IETF draft): the same key with the
// same body replays the first response, a changed body gets 422, a request still in flight
// gets 409. A second open claim for the same deceased person is refused with 409 + reference.
// The draft is kept until the queued claim is confirmed sent.

export type { OutboxRow } from './outboxDb'

export const OUTBOX_CHANGED = 'sahara-outbox-changed'
// '1' while drafts or queued claims exist on this phone. Lets the home screen skip loading
// Dexie (its own chunk) when there is nothing stored. Holds no personal data.
const LOCAL_FLAG = 'sahara.offline'
const DRAFT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000
export const MAX_AUTO_ATTEMPTS = 6 // after this, only "Send now" retries
const BASE_DELAY_MS = 5_000
const MAX_DELAY_MS = 5 * 60_000
const CONSENT_REFUSED = 'has not shared'
const REFERENCE = /\b(SP-\d+)\b/

type Db = (typeof import('./outboxDb'))['db']

let dbPromise: Promise<Db | null> | null = null

function readFlag(): boolean {
  try {
    return localStorage.getItem(LOCAL_FLAG) === '1'
  } catch {
    return true // storage blocked: assume something may be stored and look
  }
}

function writeFlag(on: boolean): void {
  try {
    if (on) localStorage.setItem(LOCAL_FLAG, '1')
    else localStorage.removeItem(LOCAL_FLAG)
  } catch {
    // Storage blocked: the flag is only an optimisation.
  }
}

async function refreshFlag(db: Db): Promise<void> {
  const stored = (await db.outbox.count()) + (await db.drafts.count())
  writeFlag(stored > 0)
}

// Loads Dexie on first use (its own chunk). Resolves null if IndexedDB is not available,
// e.g. some private-browsing modes: the app then sends directly, without offline storage.
function getDb(): Promise<Db | null> {
  dbPromise ??= import('./outboxDb')
    .then(async ({ db }) => {
      await db.open()
      // Ask the browser not to evict our data under storage pressure. The answer does not matter.
      void navigator.storage?.persist?.().catch(() => undefined)
      // Drafts hold personal details on a shared phone: drop any older than 7 days.
      const cutoff = Date.now() - DRAFT_MAX_AGE_MS
      await db.drafts.filter((d) => d.updatedAt < cutoff).delete()
      await refreshFlag(db)
      return db
    })
    .catch(() => null)
  return dbPromise
}

// Opens the database only if something may be stored. Used by the home screen and sign-out.
function storedDb(): Promise<Db | null> {
  return readFlag() ? getDb() : Promise.resolve(null)
}

function notifyChanged(): void {
  window.dispatchEvent(new Event(OUTBOX_CHANGED))
}

export function newIdempotencyKey(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID()
  // Fallback for non-secure contexts (plain http on a LAN): random v4-style id.
  const bytes = crypto.getRandomValues(new Uint8Array(16))
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}

// ---------- drafts ----------

export const makeDraftKey = (owner: string, subject: string) => `${owner}:${subject}`

// The data comes back as unknown: the caller checks its shape before using it.
export async function loadDraft(owner: string, subject: string): Promise<SavedDraft | null> {
  const db = await getDb()
  if (!db) return null
  const row = await db.drafts.get(makeDraftKey(owner, subject)).catch(() => undefined)
  return row ? { step: row.step, data: row.data } : null
}

// Best effort: if saving fails the claim still works, it just will not resume after a reload.
export async function saveDraft(owner: string, subject: string, draft: SavedDraft): Promise<boolean> {
  const db = await getDb()
  if (!db) return false
  try {
    await db.drafts.put({ key: makeDraftKey(owner, subject), owner, step: draft.step, data: draft.data, updatedAt: Date.now() })
    writeFlag(true)
    return true
  } catch {
    return false
  }
}

export async function clearDraft(owner: string, subject: string): Promise<void> {
  const db = await storedDb()
  if (!db) return
  await db.drafts.delete(makeDraftKey(owner, subject)).catch(() => undefined)
  await refreshFlag(db)
}

// Sign-out on a shared phone: remove everything this user left here.
export async function clearOwnerData(owner: string): Promise<void> {
  const db = await storedDb()
  if (!db) return
  await db.drafts.where('owner').equals(owner).delete()
  await db.outbox.where('owner').equals(owner).delete()
  await refreshFlag(db)
  notifyChanged()
}

// ---------- outbox ----------

export interface SubmitRequest {
  owner: string
  subject: string // claimant CNIC: Helper Mode keeps each family's claims apart
  subjectName: string
  path: string
  body: unknown
  draft: SavedDraft | null // restored into the drafts table if the server refuses the claim
}

export type SendResult<T> =
  | { kind: 'sent'; data: T }
  | { kind: 'queued'; why: 'offline' | 'login' | 'server' } // kept, will retry
  | { kind: 'duplicate'; message: string; reference: string | null } // already filed (409)
  | { kind: 'failed'; message: string; rowId: string | null } // refused: kept as "failed" so it can be fixed

type Verdict = 'offline' | 'login' | 'server' | 'duplicate' | 'final'

function verdictFor(error: unknown): Verdict {
  if (!(error instanceof ApiError) || error.status === 0) return 'offline'
  const { status, message } = error
  if (status === 401) return 'login'
  if (status === 409) return REFERENCE.test(message) ? 'duplicate' : 'server' // no reference = still in flight
  if (status === 408 || status === 425 || status === 429 || status >= 500) return 'server'
  return 'final' // 400, 403, 404, 422 ...: the claim itself must be fixed
}

export function isConsentProblem(row: OutboxRow): boolean {
  return row.status === 'failed' && (row.lastError ?? '').includes(CONSENT_REFUSED)
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

function backoff(attempts: number): number {
  return Math.min(BASE_DELAY_MS * 2 ** attempts, MAX_DELAY_MS)
}

// One sender at a time, in this tab and across tabs (Web Locks where available), so app open,
// the "online" event, "Send now" and a fresh "Send" never send the same row at the same moment.
let tabLock: Promise<unknown> = Promise.resolve()
function withLock<T>(task: () => Promise<T>): Promise<T> {
  const locked = (): Promise<T> =>
    typeof navigator !== 'undefined' && navigator.locks ? navigator.locks.request('sahara-outbox', task) : task()
  const run = tabLock.then(locked, locked)
  tabLock = run.catch(() => undefined)
  return run
}

async function settleSent(db: Db, row: OutboxRow): Promise<void> {
  await db.outbox.delete(row.id)
  await db.drafts.delete(row.draftKey)
  await refreshFlag(db)
}

async function markFailed(db: Db, row: OutboxRow, message: string): Promise<void> {
  await db.outbox.update(row.id, { status: 'failed', lastError: message, needsLogin: false })
  if (row.draft) {
    // Put the claim back into the wizard so "Open and fix" starts from what was sent.
    await db.drafts.put({ key: row.draftKey, owner: row.owner, step: row.draft.step, data: row.draft.data, updatedAt: Date.now() })
  }
}

async function sendRow<T>(db: Db, row: OutboxRow): Promise<SendResult<T>> {
  try {
    const result = await api<T>(row.path, { method: 'POST', body: JSON.stringify(row.body), headers: { 'Idempotency-Key': row.id } })
    await settleSent(db, row)
    return { kind: 'sent', data: result.data }
  } catch (error) {
    const message = messageOf(error)
    const verdict = verdictFor(error)
    switch (verdict) {
      case 'offline':
        await db.outbox.update(row.id, { lastError: message })
        return { kind: 'queued', why: 'offline' }
      case 'login':
        // Never drop a claim because the session ended: keep it until the user signs in again.
        await db.outbox.update(row.id, { needsLogin: true, lastError: message })
        return { kind: 'queued', why: 'login' }
      case 'server': {
        const attempts = row.attempts + 1
        await db.outbox.update(row.id, { attempts, nextAttemptAt: Date.now() + backoff(attempts), lastError: message, needsLogin: false })
        return { kind: 'queued', why: 'server' }
      }
      case 'duplicate':
        await settleSent(db, row)
        return { kind: 'duplicate', message, reference: message.match(REFERENCE)?.[1] ?? null }
      case 'final':
        await markFailed(db, row, message)
        return { kind: 'failed', message, rowId: row.id }
    }
  }
}

async function sendWithoutStorage<T>(id: string, req: SubmitRequest): Promise<SendResult<T>> {
  try {
    const result = await api<T>(req.path, { method: 'POST', body: JSON.stringify(req.body), headers: { 'Idempotency-Key': id } })
    return { kind: 'sent', data: result.data }
  } catch (error) {
    const message = messageOf(error)
    if (verdictFor(error) === 'duplicate') return { kind: 'duplicate', message, reference: message.match(REFERENCE)?.[1] ?? null }
    return { kind: 'failed', message, rowId: null }
  }
}

// Store the request on the phone, then send it, inside one lock: a sync can never pick the
// row up half-way. Even if another sender got there first, resending with the same key makes
// the server replay its first answer, so the user always sees the real result.
export async function submit<T>(req: SubmitRequest): Promise<SendResult<T>> {
  const id = newIdempotencyKey()
  const db = await getDb()
  if (!db) return sendWithoutStorage<T>(id, req)
  const row: OutboxRow = {
    id, owner: req.owner, subject: req.subject, subjectName: req.subjectName, draftKey: makeDraftKey(req.owner, req.subject),
    draft: req.draft, path: req.path, body: req.body, createdAt: Date.now(), attempts: 0, nextAttemptAt: 0,
    lastError: null, needsLogin: false, status: 'queued',
  }
  const result = await withLock(async () => {
    await db.outbox.put(row)
    writeFlag(true)
    return sendRow<T>(db, row)
  })
  notifyChanged()
  return result
}

export interface FlushSummary {
  sent: number
  duplicates: { reference: string | null; subjectName: string }[]
}

// Send this user's queued claims, oldest first. `subject` limits it to one family (Helper Mode).
// Automatic flushes respect the backoff and the attempt cap; "Send now" (force) ignores both.
export async function flush(owner: string, subject: string | undefined, force: boolean): Promise<FlushSummary> {
  const db = await storedDb()
  const summary: FlushSummary = { sent: 0, duplicates: [] }
  if (!db) return summary
  await withLock(async () => {
    const rows = await db.outbox.where('owner').equals(owner).sortBy('createdAt')
    const now = Date.now()
    for (const row of rows) {
      if (row.status !== 'queued' || (subject !== undefined && row.subject !== subject)) continue
      if (!force && (row.attempts >= MAX_AUTO_ATTEMPTS || row.nextAttemptAt > now)) continue
      const result = await sendRow(db, row)
      if (result.kind === 'sent') summary.sent += 1
      else if (result.kind === 'duplicate') summary.duplicates.push({ reference: result.reference, subjectName: row.subjectName })
      else if (result.kind === 'queued' && result.why !== 'server') break // no signal or signed out: the rest would fail too
    }
  })
  notifyChanged()
  return summary
}

export async function listRows(owner: string): Promise<OutboxRow[]> {
  const db = await storedDb()
  if (!db) return []
  return db.outbox.where('owner').equals(owner).sortBy('createdAt').catch(() => [])
}

// Every claim this user has not got onto the server yet (queued or refused), for the sign-out warning.
export async function unsentCount(owner: string): Promise<number> {
  const db = await storedDb()
  if (!db) return 0
  return db.outbox.where('owner').equals(owner).count().catch(() => 0)
}

// "Remove" on a refused claim: the user gives it up, so its saved draft goes too.
export async function removeRow(row: OutboxRow): Promise<void> {
  const db = await storedDb()
  if (!db) return
  await db.outbox.delete(row.id)
  await db.drafts.delete(row.draftKey)
  await refreshFlag(db)
  notifyChanged()
}

// "Open and fix": the claim is already back in the draft, so only the refused row goes.
export async function takeForFixing(rowId: string): Promise<void> {
  const db = await storedDb()
  if (!db) return
  await db.outbox.delete(rowId)
  notifyChanged()
}
