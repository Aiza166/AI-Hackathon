import { useCallback, useEffect, useState } from 'react'
import { api, errorText, post } from '../api/client'
import type { CaseView } from '../api/types'

// Officer review queue: highest priority first, lowest confidence first.

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
    claimant_match: { p: number; levels: Record<string, unknown> } | null
    deceased_matches: Record<string, { p: number; levels: Record<string, unknown> } | null>
  }
}

export function OfficerHome() {
  const [queue, setQueue] = useState<CaseView[]>([])
  const [selected, setSelected] = useState<CaseView | null>(null)
  const [trace, setTrace] = useState<Trace | null>(null)
  const [reason, setReason] = useState('')
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
    if (!c.latest_decision) return
    try {
      setTrace((await api<Trace>(`/api/v1/decisions/${c.latest_decision.id}/trace`)).data)
    } catch (e) {
      setError(errorText(e))
    }
  }

  async function decide(action: 'approve' | 'reject'): Promise<void> {
    if (!selected) return
    try {
      await post(`/api/v1/cases/${selected.id}/${action}`, { reason })
      setSelected(null)
      await refresh()
    } catch (e) {
      setError(errorText(e))
    }
  }

  return (
    <section className="stack">
      <h2>Review queue ({queue.length})</h2>
      {error && <p className="error" role="alert">{error}</p>}
      <table className="queue">
        <thead><tr><th>Case</th><th>Priority</th><th>Confidence</th><th>Why a human</th></tr></thead>
        <tbody>
          {queue.map((c) => (
            <tr key={c.id} className={selected?.id === c.id ? 'selected' : ''} onClick={() => void open(c)}>
              <td>{c.reference}</td>
              <td><span className={`priority p${Math.min(Math.max(c.priority, 1), 4)}`}>{c.priority}</span></td>
              <td>{c.confidence?.toFixed(2) ?? '-'}</td>
              <td>{c.latest_decision?.reason_codes.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {selected && (
        <article className="panel stack">
          <h3>{selected.reference} · {selected.status.replace('_', ' ')}</h3>
          {trace && (
            <>
              <p>System said <strong>{trace.route}</strong> ({trace.reason_codes.join(', ')}), confidence {trace.confidence.toFixed(2)} (auto-approve needs {trace.thresholds.t_auto}), rule v{trace.rule_version.version}.</p>
              <ul>
                <li>Payee check: <strong>{trace.signals.payee.replace('_', ' ')}</strong></li>
                <li>Competing claims: {trace.signals.duplicate_claims.map((d) => d.case).join(', ') || 'none'}</li>
                <li>Lawful co-sharers: {trace.signals.co_sharers.map((d) => d.case).join(', ') || 'none'}</li>
                {Object.entries(trace.signals.deceased_matches).map(([source, m]) => (
                  <li key={source}>{source.replace(/_/g, ' ')}: p={m?.p ?? '-'} {m && JSON.stringify(m.levels)}</li>
                ))}
              </ul>
            </>
          )}
          <label>Reason (required) <textarea value={reason} onChange={(e) => setReason(e.target.value)} /></label>
          <div className="row">
            <button type="button" className="primary" disabled={reason.trim().length < 3} onClick={() => void decide('approve')}>Approve</button>
            <button type="button" className="danger" disabled={reason.trim().length < 3} onClick={() => void decide('reject')}>Reject</button>
          </div>
        </article>
      )}
    </section>
  )
}
