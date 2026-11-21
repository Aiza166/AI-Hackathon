import { useState } from 'react'
import { getToken, post } from '../api/client'
import { DOC_ICONS, Icon } from '../lib/icons'
import { preparePhoto, uploadWithProgress, type PhotoHint, type PreparedPhoto } from '../lib/photo'
import { ListenButton } from './ui'

// Photograph each paper, check it on the phone, upload with progress, then show what was
// read so she can confirm it. Reasons are fixed server text (Urdu + English), never "fake".

export type DocKind = 'claimant_cnic' | 'deceased_cnic' | 'death_certificate' | 'frc' | 'nikah_nama'

const BASE: string = import.meta.env.VITE_API_BASE ?? ''

const DOC_LABELS: Record<DocKind, { ur: string; en: string; icon: string }> = {
  claimant_cnic: { ur: 'آپ کا شناختی کارڈ', en: 'Your CNIC', icon: 'id-card' },
  deceased_cnic: { ur: 'مرحوم کا شناختی کارڈ', en: 'His CNIC', icon: 'id-card' },
  death_certificate: { ur: 'وفات کا سرٹیفکیٹ', en: 'Death certificate', icon: 'document' },
  frc: { ur: 'خاندانی سرٹیفکیٹ', en: 'Family certificate (FRC)', icon: DOC_ICONS.frc },
  nikah_nama: { ur: 'نکاح نامہ', en: 'Nikah nama', icon: 'document' },
}

const HINTS: Record<Exclude<PhotoHint, 'ok'>, { ur: string; en: string }> = {
  blurry: { ur: 'تصویر دھندلی لگتی ہے۔ فون ساکت رکھ کر دوبارہ لیں۔', en: 'The photo looks blurry. Hold the phone still and take it again.' },
  dark: { ur: 'تصویر بہت اندھیری ہے۔ روشنی میں دوبارہ لیں۔', en: 'The photo is too dark. Take it again in good light.' },
  small: { ur: 'تصویر بہت چھوٹی ہے۔ کاغذ کے قریب سے لیں۔', en: 'The photo is too small. Move closer to the paper.' },
}

interface FieldRead {
  value: string
  confidence: number
  needs_confirmation: boolean
}

interface Reason {
  code: string
  text_en: string
  text_ur: string
}

interface DocResult {
  id?: string
  status?: string
  kind: DocKind
  risk_level?: string
  fields?: Record<string, FieldRead>
  reasons: Reason[]
  case_status?: string
}

type Slot =
  | { state: 'empty' }
  | { state: 'checked'; photo: PreparedPhoto }
  | { state: 'uploading'; photo: PreparedPhoto; progress: number }
  | { state: 'done'; photo: PreparedPhoto; result: DocResult }
  | { state: 'error'; photo: PreparedPhoto; message: string }

interface DocumentCaptureProps {
  caseId: string
  kinds: DocKind[]
  onDone: () => void
}

export function DocumentCapture({ caseId, kinds, onDone }: DocumentCaptureProps) {
  const [slots, setSlots] = useState<Partial<Record<DocKind, Slot>>>({})
  const setSlot = (kind: DocKind, slot: Slot) => setSlots((current) => ({ ...current, [kind]: slot }))

  async function pick(kind: DocKind, file: File | undefined): Promise<void> {
    if (!file) return
    try {
      const photo = await preparePhoto(file)
      setSlot(kind, { state: 'checked', photo })
      if (photo.hint === 'ok') await upload(kind, photo)
    } catch {
      setSlot(kind, { state: 'empty' })
    }
  }

  async function upload(kind: DocKind, photo: PreparedPhoto): Promise<void> {
    setSlot(kind, { state: 'uploading', photo, progress: 0 })
    const form = new FormData()
    form.append('kind', kind)
    form.append('file', photo.blob, `${kind}.jpg`)
    const result = await uploadWithProgress<DocResult>(`${BASE}/api/v1/cases/${caseId}/documents`, form, getToken(),
      (progress) => setSlot(kind, { state: 'uploading', photo, progress }))
    if (result.ok && result.data) setSlot(kind, { state: 'done', photo, result: result.data })
    else setSlot(kind, { state: 'error', photo, message: result.message })
  }

  return (
    <section className="stack-lg doc-capture" aria-labelledby="docs-title">
      <header className="question">
        <h2 id="docs-title" className="question-text">
          <span lang="ur" dir="rtl" className="question-ur">اپنے کاغذات کی تصویر لیں</span>
          <span className="question-en">Take a photo of each paper</span>
        </h2>
        <ListenButton audioKey="prompt_document_photos" text="اپنے کاغذات کی تصویر لیں۔ کاغذ کو روشنی میں سیدھا رکھیں۔" />
      </header>
      <p className="fine">Lay the paper flat in good light. Photos are made smaller on this phone before sending.</p>
      {kinds.map((kind) => (
        <DocSlot key={kind} caseId={caseId} kind={kind} slot={slots[kind] ?? { state: 'empty' }}
          onPick={(f) => void pick(kind, f)} onSend={(p) => void upload(kind, p)} onRetake={() => setSlot(kind, { state: 'empty' })}
          onResult={(r) => { const s = slots[kind]; if (s && 'photo' in s) setSlot(kind, { state: 'done', photo: s.photo, result: r }) }} />
      ))}
      <button type="button" className="btn btn-primary btn-big" onClick={onDone}>
        <span lang="ur" dir="rtl">آگے</span>
        <span className="btn-en">Continue</span>
        <Icon name="arrow-right" size={24} />
      </button>
      <p className="fine">You can also add photos later from your claim page.</p>
    </section>
  )
}

interface DocSlotProps {
  caseId: string
  kind: DocKind
  slot: Slot
  onPick: (file: File | undefined) => void
  onSend: (photo: PreparedPhoto) => void
  onRetake: () => void
  onResult: (result: DocResult) => void
}

function DocSlot({ caseId, kind, slot, onPick, onSend, onRetake, onResult }: DocSlotProps) {
  const label = DOC_LABELS[kind]
  const inputId = `doc-${kind}`
  return (
    <article className="doc-slot">
      <div className="doc-slot-head">
        <Icon name={label.icon} size={32} />
        <span className="doc-slot-title">
          <span lang="ur" dir="rtl" className="choice-ur">{label.ur}</span>
          <span className="choice-en">{label.en}</span>
        </span>
        {slot.state === 'done' && slot.result.status !== 'retake' && <span className="doc-tick"><Icon name="check" size={20} /></span>}
      </div>
      {'photo' in slot && <img className="doc-preview" src={slot.photo.previewUrl} alt={`Photo of ${label.en}`} />}

      {(slot.state === 'empty' || (slot.state === 'done' && slot.result.status === 'retake')) && (
        <label htmlFor={inputId} className="btn btn-secondary btn-big doc-take">
          <Icon name="camera" size={24} />
          <span lang="ur" dir="rtl">تصویر لیں</span>
          <span className="btn-en">Take photo</span>
          <input id={inputId} className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" capture="environment"
            onChange={(e) => { onPick(e.target.files?.[0]); e.target.value = '' }} />
        </label>
      )}

      {slot.state === 'checked' && slot.photo.hint !== 'ok' && (
        <div className="note note-attn" role="alert">
          <Icon name="warning" size={20} />
          <span><span className="note-ur" lang="ur" dir="rtl">{HINTS[slot.photo.hint].ur}</span>{HINTS[slot.photo.hint].en}</span>
          <div className="row">
            <button type="button" className="btn btn-primary btn-sm" onClick={onRetake}>Retake</button>
            <button type="button" className="btn btn-quiet btn-sm" onClick={() => onSend(slot.photo)}>Send anyway</button>
          </div>
        </div>
      )}

      {slot.state === 'uploading' && (
        <div className="doc-progress" role="status" aria-live="polite">
          <progress max={1} value={slot.progress} aria-label="Sending photo" />
          <span>{slot.progress < 1 ? `Sending ${Math.round(slot.progress * 100)}%` : 'Reading the paper…'}</span>
        </div>
      )}

      {slot.state === 'error' && (
        <div className="note note-risk" role="alert">
          <Icon name="warning" size={20} /><span>{slot.message}</span>
          <button type="button" className="btn btn-secondary btn-sm" onClick={() => onSend(slot.photo)}>Try again</button>
        </div>
      )}

      {slot.state === 'done' && <DocOutcome caseId={caseId} result={slot.result} onResult={onResult} />}
    </article>
  )
}

function DocOutcome({ caseId, result, onResult }: { caseId: string; result: DocResult; onResult: (r: DocResult) => void }) {
  const fields = Object.entries(result.fields ?? {})
  const unsure = fields.filter(([, f]) => f.needs_confirmation)
  const [edits, setEdits] = useState<Record<string, string>>(() => Object.fromEntries(unsure.map(([k, f]) => [k, f.value])))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function confirm(): Promise<void> {
    if (!result.id) return
    setBusy(true)
    setError(null)
    try {
      onResult((await post<DocResult>(`/api/v1/cases/${caseId}/documents/${result.id}/confirm`, { values: edits })).data)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="stack">
      {result.reasons.map((r) => (
        <p key={r.code} className={r.code === 'PHOTO_RETAKE' ? 'note note-attn' : 'note note-info'}>
          <Icon name="document" size={20} />
          <span><span className="note-ur" lang="ur" dir="rtl">{r.text_ur}</span>{r.text_en}</span>
        </p>
      ))}
      {fields.length > 0 && (
        <dl className="doc-fields">
          {fields.map(([key, f]) => (
            <div key={key} className="doc-field">
              <dt>{key.replace(/_/g, ' ')}</dt>
              {f.needs_confirmation ? (
                <dd><input className="input" aria-label={`Check ${key.replace(/_/g, ' ')}`} value={edits[key] ?? ''}
                  onChange={(e) => setEdits((cur) => ({ ...cur, [key]: e.target.value }))} /></dd>
              ) : <dd>{f.value}</dd>}
            </div>
          ))}
        </dl>
      )}
      {unsure.length > 0 && (
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => void confirm()}>
          <Icon name="check" size={20} />
          <span lang="ur" dir="rtl">درست ہے</span>
          <span className="btn-en">{busy ? 'Saving…' : 'These are correct'}</span>
        </button>
      )}
      {error && <p className="note note-risk" role="alert">{error}</p>}
    </div>
  )
}
