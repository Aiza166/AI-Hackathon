import { lazy, useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { AuditRow } from '../api/types'
import { Tabs } from '../components/Tabs'
import type { TabDef } from '../components/Tabs'
import { ErrorNote, Loading } from '../components/ui'
import { Icon } from '../lib/icons'

// Read-only audit log with a one-click hash-chain check. Also used as the admin "Audit log" tab.

const Evaluation = lazy(() => import('./Evaluation').then((m) => ({ default: m.Evaluation })))

type AuditorTab = 'audit' | 'eval'
const AUDITOR_TABS: TabDef<AuditorTab>[] = [
  { key: 'audit', icon: 'shield', label: 'Audit log' },
  { key: 'eval', icon: 'clock', label: 'Evaluation' },
]

/** Auditor home: the audit log and the (read-only) evaluation page. */
export function AuditorWorkspace() {
  const [tab, setTab] = useState<AuditorTab>('audit')
  return (
    <Tabs tabs={AUDITOR_TABS} active={tab} onSelect={setTab} label="Auditor sections" panelId="panel-auditor">
      {tab === 'audit' && <AuditorHome />}
      {tab === 'eval' && <Evaluation />}
    </Tabs>
  )
}

type Verify = { intact: boolean; checked: number; first_broken_seq: number | null }

const BLOCKED = /DENIED|FORBIDDEN|BLOCK/

export function AuditorHome({ embedded = false }: { embedded?: boolean }) {
  const [rows, setRows] = useState<AuditRow[] | null>(null)
  const [verify, setVerify] = useState<Verify | null>(null)
  const [filter, setFilter] = useState('')
  const [open, setOpen] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<AuditRow[]>('/api/v1/audit?limit=100')
      .then((r) => active && setRows(r.data))
      .catch((e: unknown) => active && setError(errorText(e)))
    return () => {
      active = false
    }
  }, [])

  async function runVerify(): Promise<void> {
    try {
      setVerify((await api<Verify>('/api/v1/audit/verify')).data)
    } catch (e) {
      setError(errorText(e))
    }
  }

  const q = filter.trim().toUpperCase()
  const shown = rows?.filter((r) => !q || r.action.includes(q) || (r.resource ?? '').toUpperCase().includes(q) || (r.role ?? '').toUpperCase().includes(q)) ?? []

  return (
    <section className="stack">
      <div className="page-head">
        {embedded ? <h2 className="page-title">Audit log</h2> : <h1 className="page-title">Audit log</h1>}
        <span className="count">{rows?.length ?? 0} latest events</span>
        <button type="button" className="btn btn-primary btn-sm" onClick={() => void runVerify()}>
          <Icon name="shield" size={18} /> Verify hash chain
        </button>
      </div>
      <p className="page-sub">Append-only. Every row is chained to the one before it with SHA-256, so any edit breaks the chain.</p>
      {verify && (
        <p className={verify.intact ? 'note note-ok' : 'note note-risk'} role="status">
          <Icon name={verify.intact ? 'shield' : 'warning'} size={22} />
          <span>{verify.intact ? `Chain intact: ${verify.checked} events checked.` : `Chain broken at event ${verify.first_broken_seq}.`}</span>
        </p>
      )}
      <ErrorNote message={error} />
      <label className="search search-staff">
        <Icon name="search" size={18} />
        <span className="sr-only">Filter events</span>
        <input className="input" placeholder="Filter by action, role or resource (e.g. CONSENT)" value={filter} onChange={(e) => setFilter(e.target.value)} />
      </label>
      {!rows && !error && <Loading label="Loading events" />}
      {rows && (
        <div className="table-wrap">
          <table className="table table-dense">
            <thead>
              <tr><th scope="col">#</th><th scope="col">Time</th><th scope="col">Actor</th><th scope="col">Action</th><th scope="col">Resource</th><th scope="col"><span className="sr-only">Details</span></th></tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <AuditRowView key={r.seq} row={r} isOpen={open === r.seq} onToggle={() => setOpen(open === r.seq ? null : r.seq)} />
              ))}
            </tbody>
          </table>
          {shown.length === 0 && <p className="empty">No events match “{filter}”.</p>}
        </div>
      )}
    </section>
  )
}

interface AuditRowViewProps {
  row: AuditRow
  isOpen: boolean
  onToggle: () => void
}

function AuditRowView({ row, isOpen, onToggle }: AuditRowViewProps) {
  const hasDetails = Object.keys(row.details ?? {}).length > 0
  return (
    <>
      <tr className={BLOCKED.test(row.action) ? 'is-flagged' : undefined}>
        <td className="num">{row.seq}</td>
        <td className="nowrap">{new Date(row.ts).toLocaleTimeString('en-GB')}</td>
        <td>{row.actor_type}{row.role ? <span className="muted"> ({row.role})</span> : null}</td>
        <td><code className="code">{row.action}</code></td>
        <td className="resource">{row.resource ?? ''}</td>
        <td>
          {hasDetails && (
            <button type="button" className="btn btn-quiet btn-xs" aria-expanded={isOpen} onClick={onToggle}>
              {isOpen ? 'Hide' : 'Details'}
            </button>
          )}
        </td>
      </tr>
      {isOpen && (
        <tr className="details-row">
          <td colSpan={6}>
            <dl className="kv">
              {Object.entries(row.details).map(([k, v]) => (
                <div key={k}><dt>{k}</dt><dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>
              ))}
            </dl>
          </td>
        </tr>
      )}
    </>
  )
}
