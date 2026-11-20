import { useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { CaseView, Family, Me, SessionUser } from '../api/types'
import { Badge, Bilingual, ErrorNote, ListenButton, Pictogram, humanize, toneFor } from '../components/ui'
import { Icon } from '../lib/icons'
import { CaseResult } from './CaseResult'
import { ClaimWizard } from './ClaimWizard'
import { MyData } from './MyData'

// Home for citizens and helpers. Helpers first pick which family they are acting for.

type View = { kind: 'list' } | { kind: 'new' } | { kind: 'case'; id: string } | { kind: 'data' }

const STATUS_UR: Record<string, string> = {
  auto_approved: 'منظور',
  approved: 'منظور',
  proof_requested: 'مزید کاغذ چاہیے',
  in_review: 'افسر دیکھ رہا ہے',
  rejected: 'نامنظور',
}
// Older backends omit consent_active: fall back to "CNIC was shared".
function hasConsent(f: Family): boolean {
  return (f.consent_active ?? true) && Boolean(f.cnic)
}

const HOME_UR = 'نیا دعویٰ شروع کرنے کے لیے بڑا بٹن دبائیں۔ اپنے دعوے نیچے دیکھیں۔'

interface CitizenHomeProps {
  user: SessionUser
}

export function CitizenHome({ user }: CitizenHomeProps) {
  const [me, setMe] = useState<Me | null>(null)
  const [families, setFamilies] = useState<Family[]>([])
  const [actingFor, setActingFor] = useState<Family | null>(null)
  const [cases, setCases] = useState<CaseView[]>([])
  const [view, setView] = useState<View>({ kind: 'list' })
  const [error, setError] = useState<string | null>(null)
  const isHelper = user.role === 'helper'

  useEffect(() => {
    let active = true
    const load = async () => {
      try {
        const meResult = await api<Me>('/api/v1/me')
        const caseResult = await api<CaseView[]>('/api/v1/cases')
        const familyResult = isHelper ? await api<Family[]>('/api/v1/helper/families') : null
        if (!active) return
        setMe(meResult.data)
        setCases(caseResult.data)
        if (familyResult) setFamilies(familyResult.data)
      } catch (e) {
        if (active) setError(errorText(e))
      }
    }
    void load()
    return () => {
      active = false
    }
  }, [isHelper, view])

  const helperClaimant = actingFor && hasConsent(actingFor) && actingFor.cnic ? { cnic: actingFor.cnic, name: actingFor.name } : null
  const citizenClaimant = me?.person ? { cnic: me.person.cnic, name: me.person.name } : null
  const claimant = isHelper ? helperClaimant : citizenClaimant
  const back = () => setView({ kind: 'list' })

  if (view.kind === 'case') return <CaseResult caseId={view.id} onBack={back} />
  if (view.kind === 'data') return <MyData onBack={back} />
  if (view.kind === 'new' && claimant) {
    return (
      <>
        {isHelper && actingFor && <ActingForBanner family={actingFor} />}
        <ClaimWizard claimant={claimant} onCancel={back} onDone={(c) => setView({ kind: 'case', id: c.id })} />
      </>
    )
  }

  const greetingName = me?.person?.name ?? user.name
  return (
    <section className="stack-lg">
      <div className="hello">
        <Bilingual as="h1" ur={isHelper ? 'خاندان منتخب کریں' : 'السلام علیکم'} en={isHelper ? `Helper mode, ${user.name}` : `Welcome, ${greetingName}`} />
        <ListenButton audioKey="prompt_home" text={HOME_UR} />
      </div>
      <ErrorNote message={error} />

      {isHelper && (
        <FamilyPicker families={families} selected={actingFor} onSelect={setActingFor} />
      )}
      {isHelper && actingFor && <ActingForBanner family={actingFor} onClear={() => setActingFor(null)} />}

      <button type="button" className="action-main" disabled={!claimant} onClick={() => setView({ kind: 'new' })}>
        <span className="action-main-icon"><Icon name="plus" size={36} /></span>
        <Bilingual ur="نیا پنشن دعویٰ" en="Start a new pension claim" />
      </button>
      {isHelper && actingFor && !hasConsent(actingFor) && (
        <p className="note note-attn">
          <Icon name="lock" size={20} />
          <span>
            <span lang="ur" dir="rtl" className="note-ur">اس خاندان نے اجازت نہیں دی۔</span>
            {actingFor.name} has not given you consent. Ask her to share access from her own phone first.
          </span>
        </p>
      )}

      {!isHelper && (
        <button type="button" className="action-row" onClick={() => setView({ kind: 'data' })}>
          <Pictogram name="shield" tone="info" />
          <Bilingual ur="میرا ڈیٹا اور اجازت" en="My data: who can see it, who saw it" />
          <Icon name="arrow-right" size={24} className="action-row-arrow" />
        </button>
      )}

      <section className="stack" aria-labelledby="claims-title">
        <Bilingual as="h2" id="claims-title" ur={isHelper ? 'دعوے' : 'میرے دعوے'} en={isHelper ? 'Claims filed from this phone' : 'My claims'} />
        {cases.length === 0 && <p className="empty">No claims yet. Start one with the big button above.</p>}
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
        </ul>
      </section>
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
