import { Suspense, lazy, useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { CaseRow, CaseStub, CaseView, Family, Me, SessionUser } from '../api/types'
import { isCaseStub } from '../api/types'
import { OutboxStrip } from '../components/OutboxStrip'
import { loadMe, saveMe } from '../lib/meCache'
import { takeForFixing, type OutboxRow } from '../lib/outbox'
import { hasPendingShare } from '../lib/share'
import { useOutbox } from '../lib/useOutbox'
import { LanguagePicker } from '../components/LanguagePicker'
import { Badge, Bilingual, ErrorNote, ListenButton, Loading, Pictogram, humanize, toneFor } from '../components/ui'
import { Icon } from '../lib/icons'
import { CaseResult } from './CaseResult'
import { ClaimWizard } from './ClaimWizard'
import { MyData } from './MyData'

// New screens load on demand so the first screen stays small on a cheap phone.
const ScamShield = lazy(() => import('./ScamShield').then((m) => ({ default: m.ScamShield })))
const SafeSwitch = lazy(() => import('./SafeSwitch').then((m) => ({ default: m.SafeSwitch })))

// Home for citizens and helpers. Helpers first pick which family they are acting for.

type View = { kind: 'list' } | { kind: 'new' } | { kind: 'case'; id: string } | { kind: 'data' } | { kind: 'scam' } | { kind: 'payout' }

const STATUS_UR: Record<string, string> = {
  auto_approved: 'منظور',
  approved: 'منظور',
  proof_requested: 'مزید کاغذ چاہیے',
  in_review: 'افسر دیکھ رہا ہے',
  rejected: 'نامنظور',
  withdrawn: 'واپس لیا گیا',
}
// Older backends omit consent_active: fall back to "CNIC was shared".
function hasConsent(f: Family): boolean {
  return (f.consent_active ?? true) && Boolean(f.cnic)
}

const HOME_UR = 'نیا دعویٰ شروع کرنے کے لیے بڑا بٹن دبائیں۔ اپنے دعوے نیچے دیکھیں۔'

interface CitizenHomeProps {
  user: SessionUser
  onSignInAgain: () => void // session ended: sign in again without deleting saved claims
}

export function CitizenHome({ user, onSignInAgain }: CitizenHomeProps) {
  // Last good profile from this tab: after a reload with no signal she can still open her saved claim.
  const [me, setMe] = useState<Me | null>(() => (user.role === 'citizen' ? loadMe(user.id) : null))
  const [families, setFamilies] = useState<Family[]>([])
  const [actingFor, setActingFor] = useState<Family | null>(null)
  const [cases, setCases] = useState<CaseView[]>([])
  const [stubs, setStubs] = useState<CaseStub[]>([])
  const [view, setView] = useState<View>({ kind: 'list' })
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)
  const isHelper = user.role === 'helper'
  // Helper Mode: only the selected family's saved claims are shown and sent (null = none chosen).
  const outboxSubject = isHelper ? (actingFor?.cnic ?? null) : undefined
  const outbox = useOutbox(user.id, outboxSubject, () => setRefreshKey((k) => k + 1))

  // Something was shared to Sahara from WhatsApp / SMS: open Scam Shield, which reads it.
  useEffect(() => {
    let active = true
    void hasPendingShare().then((pending) => { if (active && pending) setView({ kind: 'scam' }) })
    return () => { active = false }
  }, [])

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const meResult = await api<Me>('/api/v1/me')
        const caseResult = await api<CaseRow[]>('/api/v1/cases')
        const familyResult = isHelper ? await api<Family[]>('/api/v1/helper/families') : null
        if (!active) return
        setError(null) // a successful reload (e.g. after reconnect) clears an old "No connection" note
        setMe(meResult.data)
        if (!isHelper) saveMe(user.id, meResult.data)
        setCases(caseResult.data.filter((c): c is CaseView => !isCaseStub(c)))
        setStubs(caseResult.data.filter(isCaseStub))
        if (familyResult) setFamilies(familyResult.data)
      } catch (e) {
        if (active) setError(errorText(e))
      }
    }
    void load()
    return () => {
      active = false
    }
    // Reload when the view changes, after a sync sends something, and when signal returns.
  }, [isHelper, user.id, view, refreshKey, outbox.online])

  const helperClaimant = actingFor && hasConsent(actingFor) && actingFor.cnic ? { cnic: actingFor.cnic, name: actingFor.name } : null
  const citizenClaimant = me?.person ? { cnic: me.person.cnic, name: me.person.name } : null
  const claimant = isHelper ? helperClaimant : citizenClaimant
  const back = () => setView({ kind: 'list' })
  // SafeSwitch: the claimant's own claims, or (helper) only the selected family's claims, with consent.
  const payoutCases = isHelper
    ? (actingFor && hasConsent(actingFor) ? cases.filter((c) => c.claimant_person_id === actingFor.id) : [])
    : cases

  // A refused claim is already back in the draft: drop the refused copy and open the wizard.
  async function openFix(row: OutboxRow): Promise<void> {
    if (isHelper) {
      const family = families.find((f) => f.cnic === row.subject)
      if (!family) return
      setActingFor(family)
      if (!hasConsent(family)) return // the lock note explains what to do first
    }
    await takeForFixing(row.id)
    setView({ kind: 'new' })
  }

  if (view.kind === 'case') return <CaseResult caseId={view.id} onBack={back} />
  if (view.kind === 'data') return <MyData onBack={back} />
  if (view.kind === 'scam') {
    return <Suspense fallback={<Loading />}><ScamShield onBack={back} /></Suspense>
  }
  if (view.kind === 'payout' && payoutCases.length > 0) {
    return (
      <Suspense fallback={<Loading />}>
        {isHelper && actingFor && <ActingForBanner family={actingFor} />}
        <SafeSwitch cases={payoutCases} isHelper={isHelper} claimantName={claimant?.name ?? ''} onBack={back} />
      </Suspense>
    )
  }
  if (view.kind === 'new' && claimant) {
    return (
      <>
        {isHelper && actingFor && <ActingForBanner family={actingFor} />}
        <ClaimWizard
          ownerId={user.id}
          claimant={claimant}
          onCancel={back}
          onQueued={back}
          onDone={(c) => setView({ kind: 'case', id: c.id })}
        />
      </>
    )
  }

  const greetingName = me?.person?.name ?? user.name
  return (
    <section className="stack-lg">
      <div className="hello">
        <Bilingual as="h1" k={isHelper ? 'home.chooseFamily' : 'home.greeting'} ur={isHelper ? 'خاندان منتخب کریں' : 'السلام علیکم'} en={isHelper ? `Helper mode, ${user.name}` : `Welcome, ${greetingName}`} />
        <ListenButton audioKey="prompt_home" text={HOME_UR} />
      </div>
      <ErrorNote message={error} />
      <OutboxStrip state={outbox} showWho={isHelper} onSignInAgain={onSignInAgain} onOpenFix={(row) => void openFix(row)} />

      {isHelper && (
        <FamilyPicker families={families} selected={actingFor} onSelect={setActingFor} />
      )}
      {isHelper && actingFor && <ActingForBanner family={actingFor} onClear={() => setActingFor(null)} />}

      <button type="button" className="action-main" disabled={!claimant} onClick={() => setView({ kind: 'new' })}>
        <span className="action-main-icon"><Icon name="plus" size={36} /></span>
        <Bilingual k="home.newClaim" ur="نیا پنشن دعویٰ" en="Start a new pension claim" />
      </button>
      {!outbox.online && claimant && (
        <p className="note note-attn" role="status">
          <Icon name="cloud-off" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">سگنل نہیں ہے۔ آپ اپنا محفوظ دعویٰ جاری رکھ سکتی ہیں، سگنل آنے پر یہ بھیج دیا جائے گا۔</span>
            No signal. You can continue your saved claim; it will be sent when signal returns.
          </span>
        </p>
      )}
      {isHelper && actingFor && !hasConsent(actingFor) && (
        <p className="note note-attn">
          <Icon name="lock" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">اس خاندان نے اجازت نہیں دی۔</span>
            {actingFor.name} has not given you consent. Ask her to share access from her own phone first.
          </span>
        </p>
      )}

      <div className="tiles">
        <button type="button" className="tile" onClick={() => setView({ kind: 'scam' })}>
          <Pictogram name="warning" tone="risk" />
          <Bilingual k="home.scam" ur="کیا یہ پیغام دھوکہ ہے؟" en="Is this message a scam?" />
        </button>
        <button type="button" className="tile" disabled={payoutCases.length === 0} onClick={() => setView({ kind: 'payout' })}>
          <Pictogram name="bank" tone="info" />
          <Bilingual k="home.payout" ur="پنشن کا اکاؤنٹ بدلیں" en={payoutCases.length === 0 ? 'Change payout account (needs a claim)' : 'Change payout account'} />
        </button>
      </div>

      {!isHelper && (
        <button type="button" className="action-row" onClick={() => setView({ kind: 'data' })}>
          <Pictogram name="shield" tone="info" />
          <Bilingual k="home.myData" ur="میرا ڈیٹا اور اجازت" en="My data: who can see it, who saw it" />
          <Icon name="arrow-right" size={24} className="action-row-arrow" />
        </button>
      )}

      <section className="stack" aria-labelledby="claims-title">
        <Bilingual as="h2" id="claims-title" k={isHelper ? 'home.claims' : 'home.myClaims'} ur={isHelper ? 'دعوے' : 'میرے دعوے'} en={isHelper ? 'Claims filed from this phone' : 'My claims'} />
        {cases.length === 0 && stubs.length === 0 && <p className="empty">No claims yet. Start one with the big button above.</p>}
        <ul className="claim-list">
          {cases.map((c) => (
            <li key={c.id}>
              <button type="button" className="claim-item" onClick={() => setView({ kind: 'case', id: c.id })}>
                <Pictogram name={toneFor(c.status) === 'ok' ? 'check' : 'document'} tone={toneFor(c.status)} size="sm" />
                <span className="claim-ref">{c.reference}</span>
                <span className="claim-status">
                  {STATUS_UR[c.status] && <span lang="ur" dir="rtl">{STATUS_UR[c.status]}</span>}
                  <Badge tone={toneFor(c.status)}>{humanize(c.status)}</Badge>
                </span>
              </button>
            </li>
          ))}
          {isHelper && stubs.map((s) => (
            <li key={s.reference}>
              <div className="claim-item" aria-disabled="true">
                <span className="claim-ref">{s.reference}</span>
                <span className="claim-status">
                  <span lang="ur" dir="rtl">اجازت واپس لے لی گئی</span>{' '}
                  <Badge tone="quiet">Consent withdrawn</Badge>
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <LanguagePicker />
    </section>
  )
}

function ActingForBanner({ family, onClear }: { family: Family; onClear?: () => void }) {
  return (
    <div className={hasConsent(family) ? 'acting' : 'acting acting-locked'} role="status">
      <Icon name={hasConsent(family) ? 'helper' : 'lock'} size={26} />
      <span className="acting-text">
        <span lang="ur" dir="rtl">اب آپ ان کے لیے کام کر رہی ہیں:</span>
        <span>Now acting for: <strong>{family.name}</strong></span>
      </span>
      {onClear && (
        <button type="button" className="btn btn-ghost btn-sm" onClick={onClear}>Change</button>
      )}
    </div>
  )
}

interface FamilyPickerProps {
  families: Family[]
  selected: Family | null
  onSelect: (family: Family) => void
}

function FamilyPicker({ families, selected, onSelect }: FamilyPickerProps) {
  const [query, setQuery] = useState('')
  const q = query.trim().toLowerCase()
  const shown = q ? families.filter((f) => f.name.toLowerCase().includes(q)) : families
  const shared = families.filter(hasConsent).length

  return (
    <section className="families" aria-labelledby="families-title">
      <div className="families-head">
        <h2 id="families-title" className="h-plain">Families ({families.length})</h2>
        <span className="muted">{shared} shared access with you</span>
      </div>
      <label className="search">
        <Icon name="search" size={20} />
        <span className="sr-only">Search families by name</span>
        <input className="input" placeholder="Search by name" value={query} onChange={(e) => setQuery(e.target.value)} />
      </label>
      <ul className="family-list">
        {shown.map((f) => (
          <li key={f.id}>
            <button
              type="button"
              className={selected?.id === f.id ? 'family is-selected' : 'family'}
              aria-pressed={selected?.id === f.id}
              onClick={() => onSelect(f)}
            >
              <Icon name={hasConsent(f) ? 'unlock' : 'lock'} size={22} className={hasConsent(f) ? 'family-open' : 'family-lock'} />
              <span className="family-name">{f.name}</span>
              <span className="family-meta">{hasConsent(f) ? f.cnic : 'No consent'}</span>
            </button>
          </li>
        ))}
        {shown.length === 0 && <li className="empty">No family matches “{query}”.</li>}
      </ul>
    </section>
  )
}
