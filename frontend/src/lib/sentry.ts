// Loaded only through a dynamic import from monitoring.ts, so @sentry/react lives in its own chunk
// and never counts toward the citizen JS budget. No replays, no tracing, no default PII.
import { captureException, init } from '@sentry/react'
import { scrubBreadcrumb, scrubEvent } from './sentryScrub'

export type Capture = (error: unknown, componentStack?: string) => void

// App.tsx keeps the signed-in user under this key. Read the role only: never the name or ids.
const USER_KEY = 'sahara.user'

function currentRole(): string | null {
  try {
    const raw = sessionStorage.getItem(USER_KEY)
    const role: unknown = raw ? (JSON.parse(raw) as { role?: unknown }).role : null
    return typeof role === 'string' ? role : null
  } catch {
    return null
  }
}

export function start(dsn: string, environment: string, release: string | undefined): Capture {
  init({
    dsn,
    environment,
    release,
    sendDefaultPii: false,
    tracesSampleRate: 0,
    replaysSessionSampleRate: 0,
    replaysOnErrorSampleRate: 0,
    beforeSend: (event) => scrubEvent(event, currentRole()),
    beforeBreadcrumb: (crumb) => scrubBreadcrumb(crumb),
  })
  return (error, componentStack) =>
    captureException(error, componentStack ? { contexts: { react: { componentStack } } } : undefined)
}
