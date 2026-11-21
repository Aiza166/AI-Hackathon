import { Suspense, lazy, useCallback, useEffect, useState } from 'react'
import { api, errorText, post } from '../api/client'
import type { CaseView } from '../api/types'
import { Badge, ErrorNote, Loading, humanize, toneFor } from '../components/ui'
import { Icon } from '../lib/icons'
import { OfficerPayouts } from './OfficerPayouts'
import { ScamMap } from './ScamMap'

const DocumentReview = lazy(() => import('../components/DocumentReview').then((m) => ({ default: m.DocumentReview })))

// Officer review queue: highest priority first, lowest confidence first.
// Desktop: queue on the left, case detail and decision trace on the right.

type Match = { p: number; levels: Record<string, unknown> } | null
type Trace = {
  decision_id: string
  route: string
  reason_codes: string[]
  confidence: number
  thresholds: Record<string, number>
  rule_version: { version: number; label: string }
  signals: {
    payee: string
    duplicate_claims: { case: string }[]
    co_sharers: { case: string }[]
    claimant_match: Match
    deceased_matches: Record<string, Match>
  }
}

type Tab = 'queue' | 'payouts' | 'scams'
const TABS: { key: Tab; icon: string; label: string }[] = [
  { key: 'queue', icon: 'list', label: 'Review queue' },
  { key: 'payouts', icon: 'bank', label: 'Payout changes' },
  { key: 'scams', icon: 'warning', label: 'Scam map' },
]

export function OfficerHome() {
  const [tab, setTab] = useState<Tab>('queue')
  return (
    <div className="stack-lg">
      <div className="tabs" role="tablist" aria-label="Officer sections">
        {TABS.map((t) => (
          <button key={t.key} type="button" role="tab" id={`tab-${t.key}`} aria-selected={tab === t.key} aria-controls="panel-officer" className="tab" onClick={() => setTab(t.key)}>
            <Icon name={t.icon} size={20} /> {t.label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id="panel-officer" aria-labelledby={`tab-${tab}`}>
        {tab === 'queue' && <QueuePanel />}
        {tab === 'payouts' && <OfficerPayouts />}
        {tab === 'scams' && <ScamMap />}
      </div>
    </div>
  )
}

function QueuePanel() {
  const [queue, setQueue] = useState<CaseView[] | null>(null)
  const [selected, setSelected] = useState<CaseView | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setQueue((await api<CaseView[]>('/api/v1/queue')).data)
    } catch (e) {
      setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function open(c: CaseView): Promise<void> {
    setSelected(c)
    setTrace(null)
    setReason('')
    setDone(null)
    setError(null)
    if (!c.latest_decision) return
    try {
      setTrace((await api<Trace>(`/api/v1/decisions/${c.latest_decision.id}/trace`)).data)
    } catch (e) {
      setError(errorText(e))
    }
  }

  async function decide(action: 'approve' | 'reject'): Promise<void> {
    if (!selected) return
    setBusy(true)
    try {
      await post(`/api/v1/cases/${selected.id}/${action}`, { reason })
      setDone(`${selected.reference} ${action === 'approve' ? 'approved' : 'rejected'}. The citizen has been told.`)
      setSelected(null)
      await refresh()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="split">
      <section className="split-main" aria-labelledby="queue-title">
        <div className="page-head">
          <h1 id="queue-title" className="page-title">Review queue</h1>
          <span className="count">{queue?.length ?? 0} waiting</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => void refresh()}>
            <Icon name="twin" size={18} /> Refresh
          </button>
        </div>
        <p className="page-sub">Cases the system was not sure about. Highest priority and lowest confidence first.</p>
        {done && <p className="note note-ok" role="status"><Icon name="check" size={20} /><span>{done}</span></p>}
        {!queue && <Loading label="Loading queue" />}
        {queue && queue.length === 0 && <p className="empty">The queue is empty. Nothing needs a human right now.</p>}
        {queue && queue.length > 0 && (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr><th scope="col">Case</th><th scope="col">Priority</th><th scope="col">Confidence</th><th scope="col">Why a human</th></tr>
              </thead>
              <tbody>
                {queue.map((c) => (
                  <tr key={c.id} className={selected?.id === c.id ? 'is-selected' : undefined}>
                    <td>
                      <button type="button" className="row-link" onClick={() => void open(c)} aria-label={`Open case ${c.reference}`}>
                        {c.reference}
                      </button>
                    </td>
                    <td><PriorityBars level={c.priority} /></td>
                    <td><Confidence value={c.confidence} /></td>
                    <td className="codes">
                      {(c.latest_decision?.reason_codes ?? []).map((r) => <code key={r} className="code">{r}</code>)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <aside className="split-side" aria-label="Case detail">
        <ErrorNote message={error} />
        {!selected && (
          <div className="side-empty">
            <Icon name="list" size={36} />
            <p>Choose a case from the queue to see why the system handed it to you.</p>
          </div>
        )}
        {selected && (
          <article className="detail">
            <header className="detail-head">
              <h2 className="detail-title">{selected.reference}</h2>
              <Badge tone={toneFor(selected.status)}>{humanize(selected.status)}</Badge>
            </header>
            {selected.latest_decision && !trace && <Loading label="Loading decision trace" />}
            {trace && <TraceView trace={trace} />}
            <Suspense fallback={<Loading label="Loading documents" />}>
              <DocumentReview key={selected.id} caseId={selected.id} />
            </Suspense>
            <label className="field">
              <span className="field-label">Your reason (required, saved in the audit log)</span>
              <textarea className="input" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} />
            </label>
            <div className="row">
              <button type="button" className="btn btn-primary" disabled={busy || reason.trim().length < 3} onClick={() => void decide('approve')}>
                <Icon name="check" size={20} /> Approve
              </button>
              <button type="button" className="btn btn-danger" disabled={busy || reason.trim().length < 3} onClick={() => void decide('reject')}>
                <Icon name="close" size={20} /> Reject
              </button>
            </div>
            <p className="fine">Only an officer can reject. The system never does.</p>
          </article>
        )}
      </aside>
    </div>
  )
}

function TraceView({ trace }: { trace: Trace }) {
  const t = trace.signals
  return (
    <div className="trace">
      <div className="trace-route">
        <Badge tone={toneFor(trace.route)}>{trace.route}</Badge>
        <span>confidence <strong>{trace.confidence.toFixed(2)}</strong></span>
        <span className="muted">auto-approve needs {trace.thresholds.t_auto}</span>
      </div>
      <p className="muted">Rule v{trace.rule_version.version}: {trace.rule_version.label}</p>
      <div className="codes">{trace.reason_codes.map((r) => <code key={r} className="code">{r}</code>)}</div>
      <dl className="facts">
        <dt>Payee check</dt><dd>{humanize(t.payee)}</dd>
        <dt>Competing claims</dt><dd>{t.duplicate_claims.map((d) => d.case).join(', ') || 'None'}</dd>
        <dt>Lawful co-sharers</dt><dd>{t.co_sharers.map((d) => d.case).join(', ') || 'None'}</dd>
        {t.claimant_match && <><dt>Claimant identity</dt><dd><MatchView m={t.claimant_match} /></dd></>}
        {Object.entries(t.deceased_matches).map(([source, m]) => (
          <MatchRow key={source} source={source} m={m} />
        ))}
      </dl>
    </div>
  )
}

function MatchRow({ source, m }: { source: string; m: Match }) {
  return (
    <>
      <dt>{humanize(source)}</dt>
      <dd>{m ? <MatchView m={m} /> : <span className="muted">No record found</span>}</dd>
    </>
  )
}

function MatchView({ m }: { m: NonNullable<Match> }) {
  return (
    <span className="match">
      <Confidence value={m.p} />
      <span className="levels">
        {Object.entries(m.levels).map(([k, v]) => (
          <span key={k} className="level"><span className="muted">{humanize(k)}</span> {String(v)}</span>
        ))}
      </span>
    </span>
  )
}

function PriorityBars({ level }: { level: number }) {
  const capped = Math.max(1, Math.min(level, 3))
  return (
    <span className="prio" aria-label={`Priority ${level}`}>
      {[1, 2, 3].map((i) => <span key={i} className={i <= capped ? `prio-bar on p${capped}` : 'prio-bar'} />)}
      <span className="prio-n">{level}</span>
    </span>
  )
}

function Confidence({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span className="muted">-</span>
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const tone = value >= 0.95 ? 'ok' : value >= 0.7 ? 'attn' : 'risk'
  return (
    <span className="conf">
      <span className="conf-track" aria-hidden="true"><span className={`conf-fill tone-${tone}`} style={{ width: `${pct}%` }} /></span>
      <span className="conf-n">{value.toFixed(2)}</span>
    </span>
  )
}
