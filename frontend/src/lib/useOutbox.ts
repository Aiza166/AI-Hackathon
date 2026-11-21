import { useCallback, useEffect, useRef, useState } from 'react'
import { flush, listRows, MAX_AUTO_ATTEMPTS, OUTBOX_CHANGED, removeRow, type OutboxRow } from './outbox'

// Tracks claims saved on the phone but not yet sent, and sends them on app open, on
// reconnect (the browser's "online" event), when a backoff timer is due, or with "Send now".
// `subject` limits everything to one family (Helper Mode); null = no family chosen, show nothing.

export interface DuplicateNotice {
  reference: string | null
  subjectName: string
}

export interface OutboxState {
  queued: OutboxRow[]
  failed: OutboxRow[]
  needsLogin: boolean
  paused: boolean // automatic tries stopped after repeated server errors; "Send now" still works
  online: boolean
  syncing: boolean
  notices: DuplicateNotice[]
  sendNow: () => Promise<void>
  dismissNotice: (notice: DuplicateNotice) => void
  remove: (row: OutboxRow) => Promise<void>
}

const MIN_TIMER_MS = 1_000
const TIMER_MARGIN_MS = 250 // fire just after the row is due, never just before

export function useOutbox(owner: string, subject: string | null | undefined, onSent: () => void): OutboxState {
  const [rows, setRows] = useState<OutboxRow[]>([])
  const [online, setOnline] = useState(() => navigator.onLine)
  const [syncing, setSyncing] = useState(false)
  const [notices, setNotices] = useState<DuplicateNotice[]>([])
  const onSentRef = useRef(onSent)
  useEffect(() => {
    onSentRef.current = onSent
  }, [onSent])

  const refresh = useCallback(async () => {
    const all = subject === null ? [] : await listRows(owner)
    setRows(subject === undefined ? all : all.filter((r) => r.subject === subject))
  }, [owner, subject])

  const send = useCallback(
    async (force: boolean) => {
      if (subject === null) return
      setSyncing(true)
      try {
        const summary = await flush(owner, subject, force)
        if (summary.duplicates.length > 0) setNotices((current) => [...current, ...summary.duplicates])
        if (summary.sent > 0 || summary.duplicates.length > 0) onSentRef.current()
      } finally {
        setSyncing(false)
        await refresh()
      }
    },
    [owner, subject, refresh],
  )

  useEffect(() => {
    const goOnline = () => {
      setOnline(true)
      void send(false)
    }
    const goOffline = () => setOnline(false)
    const changed = () => void refresh()
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    window.addEventListener(OUTBOX_CHANGED, changed)
    // Something may be waiting from an earlier visit. Check after the first paint; the database
    // (Dexie, its own chunk) is only loaded when the phone has something stored.
    const firstCheck = window.setTimeout(() => void (navigator.onLine ? send(false) : refresh()), 0)
    return () => {
      window.clearTimeout(firstCheck)
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
      window.removeEventListener(OUTBOX_CHANGED, changed)
    }
  }, [send, refresh])

  const queued = rows.filter((r) => r.status === 'queued')
  const failed = rows.filter((r) => r.status === 'failed')
  const needsLogin = queued.some((r) => r.needsLogin)
  const retryable = queued.filter((r) => !r.needsLogin && r.attempts < MAX_AUTO_ATTEMPTS)
  const paused = queued.length > 0 && !needsLogin && retryable.length === 0
  const nextDue = retryable.reduce((min, r) => Math.min(min, r.nextAttemptAt), Infinity)

  // Retry after the backoff delay of the earliest row (server errors only).
  useEffect(() => {
    if (!online || !Number.isFinite(nextDue) || nextDue === 0) return
    const timer = window.setTimeout(() => void send(false), Math.max(nextDue - Date.now() + TIMER_MARGIN_MS, MIN_TIMER_MS))
    return () => window.clearTimeout(timer)
  }, [online, nextDue, send])

  const dismissNotice = useCallback((notice: DuplicateNotice) => setNotices((current) => current.filter((n) => n !== notice)), [])
  const remove = useCallback(async (row: OutboxRow) => {
    await removeRow(row)
  }, [])

  return { queued, failed, needsLogin, paused, online, syncing, notices, sendNow: () => send(true), dismissNotice, remove }
}
