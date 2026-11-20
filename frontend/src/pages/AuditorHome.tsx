import { useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { AuditRow } from '../api/types'

// Read-only audit log with a one-click hash-chain check.

type Verify = { intact: boolean; checked: number; first_broken_seq: number | null }

export function AuditorHome() {
  const [rows, setRows] = useState<AuditRow[]>([])
  const [verify, setVerify] = useState<Verify | null>(null)
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

  return (
    <section className="stack">
      <div className="row">
        <h2>Audit log</h2>
        <button type="button" className="primary" onClick={() => void runVerify()}>Verify hash chain</button>
      </div>
      {verify && (
        <p className={`status ${verify.intact ? 'ok' : 'bad'}`}>
          {verify.intact ? `Chain intact: ${verify.checked} events checked` : `Chain BROKEN at event ${verify.first_broken_seq}`}
        </p>
      )}
      {error && <p className="error" role="alert">{error}</p>}
      <table className="queue">
        <thead><tr><th>#</th><th>Time</th><th>Actor</th><th>Action</th><th>Resource</th></tr></thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.seq}>
              <td>{r.seq}</td>
              <td>{new Date(r.ts).toLocaleTimeString()}</td>
              <td>{r.actor_type}{r.role ? ` (${r.role})` : ''}</td>
              <td>{r.action}</td>
              <td>{r.resource ?? ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
