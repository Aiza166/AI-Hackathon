import { Component, type ErrorInfo, type ReactNode } from 'react'
import { reportError } from '../lib/monitoring'
import { PrototypeBanner } from './PrototypeBanner'

type Props = { children: ReactNode }
type State = { failed: boolean }

// Catches render errors so the screen never goes blank, and reports them to Sentry (scrubbed,
// only when monitoring is configured). A class component because React has no hook for this.
export class ErrorBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    reportError(error, info.componentStack ?? undefined)
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children
    return (
      <main className="error-fallback" role="alert">
        <PrototypeBanner />
        <p lang="ur" dir="rtl">کچھ غلط ہو گیا۔ آپ کی معلومات اس فون پر محفوظ ہیں۔</p>
        <p>Something went wrong. Your saved answers are still on this phone.</p>
        <button type="button" className="btn btn-primary" onClick={() => window.location.reload()}>
          <span lang="ur" dir="rtl">دوبارہ کھولیں</span> / Reload
        </button>
      </main>
    )
  }
}
