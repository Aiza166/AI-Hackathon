import { useCallback, useEffect, useState } from 'react'
import { api, errorText, post } from '../api/client'
import type { PayoutChange } from '../api/types'
import { Badge, ErrorNote, Loading, formatTime, humanize } from '../components/ui'
import { Icon } from '../lib/icons'
import { PayeeCard } from './SafeSwitch'

// Officer view of SafeSwitch: payout changes held because something looked wrong.
// Approving still needs the claimant's own PIN; the change only applies after the hold.

type Filter = 'flagged' | 'all'

export function OfficerPayouts() {
  const [filter, setFilter] = useState<Filter>('flagged')
  const [rows, setRows] = useState<PayoutChange[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  const load = useCallback(async (which: Filter) => {
    try {
      setRows((await api<PayoutChange[]>(`/api/v1/payout-changes?status=${which}`)).data)
      setError(null)
    } catch (e) {
      setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    void load(filter)
  }, [filter, load])

  async function done(message: string): Promise<void> {
    setNotice(message)
    await load(filter)
  }

  return (
    <section className="stack-lg" aria-labelledby="payouts-title">
      <div className="page-head">
        <h1 id="payouts-title" className="page-title">Payout account changes</h1>
        <span className="count">{rows?.length ?? 0} shown</span>
        <label className="row">
          <span className="sr-only">Show</span>
          <select className="input" value={filter} onChange={(e) => setFilter(e.target.value as Filter)}>
            <option value="flagged">Flagged (need you)</option>
            <option value="all">All recent</option>
          </select>
        </label>
      </div>
      <p className="page-sub">Changes held longer because the payee check, a joint account, a timeout or account reuse raised a flag. Money keeps going to the old account until the hold ends.</p>
      {notice && <p className="note note-ok" role="status"><Icon name="check" size={20} /><span>{notice}</span></p>}
      <ErrorNote message={error} />
      {!rows && !error && <Loading label="Loading payout changes" />}
      {rows && rows.length === 0 && <p className="empty">No payout changes need a person right now.</p>}
      <div className="change-grid">
        {rows?.map((c) => <ChangeCard key={c.id} change={c} onDone={(m) => void done(m)} />)}
      </div>
    </section>
  )
}

function ChangeCard({ change, onDone }: { change: PayoutChange; onDone: (message: string) => void }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function decide(action: 'approve' | 'reject'): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      await post(`/api/v1/payout-changes/${change.id}/${action}`, { note })
      onDone(`Change for ${change.case_reference ?? 'case'} ${action === 'approve' ? 'approved' : 'rejected'}.`)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="detail" aria-label={`Payout change for ${change.case_reference ?? change.case_id}`}>
      <header className="detail-head">
        <h2 className="detail-title">{change.case_reference ?? 'Case'}</h2>
        <Badge tone={change.status === 'flagged' ? 'attn' : change.status === 'rejected' ? 'risk' : 'info'}>{humanize(change.status)}</Badge>
      </header>
      <PayeeCard payee={change.payee_result} check={change.payee_check} last4={change.new_iban_last4} />
      <div className="codes">{change.flags.map((f) => <code key={f} className="code">{f}</code>)}</div>
      <dl className="facts">
        <dt>Started by</dt><dd>{change.requested_role}</dd>
        <dt>Claimant PIN</dt><dd>{change.confirmed ? 'Confirmed' : 'Not yet'}</dd>
        <dt>Hold until</dt><dd>{formatTime(change.hold_until)}</dd>
      </dl>
      {change.status === 'flagged' && (
        <>
          <label className="field">
            <span className="field-label">Your note (required, saved in the audit log)</span>
            <textarea className="input" rows={2} value={note} onChange={(e) => setNote(e.target.value)} />
          </label>
          <ErrorNote message={error} />
          <div className="row">
            <button type="button" className="btn btn-primary" disabled={busy || note.trim().length < 3} onClick={() => void decide('approve')}>
              <Icon name="check" size={20} /> Approve
            </button>
            <button type="button" className="btn btn-danger" disabled={busy || note.trim().length < 3} onClick={() => void decide('reject')}>
              <Icon name="close" size={20} /> Reject
            </button>
          </div>
          <p className="fine">Approving does not skip the claimant's PIN or the hold.</p>
        </>
      )}
    </article>
  )
}
