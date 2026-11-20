import { useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { CitizenExplanation } from '../api/types'
import { ICONS } from '../lib/icons'
import { speak } from '../lib/speak'

// The citizen's view of a decision: icon + Urdu sentence + audio. Never generated text.

const STATUS_COLOUR: Record<string, string> = {
  auto_approved: 'ok', approved: 'ok', proof_requested: 'warn', in_review: 'info', rejected: 'bad',
}

interface CaseResultProps {
  caseId: string
  onBack: () => void
}

export function CaseResult({ caseId, onBack }: CaseResultProps) {
  const [data, setData] = useState<CitizenExplanation | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    api<CitizenExplanation>(`/api/v1/cases/${caseId}/explanation`)
      .then((r) => active && setData(r.data))
      .catch((e: unknown) => active && setError(errorText(e)))
    return () => {
      active = false
    }
  }, [caseId])

  if (error) return <p className="error" role="alert">{error}</p>
  if (!data) return <p>Loading...</p>

  return (
    <section className="stack">
      <p className={`status ${STATUS_COLOUR[data.status] ?? 'info'}`}>Claim {data.case_reference}: {data.status.replace('_', ' ')}</p>
      {data.explanations.map((x) => (
        <article key={x.reason_code} className="explanation">
          <span className="icon big" aria-hidden="true">{ICONS[x.icon] ?? 'ℹ'}</span>
          <p lang="ur" className="urdu big">{x.text_ur}</p>
          <p className="muted">{x.text_en}</p>
          <button type="button" className="audio" aria-label="Listen" onClick={() => void speak(x.audio_key, x.text_ur)}>{'\u{1F50A}'} Listen</button>
        </article>
      ))}
      {data.missing_items.length > 0 && (
        <p>Please send: {data.missing_items.map((m) => m.replace(/_/g, ' ')).join(', ')}</p>
      )}
      {data.entitlement_end && <p>Paid until {data.entitlement_end} (rule v2: 10-year cap)</p>}
      <button type="button" onClick={onBack}>{'⬅'} Back</button>
    </section>
  )
}
