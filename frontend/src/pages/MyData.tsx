import { useCallback, useEffect, useState } from 'react'
import { api, errorText, patch, post } from '../api/client'
import type { AccessLogRow, Consent, ConsentField, ConsentList, CorrectionField } from '../api/types'
import { Badge, Bilingual, ErrorNote, ListenButton, Loading, Pictogram, formatTime } from '../components/ui'
import { Icon } from '../lib/icons'

// "My data": who can see my data (per-field switches, withdraw), who saw it, and fix a mistake.
// The server enforces every consent; this screen only asks it.

type Tab = 'share' | 'log' | 'fix'

const FIELD_LABEL: Record<string, { icon: string; ur: string; en: string }> = {
  cnic: { icon: 'id-card', ur: 'شناختی کارڈ نمبر', en: 'ID card number' },
  family_record: { icon: 'family', ur: 'خاندانی ریکارڈ', en: 'Family record' },
  death_certificate: { icon: 'certificate', ur: 'وفات کا سرٹیفکیٹ', en: 'Death certificate' },
  payout_account: { icon: 'bank', ur: 'بینک اکاؤنٹ', en: 'Bank account' },
  case_details: { icon: 'document', ur: 'دعوے کی تفصیل', en: 'Claim details' },
}
const ACTION_LABEL: Record<string, { icon: string; tone: 'ok' | 'attn' | 'risk' | 'info' | 'quiet'; ur: string; en: string }> = {
  DATA_ACCESS: { icon: 'eye', tone: 'info', ur: 'آپ کا ڈیٹا دیکھا', en: 'Looked at your data' },
  CONSENT_DENIED: { icon: 'lock', tone: 'risk', ur: 'روک دیا گیا، اجازت نہیں تھی', en: 'Tried to look, and was blocked' },
  CONSENT_WITHDRAWN: { icon: 'close', tone: 'quiet', ur: 'آپ نے اجازت واپس لی', en: 'You took back access' },
  CONSENT_GRANTED: { icon: 'unlock', tone: 'ok', ur: 'آپ نے اجازت دی', en: 'You gave access' },
  CONSENT_CHANGED: { icon: 'pen', tone: 'attn', ur: 'آپ نے اجازت بدلی', en: 'You changed what is shared' },
  CORRECTION_REQUESTED: { icon: 'pen', tone: 'info', ur: 'درستی کی درخواست', en: 'You asked for a correction' },
  CORRECTION_APPROVED: { icon: 'check', tone: 'ok', ur: 'درستی منظور', en: 'Correction approved' },
  CORRECTION_REJECTED: { icon: 'warning', tone: 'attn', ur: 'درستی نامنظور', en: 'Correction not approved' },
}
const CORRECTIONS: { key: CorrectionField; icon: string; ur: string; en: string }[] = [
  { key: 'name', icon: 'person', ur: 'نام', en: 'Name' },
  { key: 'date_of_birth', icon: 'calendar', ur: 'تاریخ پیدائش', en: 'Date of birth' },
  { key: 'payout_account', icon: 'bank', ur: 'بینک اکاؤنٹ', en: 'Bank account' },
  { key: 'family_record', icon: 'family', ur: 'خاندانی ریکارڈ', en: 'Family record' },
]
const TAB_UR = {
  share: 'یہاں دیکھیں کون آپ کا ڈیٹا دیکھ سکتا ہے۔ بٹن سے اجازت بند یا واپس کریں۔',
  log: 'یہاں دیکھیں کس نے آپ کا ڈیٹا کب دیکھا۔',
  fix: 'اگر آپ کے ریکارڈ میں غلطی ہے تو یہاں بتائیں۔',
}

export function MyData({ onBack }: { onBack: () => void }) {
  const [tab, setTab] = useState<Tab>('share')
  const tabs: { key: Tab; icon: string; ur: string; en: string }[] = [
    { key: 'share', icon: 'people', ur: 'کون دیکھ سکتا ہے', en: 'Who can see' },
    { key: 'log', icon: 'clock', ur: 'کس نے دیکھا', en: 'Who saw' },
    { key: 'fix', icon: 'pen', ur: 'غلطی درست کریں', en: 'Fix a mistake' },
  ]

  return (
    <section className="stack-lg">
      <button type="button" className="btn btn-quiet btn-sm self-start" onClick={onBack}>
        <Icon name="arrow-left" size={20} /> Home
      </button>
      <div className="hello">
        <Bilingual as="h1" ur="میرا ڈیٹا" en="My data" />
        <ListenButton audioKey={`mydata_${tab}`} text={TAB_UR[tab]} />
      </div>
      <div className="segmented" role="tablist" aria-label="My data sections">
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            id={`tab-${t.key}`}
            aria-selected={tab === t.key}
            aria-controls={`panel-${t.key}`}
            className="segment"
            onClick={() => setTab(t.key)}
          >
            <Icon name={t.icon} size={24} />
            <span lang="ur" dir="rtl" className="segment-ur">{t.ur}</span>
            <span className="segment-en">{t.en}</span>
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === 'share' && <SharePanel />}
        {tab === 'log' && <AccessLog />}
        {tab === 'fix' && <CorrectionForm />}
      </div>
    </section>
  )
}

function SharePanel() {
  const [data, setData] = useState<ConsentList | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [confirmId, setConfirmId] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setData((await api<ConsentList>('/api/v1/me/consents')).data)
    } catch (e) {
      setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  async function run(id: string, action: () => Promise<unknown>): Promise<void> {
    setBusyId(id)
    setError(null)
    try {
      await action()
      setConfirmId(null)
      await load()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusyId(null)
    }
  }

  function toggleField(c: Consent, field: ConsentField): void {
    const next = c.fields.includes(field) ? c.fields.filter((f) => f !== field) : [...c.fields, field]
    void run(c.id, () => patch(`/api/v1/me/consents/${c.id}`, { fields: next }))
  }

  if (!data) return error ? <ErrorNote message={error} /> : <Loading />
  const active = data.consents.filter((c) => c.status === 'active')
  const withdrawn = data.consents.filter((c) => c.status === 'withdrawn')

  return (
    <div className="stack">
      <ErrorNote message={error} />
      {active.length === 0 && <p className="empty">Nobody can see your data right now.</p>}
      {active.map((c) => (
        <article key={c.id} className="grant" aria-busy={busyId === c.id}>
          <header className="grant-head">
            <Pictogram name={c.grantee_type === 'helper' ? 'helper' : 'bank'} />
            <div>
              <h3 className="grant-name">{c.grantee_name}</h3>
              <p className="muted">{c.grantee_type === 'helper' ? 'Community helper' : 'Pension department'}, since {formatTime(c.created_at)}</p>
            </div>
            <Badge tone="ok">Can see</Badge>
          </header>
          <ul className="switches">
            {data.fields.map((f) => {
              const on = c.fields.includes(f)
              const last = on && c.fields.length === 1
              const label = FIELD_LABEL[f] ?? { icon: 'document', ur: f, en: f }
              return (
                <li key={f}>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={on}
                    className="switch-row"
                    disabled={busyId !== null || last}
                    title={last ? 'At least one item must stay shared. Use “Take back all access” instead.' : undefined}
                    onClick={() => toggleField(c, f)}
                  >
                    <Icon name={label.icon} size={24} />
                    <span className="switch-label">
                      <span lang="ur" dir="rtl">{label.ur}</span>
                      <span className="bi-en">{label.en}</span>
                    </span>
                    <span className="switch" aria-hidden="true"><span className="switch-knob" /></span>
                    <span className="switch-state">{on ? 'Shared' : 'Hidden'}</span>
                  </button>
                </li>
              )
            })}
          </ul>
          {confirmId === c.id ? (
            <div className="confirm" role="group" aria-label="Confirm withdrawal">
              <p>
                <span lang="ur" dir="rtl" className="note-ur">کیا آپ واقعی اجازت واپس لینا چاہتی ہیں؟</span>
                {c.grantee_name} will not be able to see any of your data after this.
              </p>
              <div className="row">
                <button type="button" className="btn btn-danger btn-big" disabled={busyId !== null} onClick={() => void run(c.id, () => post(`/api/v1/me/consents/${c.id}/withdraw`, {}))}>
                  <span lang="ur" dir="rtl">ہاں، واپس لیں</span>
                  <span className="btn-en">Yes, take back</span>
                </button>
                <button type="button" className="btn btn-secondary btn-big" onClick={() => setConfirmId(null)}>Keep sharing</button>
              </div>
            </div>
          ) : (
            <button type="button" className="btn btn-danger-outline btn-big btn-block" onClick={() => setConfirmId(c.id)}>
              <Icon name="lock" size={24} />
              <span lang="ur" dir="rtl">اجازت واپس لیں</span>
              <span className="btn-en">Take back all access</span>
            </button>
          )}
        </article>
      ))}

      {withdrawn.length > 0 && (
        <section className="stack" aria-labelledby="past-title">
          <h3 id="past-title" className="h-plain">Access you took back</h3>
          {withdrawn.map((c) => (
            <article key={c.id} className="grant grant-past">
              <header className="grant-head">
                <Pictogram name="lock" tone="quiet" size="sm" />
                <div>
                  <p className="grant-name">{c.grantee_name}</p>
                  <p className="muted">Taken back {c.withdrawn_at ? formatTime(c.withdrawn_at) : ''}</p>
                </div>
                <button
                  type="button"
                  className="btn btn-secondary btn-sm"
                  disabled={busyId !== null}
                  onClick={() => void run(c.id, () => post('/api/v1/me/consents', { grantee_type: c.grantee_type, grantee_id: c.grantee_id, fields: c.fields }))}
                >
                  Share again
                </button>
              </header>
            </article>
          ))}
        </section>
      )}
    </div>
  )
}

function AccessLog() {
  const [rows, setRows] = useState<AccessLogRow[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<AccessLogRow[]>('/api/v1/me/access-log')
      .then((r) => active && setRows(r.data))
      .catch((e: unknown) => active && setError(errorText(e)))
    return () => {
      active = false
    }
  }, [])

  if (error) return <ErrorNote message={error} />
  if (!rows) return <Loading />
  if (rows.length === 0) return <p className="empty">Nobody has looked at your data yet.</p>

  return (
    <ol className="timeline">
      {rows.map((r) => {
        const a = ACTION_LABEL[r.action] ?? { icon: 'eye', tone: 'info' as const, ur: '', en: r.action }
        const field = r.field ? FIELD_LABEL[r.field]?.en ?? r.field : null
        return (
          <li key={r.seq} className={`tl-item tone-${a.tone}`}>
            <span className="tl-dot"><Icon name={a.icon} size={20} /></span>
            <div className="tl-body">
              <p className="tl-who"><strong>{r.who}</strong>{r.role ? <span className="muted">, {r.role}</span> : null}</p>
              {a.ur && <p lang="ur" dir="rtl" className="tl-ur">{a.ur}</p>}
              <p className="tl-en">{a.en}{field ? `: ${field}` : ''}{r.basis ? ` (${r.basis.replace(/_/g, ' ')})` : ''}</p>
              <time className="tl-time" dateTime={r.ts}>{formatTime(r.ts)}</time>
            </div>
          </li>
        )
      })}
    </ol>
  )
}

function CorrectionForm() {
  const [field, setField] = useState<CorrectionField>('name')
  const [value, setValue] = useState('')
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sent, setSent] = useState(false)

  async function submit(): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      await post('/api/v1/me/corrections', { field, requested_value: value.trim(), reason: reason.trim() })
      setSent(true)
      setValue('')
      setReason('')
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <div className="stack">
        <p className="note note-ok" role="status">
          <Icon name="check" size={22} />
          <span><span lang="ur" dir="rtl" className="note-ur">آپ کی درخواست بھیج دی گئی۔</span>Request sent. An officer will check it; your old record is kept until then.</span>
        </p>
        <button type="button" className="btn btn-secondary" onClick={() => setSent(false)}>Fix something else</button>
      </div>
    )
  }

  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); void submit() }}>
      <fieldset className="fieldset">
        <legend className="field-label">What is wrong?</legend>
        <div className="choice-grid choice-2">
          {CORRECTIONS.map((c) => (
            <button key={c.key} type="button" className="choice choice-sm" aria-pressed={field === c.key} onClick={() => setField(c.key)}>
              <Icon name={c.icon} size={30} />
              <span lang="ur" dir="rtl" className="choice-ur">{c.ur}</span>
              <span className="choice-en">{c.en}</span>
            </button>
          ))}
        </div>
      </fieldset>
      <label className="field">
        <span className="field-label">What should it say?</span>
        <input className="input input-big" value={value} maxLength={200} onChange={(e) => setValue(e.target.value)} required />
      </label>
      <label className="field">
        <span className="field-label">Why? (for example: spelling on my CNIC is different)</span>
        <textarea className="input" rows={3} value={reason} maxLength={1000} onChange={(e) => setReason(e.target.value)} required />
      </label>
      <ErrorNote message={error} />
      <button type="submit" className="btn btn-primary btn-big btn-block" disabled={busy || value.trim().length < 1 || reason.trim().length < 3}>
        <span lang="ur" dir="rtl">درخواست بھیجیں</span>
        <span className="btn-en">{busy ? 'Sending…' : 'Send correction request'}</span>
      </button>
    </form>
  )
}
