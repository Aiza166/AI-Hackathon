import { Suspense, lazy, useEffect, useState } from 'react'
import { api, errorText } from '../api/client'
import type { CitizenExplanation } from '../api/types'
import { ErrorNote, ListenButton, Loading, Local, Pictogram, humanize, toneFor } from '../components/ui'
import { DOC_ICONS, Icon } from '../lib/icons'
import { useLang } from '../lib/useLang'

const DocumentCapture = lazy(() => import('../components/DocumentCapture').then((m) => ({ default: m.DocumentCapture })))
const PHOTO_KINDS = ['death_certificate', 'claimant_cnic', 'frc', 'nikah_nama'] as const

// The citizen's view of a decision: icon + Urdu sentence + audio. Never generated text.

// `k` = key in the Sindhi/Punjabi packs (src/i18n); Listen always speaks the Urdu line.
const HEADLINE: Record<string, { icon: string; k: string; ur: string; en: string }> = {
  auto_approved: { icon: 'check', k: 'head.approved', ur: 'آپ کا دعویٰ منظور ہو گیا', en: 'Your claim is approved' },
  approved: { icon: 'check', k: 'head.approved', ur: 'آپ کا دعویٰ منظور ہو گیا', en: 'Your claim is approved' },
  proof_requested: { icon: 'document', k: 'head.proof_requested', ur: 'ایک اور کاغذ چاہیے', en: 'One more paper is needed' },
  in_review: { icon: 'person', k: 'head.in_review', ur: 'افسر آپ کا دعویٰ دیکھے گا', en: 'An officer will look at your claim' },
  rejected: { icon: 'warning', k: 'head.rejected', ur: 'افسر نے دعویٰ نامنظور کیا', en: 'The officer did not approve this claim' },
  withdrawn: { icon: 'close', k: 'head.withdrawn', ur: 'آپ نے یہ دعویٰ واپس لے لیا', en: 'You withdrew this claim' },
}
const FALLBACK = { icon: 'clock', k: 'head.saved', ur: 'آپ کا دعویٰ محفوظ ہے', en: 'Your claim is saved' }

interface CaseResultProps {
  caseId: string
  onBack: () => void
}

export function CaseResult({ caseId, onBack }: CaseResultProps) {
  const [data, setData] = useState<CitizenExplanation | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [addingPhotos, setAddingPhotos] = useState(false)
  const { text } = useLang()

  useEffect(() => {
    let active = true
    api<CitizenExplanation>(`/api/v1/cases/${caseId}/explanation`)
      .then((r) => active && setData(r.data))
      .catch((e: unknown) => active && setError(errorText(e)))
    return () => {
      active = false
    }
  }, [caseId])

  const backButton = (
    <button type="button" className="btn btn-secondary btn-big" onClick={onBack}>
      <Icon name="arrow-left" size={24} />
      <Local k="nav.back" ur="واپس" />
      <span className="btn-en">Back</span>
    </button>
  )

  if (error) return <section className="stack"><ErrorNote message={error} />{backButton}</section>
  if (!data) return <Loading label="Opening your claim" />

  if (addingPhotos) {
    return (
      <Suspense fallback={<Loading label="Opening the camera step" />}>
        <DocumentCapture caseId={caseId} kinds={[...PHOTO_KINDS]} onDone={() => setAddingPhotos(false)} />
      </Suspense>
    )
  }

  const head = HEADLINE[data.status] ?? FALLBACK
  const tone = toneFor(data.status)

  return (
    <section className="stack-lg">
      <header className={`verdict tone-${tone}`}>
        <span className="verdict-icon"><Icon name={head.icon} size={52} /></span>
        <h1 className="verdict-text">
          <Local k={head.k} ur={head.ur} className="verdict-ur" />
          <span className="verdict-en">{head.en}</span>
        </h1>
        <ListenButton audioKey={`status_${data.status}`} text={head.ur} />
        <p className="verdict-ref">Claim {data.case_reference}, {humanize(data.status)}</p>
      </header>

      {data.explanations.length > 0 && (
        <section className="stack" aria-labelledby="why-title">
          <h2 id="why-title" className="bi">
            <Local k="why" ur="کیوں؟" className="bi-ur" />
            <span className="bi-en">Why</span>
          </h2>
          {data.explanations.map((x) => {
            const reason = text(`reason.${x.reason_code}`, x.text_ur)
            return (
            <article key={x.reason_code} className="reason">
              <Pictogram name={x.icon} tone={tone === 'ok' ? 'ok' : 'info'} />
              <div className="reason-body">
                <p lang={reason.tag} dir="rtl" className="reason-ur">{reason.text}</p>
                <p className="reason-en">{x.text_en}</p>
              </div>
              <ListenButton audioKey={x.audio_key} text={x.text_ur} compact />
            </article>
            )
          })}
        </section>
      )}

      {data.missing_items.length > 0 && (
        <section className="stack" aria-labelledby="send-title">
          <h2 id="send-title" className="bi">
            <span className="bi-ur" lang="ur" dir="rtl">یہ کاغذ بھیجیں</span>
            <span className="bi-en">Please send</span>
          </h2>
          <ul className="doc-chips">
            {data.missing_items.map((m) => (
              <li key={m}><Icon name={DOC_ICONS[m] ?? 'document'} size={26} /> {m === 'claimant_dob' ? 'Your date of birth (as on your CNIC)' : humanize(m)}</li>
            ))}
          </ul>
        </section>
      )}

      {data.entitlement_end && (
        <p className="note note-info">
          <Icon name="calendar" size={22} />
          <span>Pension is paid until <strong>{data.entitlement_end}</strong> (rule v2: 10-year limit for children and other heirs).</span>
        </p>
      )}
      <button type="button" className="btn btn-secondary btn-big" onClick={() => setAddingPhotos(true)}>
        <Icon name="camera" size={24} />
        <span lang="ur" dir="rtl">کاغذات کی تصویر بھیجیں</span>
        <span className="btn-en">Send photos of papers</span>
      </button>
      {backButton}
    </section>
  )
}
