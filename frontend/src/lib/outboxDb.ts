import Dexie, { type Table } from 'dexie'
import type { Sealed } from './outboxCrypto'

// The only module that imports Dexie. It is loaded with a dynamic import (see outbox.ts),
// so Dexie lives in its own chunk and never weighs down the first screen.
// Everything here is PROTOTYPE mock data, encrypted at rest; rows are scoped to the signed-in user (owner)
// and deleted on sign-out. Drafts older than 7 days are dropped when the database opens.

export interface SavedDraft {
  step: number
  data: unknown
}

// What the app works with (decrypted in memory).
export interface OutboxRow {
  id: string // UUID made when the user tapped Send; sent as the Idempotency-Key header on every attempt
  owner: string // signed-in user id
  subject: string // claimant CNIC (Helper Mode: which family this claim is for)
  subjectName: string
  draftKey: string // the draft is kept until this row is confirmed sent
  draft: SavedDraft | null // wizard state at Send, restored if the server refuses the claim
  path: string
  body: unknown
  createdAt: number
  attempts: number // server errors only; drives the backoff and the auto-retry cap
  nextAttemptAt: number
  lastError: string | null
  needsLogin: boolean // the session ended (401): kept until the user signs in again
  status: 'queued' | 'failed' // failed = refused by the server (4xx), waiting for "Open and fix"
}

// The private parts of a row, stored only encrypted (see outboxCrypto.ts).
export interface OutboxSecret {
  subject: string
  subjectName: string
  draft: SavedDraft | null
  body: unknown
}

// What IndexedDB holds: personal data only as AES-GCM ciphertext; the CNIC only masked.
export interface StoredDraft {
  key: string // `${owner}:${blind id of the claimant CNIC}`
  owner: string
  updatedAt: number
  sealed: Sealed // SavedDraft
}

export interface StoredOutbox extends Omit<OutboxRow, 'subject' | 'subjectName' | 'draft' | 'body'> {
  subjectMask: string // ****1234, for nothing but debugging
  sealed: Sealed // OutboxSecret
}

class SaharaDb extends Dexie {
  drafts!: Table<StoredDraft, string>
  outbox!: Table<StoredOutbox, string>

  constructor() {
    super('sahara-offline')
    this.version(1).stores({
      drafts: 'key, owner',
      outbox: 'id, owner, createdAt',
    })
    // v2: rows are encrypted. Version 1 rows were plain text: delete them on upgrade.
    this.version(2)
      .stores({ drafts: 'key, owner', outbox: 'id, owner, createdAt' })
      .upgrade(async (tx) => {
        await tx.table('drafts').clear()
        await tx.table('outbox').clear()
      })
  }
}

export const db = new SaharaDb()
