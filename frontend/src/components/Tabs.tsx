import { Component, Suspense } from 'react'
import type { KeyboardEvent, ReactNode } from 'react'
import { Icon } from '../lib/icons'

// Staff tab bar (ARIA tabs pattern: one Tab stop, arrow keys move between tabs, Home/End) and a panel
// that loads lazy chunks behind an error boundary, so a chunk that fails to load (offline, or stale after
// a redeploy) shows "could not load, retry" instead of a blank app.

export type TabDef<K extends string> = { key: K; icon: string; label: string }

interface TabsProps<K extends string> {
  tabs: TabDef<K>[]
  active: K
  onSelect: (key: K) => void
  label: string
  panelId: string
  children: ReactNode
}

export function Tabs<K extends string>({ tabs, active, onSelect, label, panelId, children }: TabsProps<K>) {
  function onKey(event: KeyboardEvent<HTMLDivElement>): void {
    const index = tabs.findIndex((t) => t.key === active)
    const last = tabs.length - 1
    const next = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key]
    if (next === undefined) return
    event.preventDefault()
    onSelect(tabs[next].key)
    document.getElementById(`tab-${tabs[next].key}`)?.focus()
  }

  return (
    <div className="stack-lg">
      <div className="tabs" role="tablist" aria-label={label} onKeyDown={onKey}>
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`tab-${t.key}`}
            aria-selected={active === t.key}
            aria-controls={panelId}
            tabIndex={active === t.key ? 0 : -1}
            className="tab"
            onClick={() => onSelect(t.key)}
          >
            <Icon name={t.icon} size={20} /> {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={panelId} aria-labelledby={`tab-${active}`} tabIndex={0}>
        <ChunkBoundary key={active}>
          <Suspense fallback={<p className="loading" role="status">Loading…</p>}>{children}</Suspense>
        </ChunkBoundary>
      </div>
    </div>
  )
}

interface BoundaryState {
  failed: boolean
}

/** Error boundaries must be class components in React 19. Resets when the tab changes (keyed by the parent). */
export class ChunkBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { failed: false }

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true }
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children
    return (
      <div className="note note-risk" role="alert">
        <Icon name="warning" size={20} />
        <span>
          This section could not load (no connection, or the app was just updated).{' '}
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => window.location.reload()}>Reload</button>
        </span>
      </div>
    )
  }
}
