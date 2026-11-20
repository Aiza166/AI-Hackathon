import { useCallback, useEffect, useRef, useState } from 'react'
import { flush, OUTBOX_CHANGED, pendingCount } from './outbox'

// Tracks claims saved on the phone but not yet sent, and sends them
// on reconnect (the browser's "online" event), on first load, or with "Send now".

export interface OutboxState {
  pending: number
  online: boolean
  syncing: boolean
  failed: string[]
  sendNow: () => Promise<void>
}

export function useOutbox(owner: string, onSent: () => void): OutboxState {
  const [pending, setPending] = useState(0)
  const [online, setOnline] = useState(() => navigator.onLine)
  const [syncing, setSyncing] = useState(false)
  const [failed, setFailed] = useState<string[]>([])
  const onSentRef = useRef(onSent)
  useEffect(() => {
    onSentRef.current = onSent
  }, [onSent])

  const sendNow = useCallback(async () => {
    setSyncing(true)
    try {
      const summary = await flush(owner)
      setPending(summary.remaining)
      setFailed(summary.failed)
      if (summary.sent > 0) onSentRef.current()
    } finally {
      setSyncing(false)
    }
  }, [owner])

  useEffect(() => {
    let active = true
    const refresh = () => {
      void pendingCount(owner).then((n) => {
        if (active) setPending(n)
      })
    }
    const goOnline = () => {
      setOnline(true)
      void sendNow()
    }
    const goOffline = () => setOnline(false)
    window.addEventListener('online', goOnline)
    window.addEventListener('offline', goOffline)
    window.addEventListener(OUTBOX_CHANGED, refresh)
    // Something may be waiting from an earlier visit. Check after the first paint, so the
    // home screen shows at once and Dexie (its own chunk) loads in the background.
    const firstCheck = window.setTimeout(() => {
      if (navigator.onLine) void sendNow()
      else refresh()
    }, 0)
    return () => {
      active = false
      window.clearTimeout(firstCheck)
      window.removeEventListener('online', goOnline)
      window.removeEventListener('offline', goOffline)
      window.removeEventListener(OUTBOX_CHANGED, refresh)
    }
  }, [owner, sendNow])

  return { pending, online, syncing, failed, sendNow }
}
