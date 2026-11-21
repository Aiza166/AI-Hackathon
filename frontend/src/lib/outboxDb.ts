import Dexie, { type Table } from 'dexie'

// The only module that imports Dexie. It is loaded with a dynamic import (see outbox.ts),
// so Dexie lives in its own chunk and never weighs down the first screen.
// Everything here is PROTOTYPE mock data; rows are scoped to the signed-in user (owner)
// and deleted on sign-out. Drafts older than 7 days are dropped when the database opens.

export interface SavedDraft {
  step: number
  data: unknown
}

export interface DraftRow extends SavedDraft {
  key: string // `${owner}:${claimantCnic}`
  owner: string
  updatedAt: number
}

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

class SaharaDb extends Dexie {
  drafts!: Table<DraftRow, string>
  outbox!: Table<OutboxRow, string>

  constructor() {
    super('sahara-offline')
    this.version(1).stores({
      drafts: 'key, owner',
      outbox: 'id, owner, createdAt',
    })
  }
}

export const db = new SaharaDb()
