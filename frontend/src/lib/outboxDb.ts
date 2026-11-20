import Dexie, { type Table } from 'dexie'

// The only module that imports Dexie. It is loaded with a dynamic import (see outbox.ts),
// so Dexie lives in its own chunk and never weighs down the first screen.
// Everything here is PROTOTYPE mock data; rows are scoped to the signed-in user (owner).

export interface DraftRow {
  key: string // `${owner}:${claimantCnic}`
  owner: string
  step: number
  data: unknown
  updatedAt: number
}

export interface OutboxRow {
  id: string // idempotency key, sent as the Idempotency-Key header
  owner: string
  path: string
  body: unknown
  createdAt: number
  attempts: number
  lastError: string | null
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
