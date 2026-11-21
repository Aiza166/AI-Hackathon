import { useCallback, useEffect, useState } from 'react'
import { api, errorText, post } from '../api/client'
import type { CaseView, PayeeCheck, PayoutChange } from '../api/types'
import { Badge, Bilingual, ErrorNote, ListenButton, Loading, Pictogram } from '../components/ui'
import { Icon } from '../lib/icons'

// SafeSwitch: change where the pension is paid. Nothing changes at once: a mock Raast title
// fetch checks the new account, the change is held 48 hours (4 business days if anything looks
// wrong), and only the claimant herself can confirm it with her own PIN. A helper can start
// a change for her but never confirm it.

const OPEN = new Set(['held', 'flagged', 'confirmed', 'approved'])
const INTRO_UR = 'پنشن کا اکاؤنٹ بدلنے کے لیے نیا اکاؤنٹ نمبر لکھیں۔ تبدیلی فوراً نہیں ہوگی، اڑتالیس گھنٹے انتظار ہوگا اور آپ کا اپنا پن لگے گا۔'
const IBAN_PATTERN = /^[A-Z0-9]{10,34}$/

const PAYEE: Record<string, { tone: 'ok' | 'attn' | 'risk'; icon: string; ur: string; en: string }> = {
  match: { tone: 'ok', icon: 'check', ur: 'نام مل گیا', en: 'Match: the account is in your name' },
  close_match: { tone: 'attn', icon: 'question', ur: 'نام تقریباً ملتا ہے', en: 'Close match: needs a second look' },
  no_match: { tone: 'risk', icon: 'warning', ur: 'نام نہیں ملتا', en: 'No match: not your account' },
  unavailable: { tone: 'risk', icon: 'cloud-off', ur: 'بینک سے جواب نہیں آیا', en: 'The bank did not answer in time' },
}
const FLAG_TEXT: Record<string, [string, string]> = {
  PAYEE_CLOSE_MATCH: ['اکاؤنٹ کا نام پوری طرح نہیں ملتا۔', 'The account name does not fully match yours.'],
  PAYEE_NO_MATCH: ['یہ اکاؤنٹ آپ کے نام پر نہیں۔', 'This account is not in your name.'],
  JOINT_ACCOUNT: ['یہ مشترکہ اکاؤنٹ ہے۔ پنشن صرف آپ کے اپنے اکاؤنٹ میں آ سکتی ہے، ثبوت چاہیے۔', 'This is a joint account. Pension must go to your own account: proof is needed.'],
  PAYEE_CHECK_TIMEOUT: ['بینک نے وقت پر جواب نہیں دیا۔ افسر خود جانچ کرے گا۔', 'The bank check timed out. An officer will check it by hand.'],
  ACCOUNT_USED_BY_ANOTHER_CLAIM: ['یہ اکاؤنٹ کسی اور دعوے میں بھی ہے۔', 'This account is used by another claim.'],
  CHANGE_SOON_AFTER_DEATH: ['وفات کے فوراً بعد تبدیلی پر زیادہ احتیاط ہوتی ہے۔', 'Changes soon after a death get extra care.'],
}
const STATUS_TEXT: Record<string, [string, string]> = {
  held: ['انتظار میں: آپ کے پن کا انتظار', 'On hold: waiting for your PIN'],
  flagged: ['افسر کی جانچ اور زیادہ انتظار', 'Held longer: an officer must check'],
  approved: ['افسر نے منظور کیا: آپ کا پن چاہیے', 'Officer approved: your PIN is needed'],
  confirmed: ['تصدیق ہو گئی: وقت پورا ہونے پر بدل جائے گا', 'Confirmed: switches when the hold ends'],
  applied: ['اکاؤنٹ بدل گیا', 'Account changed'],
  rejected: ['افسر نے روک دیا', 'Stopped by an officer'],
  cancelled: ['منسوخ', 'Cancelled'],
}
// Mock accounts from the seeded demo world, so judges can try each outcome.
const DEMO_IBANS = [
  { iban: 'PK00MOCK0000000000000013', label: 'Own wallet' },
  { iban: 'PK00MOCK0000000000000012', label: 'Joint account' },
  { iban: 'PK00MOCK0000000000000008', label: "Someone else's" },
]

function flagText(flag: string): [string, string] {
  if (flag.startsWith('SERVICE_UNAVAILABLE')) return ['ریکارڈ تک رسائی نہیں ہوئی۔', 'A record service did not answer.']
  return FLAG_TEXT[flag] ?? ['مزید جانچ ضروری ہے۔', 'Needs a second look.']
}

interface SafeSwitchProps {
  cases: CaseView[]
  isHelper: boolean
  claimantName: string
  onBack: () => void
}

export function SafeSwitch({ cases, isHelper, claimantName, onBack }: SafeSwitchProps) {
  const [caseId, setCaseId] = useState<string>(cases[0]?.id ?? '')
  const [changes, setChanges] = useState<PayoutChange[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (id: string) => {
    if (!id) return
    try {
      setChanges((await api<PayoutChange[]>(`/api/v1/cases/${id}/payout-changes`)).data)
      setError(null)
    } catch (e) {
      setError(errorText(e))
    }
  }, [])

  useEffect(() => {
    void load(caseId)
  }, [caseId, load])

  const open = changes?.find((c) => OPEN.has(c.status)) ?? null
  const past = (changes ?? []).filter((c) => c !== open)

  return (
    <section className="stack-lg" aria-labelledby="switch-title">
      <button type="button" className="btn btn-ghost btn-sm self-start" onClick={onBack}>
        <Icon name="arrow-left" size={20} />
        <span lang="ur" dir="rtl">واپس</span>
        <span>Back</span>
      </button>
      <div className="hello">
        <Bilingual as="h1" id="switch-title" ur="پنشن کا اکاؤنٹ بدلیں" en="Change payout account" />
        <ListenButton audioKey="prompt_safeswitch" text={INTRO_UR} />
      </div>
      {isHelper && (
        <p className="note note-info">
          <Icon name="helper" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">آپ تبدیلی شروع کر سکتی ہیں، لیکن تصدیق صرف {claimantName} اپنے فون پر اپنے پن سے کریں گی۔</span>
            You can start a change for {claimantName}, but only she can confirm it, on her own phone with her own PIN.
          </span>
        </p>
      )}

      {cases.length > 1 && (
        <label className="field">
          <span className="field-label">Which claim?</span>
          <select className="input input-big" value={caseId} onChange={(e) => setCaseId(e.target.value)}>
            {cases.map((c) => <option key={c.id} value={c.id}>{c.reference}</option>)}
          </select>
        </label>
      )}

      <ErrorNote message={error} />
      {!changes && !error && <Loading label="Loading account changes" />}
      {changes && open && (
        <PendingChange change={open} isHelper={isHelper} claimantName={claimantName} onChanged={() => void load(caseId)} />
      )}
      {changes && !open && <NewChange caseId={caseId} onCreated={() => void load(caseId)} />}

      {past.length > 0 && (
        <section className="stack" aria-labelledby="switch-history">
          <h2 id="switch-history" className="h-plain">Earlier changes</h2>
          <ul className="claim-list">
            {past.map((c) => (
              <li key={c.id} className="claim-item claim-item-static">
                <Icon name="bank" size={22} />
                <span className="claim-ref">…{c.new_iban_last4}</span>
                <span className="claim-status">
                  <span lang="ur" dir="rtl">{STATUS_TEXT[c.status]?.[0]}</span>
                  <Badge tone={c.status === 'applied' ? 'ok' : 'quiet'}>{STATUS_TEXT[c.status]?.[1] ?? c.status}</Badge>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </section>
  )
}

function NewChange({ caseId, onCreated }: { caseId: string; onCreated: () => void }) {
  const [iban, setIban] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const clean = iban.replace(/\s/g, '').toUpperCase()

  async function submit(): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      await post<PayoutChange>(`/api/v1/cases/${caseId}/payout-change`, { new_iban: clean })
      onCreated()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); void submit() }}>
      <label className="field">
        <span className="field-label">
          <Icon name="bank" size={22} />
          <span lang="ur" dir="rtl">نیا اکاؤنٹ نمبر (IBAN)</span>
          <span>New account number (IBAN), in your own name</span>
        </span>
        <span dir="ltr" className="ltr-island">
          <input
            className="input input-big input-digits"
            autoComplete="off"
            autoCapitalize="characters"
            maxLength={40}
            value={iban}
            onChange={(e) => setIban(e.target.value)}
            aria-describedby="iban-hint"
          />
        </span>
        <span id="iban-hint" className="field-hint">
          <span lang="ur" dir="rtl">ہم بینک سے اکاؤنٹ کا نام چیک کریں گے۔ تبدیلی اڑتالیس گھنٹے بعد اور آپ کے پن سے ہوگی۔</span>
          <span>We check the name on the account with the bank. Nothing changes for 48 hours, and only with your PIN.</span>
        </span>
      </label>
      <div className="row" aria-label="Demo accounts (mock)">
        {DEMO_IBANS.map((d) => (
          <button key={d.iban} type="button" className="btn btn-quiet btn-sm" onClick={() => setIban(d.iban)}>
            Demo: {d.label}
          </button>
        ))}
      </div>
      <ErrorNote message={error} />
      <button type="submit" className="btn btn-primary btn-big" disabled={busy || !IBAN_PATTERN.test(clean)}>
        <Icon name="shield" size={24} />
        <span lang="ur" dir="rtl">اکاؤنٹ چیک کریں</span>
        <span className="btn-en">{busy ? 'Checking…' : 'Check account and request change'}</span>
      </button>
    </form>
  )
}

interface PendingChangeProps {
  change: PayoutChange
  isHelper: boolean
  claimantName: string
  onChanged: () => void
}

function PendingChange({ change, isHelper, claimantName, onChanged }: PendingChangeProps) {
  const [pin, setPin] = useState('')
  const [askCancel, setAskCancel] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const status = STATUS_TEXT[change.status] ?? [change.status, change.status]
  const needsPin = !change.confirmed && (change.status === 'held' || change.status === 'flagged' || change.status === 'approved')

  async function act(path: string, body: unknown): Promise<void> {
    setBusy(true)
    setError(null)
    try {
      await post<PayoutChange>(path, body)
      setPin('')
      setAskCancel(false)
      onChanged()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="stack-lg" aria-labelledby="pending-title">
      <div className={`verdict tone-${change.status === 'flagged' ? 'attn' : 'info'}`} role="status">
        <Pictogram name="clock" tone={change.status === 'flagged' ? 'attn' : 'info'} size="lg" />
        <div className="stack">
          <Bilingual as="h2" id="pending-title" ur={status[0]} en={status[1]} />
          <Countdown until={change.hold_until} />
        </div>
      </div>

      <PayeeCard payee={change.payee_result} check={change.payee_check} last4={change.new_iban_last4} />

      {change.flags.length > 0 && (
        <ul className="reason-list" aria-label="Why it is held longer">
          {change.flags.map((f) => {
            const [ur, en] = flagText(f)
            return (
              <li key={f} className="reason-item">
                <Icon name="warning" size={22} />
                <span className="bi"><span className="bi-ur" lang="ur" dir="rtl">{ur}</span><span className="bi-en">{en}</span></span>
              </li>
            )
          })}
        </ul>
      )}
      {change.status === 'flagged' && (
        <p className="note note-attn">
          <Icon name="person" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">ایک افسر اس تبدیلی کو دیکھے گا۔ تب تک پنشن پرانے اکاؤنٹ میں ہی آئے گی۔</span>
            An officer will review this change. Until then the pension keeps going to the old account.
          </span>
        </p>
      )}

      <ErrorNote message={error} />
      {needsPin && !isHelper && (
        <form className="form" onSubmit={(e) => { e.preventDefault(); void act(`/api/v1/payout-changes/${change.id}/confirm`, { pin }) }}>
          <label className="field">
            <span className="field-label">
              <Icon name="lock" size={22} />
              <span lang="ur" dir="rtl">تصدیق کے لیے اپنا پن لکھیں</span>
              <span>Enter your own PIN to confirm</span>
            </span>
            <span dir="ltr" className="ltr-island">
              <input className="input input-big input-pin" type="password" inputMode="numeric" autoComplete="current-password"
                maxLength={8} value={pin} onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))} />
            </span>
          </label>
          <button type="submit" className="btn btn-primary btn-big" disabled={busy || pin.length < 4}>
            <Icon name="check" size={24} />
            <span lang="ur" dir="rtl">تصدیق کریں</span>
            <span className="btn-en">Confirm with my PIN</span>
          </button>
        </form>
      )}
      {needsPin && isHelper && (
        <p className="note note-info">
          <Icon name="lock" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">صرف {claimantName} اپنے فون پر تصدیق کر سکتی ہیں۔</span>
            Only {claimantName} can confirm this, on her own phone with her own PIN.
          </span>
        </p>
      )}

      {!askCancel ? (
        <button type="button" className="btn btn-danger-outline btn-big" onClick={() => setAskCancel(true)}>
          <Icon name="close" size={22} />
          <span lang="ur" dir="rtl">یہ تبدیلی روک دیں</span>
          <span className="btn-en">Cancel this change</span>
        </button>
      ) : (
        <div className="confirm" role="alertdialog" aria-labelledby="cancel-title">
          <p id="cancel-title">
            <span lang="ur" dir="rtl" className="note-ur">کیا آپ یہ تبدیلی روکنا چاہتی ہیں؟ پنشن پرانے اکاؤنٹ میں ہی آئے گی۔</span>
            Stop this change? The pension keeps going to the old account.
          </p>
          <div className="row">
            <button type="button" className="btn btn-secondary btn-big" onClick={() => setAskCancel(false)}>
              <span lang="ur" dir="rtl">نہیں</span>
              <span className="btn-en">Keep it</span>
            </button>
            <button type="button" className="btn btn-danger btn-big" disabled={busy} onClick={() => void act(`/api/v1/payout-changes/${change.id}/cancel`, {})}>
              <span lang="ur" dir="rtl">ہاں، روک دیں</span>
              <span className="btn-en">Yes, cancel</span>
            </button>
          </div>
        </div>
      )}
    </article>
  )
}

export function PayeeCard({ payee, check, last4 }: { payee: string; check: PayeeCheck | null; last4: string }) {
  const p = PAYEE[payee] ?? PAYEE.no_match
  return (
    <div className={`payee tone-${p.tone}`}>
      <Pictogram name={p.icon} tone={p.tone} />
      <div className="stack payee-body">
        <Bilingual ur={p.ur} en={p.en} />
        <dl className="facts">
          <dt>Account</dt><dd dir="ltr">…{last4}</dd>
          {check?.masked_title && <><dt>Name at bank</dt><dd dir="ltr" className="mono">{check.masked_title}</dd></>}
          {check?.account_type && <><dt>Type</dt><dd>{check.account_type === 'WALLET' ? 'Mobile wallet' : 'Bank account'}</dd></>}
          {check?.account_holding && <><dt>Holder</dt><dd>{check.account_holding === 'JOINT' ? 'Joint (two names)' : 'Single'}</dd></>}
        </dl>
        <p className="fine">Mock Raast-style title fetch. Our match / close match / no match check is simulated.</p>
      </div>
    </div>
  )
}

function remaining(until: string, now: number): { days: number; hours: number; minutes: number; done: boolean } {
  const ms = new Date(until).getTime() - now
  if (ms <= 0) return { days: 0, hours: 0, minutes: 0, done: true }
  const minutes = Math.floor(ms / 60000)
  return { days: Math.floor(minutes / 1440), hours: Math.floor((minutes % 1440) / 60), minutes: minutes % 60, done: false }
}

function Countdown({ until }: { until: string }) {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000)
    return () => window.clearInterval(id)
  }, [])
  const r = remaining(until, now)
  const when = new Date(until).toLocaleString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  if (r.done) return <p className="countdown">Hold has ended</p>
  return (
    <p className="countdown">
      <span lang="ur" dir="rtl">باقی وقت:</span>{' '}
      <strong dir="ltr">{r.days > 0 ? `${r.days}d ` : ''}{r.hours}h {r.minutes}m</strong>
      <span className="fine"> (until {when})</span>
    </p>
  )
}
