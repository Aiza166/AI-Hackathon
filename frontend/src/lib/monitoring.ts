// Error monitoring, kept off the critical path. Nothing happens unless VITE_SENTRY_DSN was set at
// build time. The Sentry SDK chunk is fetched after the first paint (when the browser is idle), and
// errors caught before it arrives are queued (at most a few) and sent once it is ready.
import type { Capture } from './sentry'

const DSN: string = import.meta.env.VITE_SENTRY_DSN ?? ''
const RELEASE: string | undefined = import.meta.env.VITE_SENTRY_RELEASE || undefined
const ENVIRONMENT: string = import.meta.env.VITE_SENTRY_ENVIRONMENT || (RELEASE ? 'production' : 'local')
const MAX_QUEUED = 5
const IDLE_TIMEOUT_MS = 4000

type Pending = { error: unknown; componentStack?: string }

let capture: Capture | null = null
let queue: Pending[] = []

export function monitoringEnabled(): boolean {
  return DSN.length > 0
}

/** Report an error to Sentry (queued until the SDK has loaded; dropped when monitoring is off). */
export function reportError(error: unknown, componentStack?: string): void {
  if (!monitoringEnabled()) return
  if (capture) {
    capture(error, componentStack)
    return
  }
  if (queue.length < MAX_QUEUED) queue = [...queue, { error, componentStack }]
}

async function load(): Promise<void> {
  try {
    const sentry = await import('./sentry')
    capture = sentry.start(DSN, ENVIRONMENT, RELEASE)
    const pending = queue
    queue = []
    pending.forEach((item) => capture?.(item.error, item.componentStack))
  } catch {
    // Offline or blocked: monitoring is optional and must never break the app.
  }
}

function whenIdle(task: () => void): void {
  const idle = (globalThis as { requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number }).requestIdleCallback
  if (idle) idle(task, { timeout: IDLE_TIMEOUT_MS })
  else setTimeout(task, 1)
}

/** Call once at start-up. Loads the SDK after first paint, only when a DSN is configured. */
export function startMonitoring(): void {
  if (!monitoringEnabled()) return
  const onEarlyError = (event: ErrorEvent) => reportError(event.error ?? event.message)
  const onEarlyRejection = (event: PromiseRejectionEvent) => reportError(event.reason)
  window.addEventListener('error', onEarlyError)
  window.addEventListener('unhandledrejection', onEarlyRejection)
  const begin = () =>
    whenIdle(() => {
      void load().finally(() => {
        // From here on the SDK's own global handlers report these.
        window.removeEventListener('error', onEarlyError)
        window.removeEventListener('unhandledrejection', onEarlyRejection)
      })
    })
  if (document.readyState === 'complete') begin()
  else window.addEventListener('load', begin, { once: true })
}
