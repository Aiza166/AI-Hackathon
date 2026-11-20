import { api, ApiError } from '../api/client'
import type { OutboxRow } from './outboxDb'

// Offline-first sending (Challenge 7: weak internet).
// 1. Each claim step is saved on the phone as a draft, so a reload resumes from the same step.
// 2. "Send" first stores the request in the outbox with an idempotency key, then tries to send it.
// 3. If there is no signal it stays queued and is sent on reconnect or with "Send now".
// The server stops a second copy: same Idempotency-Key, and a 409 for an already-open claim.

export const OUTBOX_CHANGED = 'sahara-outbox-changed'

type Db = (typeof import('./outboxDb'))['db']

let dbPromise: Promise<Db | null> | null = null

// Loads Dexie on first use (its own chunk). Resolves null if IndexedDB is not available,
// e.g. some private-browsing modes: the app then sends directly, without offline storage.
function getDb(): Promise<Db | null> {
  dbPromise ??= import('./outboxDb')
    .then(async ({ db }) => {
      await db.open()
      return db
    })
    .catch(() => null)
  return dbPromise
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

export interface Draft<T> {
  step: number
  data: T
}

const draftKey = (owner: string, subject: string) => `${owner}:${subject}`

export async function loadDraft<T>(owner: string, subject: string): Promise<Draft<T> | null> {
  const db = await getDb()
  if (!db) return null
  const row = await db.drafts.get(draftKey(owner, subject)).catch(() => undefined)
  return row ? { step: row.step, data: row.data as T } : null
}

// Best effort: if saving fails the claim still works, it just will not resume after a reload.
export async function saveDraft<T>(owner: string, subject: string, draft: Draft<T>): Promise<boolean> {
  const db = await getDb()
  if (!db) return false
  try {
    await db.drafts.put({ key: draftKey(owner, subject), owner, step: draft.step, data: draft.data, updatedAt: Date.now() })
    return true
  } catch {
    return false
  }
}

export async function clearDraft(owner: string, subject: string): Promise<void> {
  const db = await getDb()
  await db?.drafts.delete(draftKey(owner, subject)).catch(() => undefined)
}

// ---------- outbox ----------

export type SendResult<T> =
  | { kind: 'sent'; data: T }
  | { kind: 'queued'; reason: string } // no signal or server busy: kept, will retry
  | { kind: 'duplicate'; message: string } // the server already has an open claim like this one (409)
  | { kind: 'failed'; message: string } // the server refused it: removed, user must fix and resend

function isRetryable(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return error.status === 0 || error.status === 408 || error.status === 425 || error.status === 429 || error.status >= 500
}

function messageOf(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong'
}

// One sender at a time, so the "online" event and the "Send now" button never send the same row twice.
let lock: Promise<unknown> = Promise.resolve()
function withLock<T>(task: () => Promise<T>): Promise<T> {
  const run = lock.then(task, task)
  lock = run.catch(() => undefined)
  return run
}

async function sendRow<T>(db: Db, row: OutboxRow): Promise<SendResult<T>> {
  try {
    const result = await api<T>(row.path, {
      method: 'POST',
      body: JSON.stringify(row.body),
      headers: { 'Idempotency-Key': row.id },
    })
    await db.outbox.delete(row.id)
    return { kind: 'sent', data: result.data }
  } catch (error) {
    if (isRetryable(error)) {
      await db.outbox.update(row.id, { attempts: row.attempts + 1, lastError: messageOf(error) })
      return { kind: 'queued', reason: messageOf(error) }
    }
    await db.outbox.delete(row.id)
    if (error instanceof ApiError && error.status === 409) return { kind: 'duplicate', message: messageOf(error) }
    return { kind: 'failed', message: messageOf(error) }
  }
}

// Store the request on the phone first, then try to send it right away.
export async function submit<T>(owner: string, path: string, body: unknown): Promise<SendResult<T>> {
  const id = newIdempotencyKey()
  const db = await getDb()
  if (!db) {
    // No offline storage: plain send, still with an idempotency key.
    try {
      const result = await api<T>(path, { method: 'POST', body: JSON.stringify(body), headers: { 'Idempotency-Key': id } })
      return { kind: 'sent', data: result.data }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) return { kind: 'duplicate', message: messageOf(error) }
      return { kind: 'failed', message: messageOf(error) }
    }
  }
  await db.outbox.put({ id, owner, path, body, createdAt: Date.now(), attempts: 0, lastError: null })
  const result = await withLock(async (): Promise<SendResult<T>> => {
    const row = await db.outbox.get(id)
    if (!row) return { kind: 'duplicate', message: 'This claim was already sent.' } // a sync sent it first
    return sendRow<T>(db, row)
  })
  notifyChanged()
  return result
}

export interface FlushSummary {
  sent: number
  failed: string[]
  remaining: number
}

// Send everything this user has waiting, oldest first. Stops at the first "no signal".
export async function flush(owner: string): Promise<FlushSummary> {
  const db = await getDb()
  if (!db) return { sent: 0, failed: [], remaining: 0 }
  const summary = await withLock(async (): Promise<FlushSummary> => {
    const rows = await db.outbox.where('owner').equals(owner).sortBy('createdAt')
    let sent = 0
    const failed: string[] = []
    for (const row of rows) {
      const result = await sendRow(db, row)
      if (result.kind === 'sent' || result.kind === 'duplicate') sent += 1
      else if (result.kind === 'failed') failed.push(result.message)
      else break
    }
    const remaining = await db.outbox.where('owner').equals(owner).count()
    return { sent, failed, remaining }
  })
  notifyChanged()
  return summary
}

export async function pendingCount(owner: string): Promise<number> {
  const db = await getDb()
  if (!db) return 0
  return db.outbox.where('owner').equals(owner).count().catch(() => 0)
}
