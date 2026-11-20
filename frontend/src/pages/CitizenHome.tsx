import { useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { CaseView, Family, Me, SessionUser } from '../api/types'
import { CaseResult } from './CaseResult'
import { ClaimWizard } from './ClaimWizard'

// Home for citizens and helpers. Helpers first pick which family they are acting for.

type View = { kind: 'list' } | { kind: 'new' } | { kind: 'case'; id: string }

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

  const claimant = isHelper
    ? actingFor && { cnic: actingFor.cnic, name: actingFor.name }
    : me?.person && { cnic: me.person.cnic, name: me.person.name }

  if (view.kind === 'case') return <CaseResult caseId={view.id} onBack={() => setView({ kind: 'list' })} />
  if (view.kind === 'new' && claimant) {
    return <ClaimWizard claimant={claimant} onCancel={() => setView({ kind: 'list' })} onDone={(c) => setView({ kind: 'case', id: c.id })} />
  }

  return (
    <section className="stack">
      {error && <p className="error" role="alert">{error}</p>}
      {isHelper && (
        <div className="stack">
          <h2>Acting for <span lang="ur">کس کے لیے</span></h2>
          <select
            aria-label="Choose family"
            value={actingFor?.id ?? ''}
            onChange={(e) => setActingFor(families.find((f) => f.id === e.target.value) ?? null)}
          >
            <option value="">Choose a family ({families.length})</option>
            {families.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
          </select>
          {actingFor && <p className="acting-for">Now acting for: <strong>{actingFor.name}</strong></p>}
        </div>
      )}
      <button type="button" className="primary huge" disabled={!claimant} onClick={() => setView({ kind: 'new' })}>
        {'➕'} New pension claim <span lang="ur">نیا دعویٰ</span>
      </button>
      <h2>My claims <span lang="ur">میرے دعوے</span></h2>
      {cases.length === 0 && <p className="muted">No claims yet.</p>}
      <ul className="case-list">
        {cases.map((c) => (
          <li key={c.id}>
            <button type="button" onClick={() => setView({ kind: 'case', id: c.id })}>
              <strong>{c.reference}</strong> · {c.status.replace('_', ' ')}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}
