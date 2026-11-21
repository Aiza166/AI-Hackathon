import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { CaseView, ClaimIn, DocumentKind } from '../api/types'
import { ErrorNote, ListenButton, Loading, Local, Pictogram } from '../components/ui'
import { DOC_ICONS, Icon } from '../lib/icons'
import { clearDraft, loadDraft, saveDraft, submit as submitQueued, takeForFixing } from '../lib/outbox'

// Photos of the papers, right after the claim is sent (loaded on demand to keep the shell small).
const DocumentCapture = lazy(() => import('../components/DocumentCapture').then((m) => ({ default: m.DocumentCapture })))

// One question per screen, big icons, audio on every step (low-literacy first).
// Every step is saved on the phone (lib/outbox.ts), so a reload or a dropped signal loses nothing.

type Relation = ClaimIn['relation_claimed']

interface Claimant {
  cnic: string
  name: string
}

interface ClaimWizardProps {
  ownerId: string
  claimant: Claimant
  onDone: (created: CaseView) => void
  onQueued: () => void
  onCancel: () => void
}

interface ClaimDraft {
  relation: Relation
  dob: string // YYYY-MM-DD from <input type="date">, '' = not given
  deceasedName: string
  deceasedCnic: string
  documents: DocumentKind[]
  iban: string
}

const RELATIONS: { key: Relation; icon: string; ur: string; en: string }[] = [
  { key: 'widow', icon: 'widow', ur: 'بیوہ', en: 'Widow' },
  { key: 'son', icon: 'son', ur: 'بیٹا', en: 'Son' },
  { key: 'daughter', icon: 'daughter', ur: 'بیٹی', en: 'Daughter' },
]
const DOCS: { key: DocumentKind; ur: string; en: string }[] = [
  { key: 'death_certificate', ur: 'وفات کا سرٹیفکیٹ', en: 'Death certificate' },
  { key: 'claimant_cnic', ur: 'آپ کا شناختی کارڈ', en: 'Your CNIC' },
  { key: 'frc', ur: 'خاندانی سرٹیفکیٹ', en: 'Family certificate (FRC)' },
  { key: 'nikah_nama', ur: 'نکاح نامہ', en: 'Nikah nama' },
]
const STEPS = [
  { key: 'prompt_relation', icon: 'family', ur: 'آپ مرحوم کی کون ہیں؟', en: 'How were you related to him?' },
  { key: 'prompt_dob', icon: 'calendar', ur: 'آپ کی تاریخ پیدائش کیا ہے؟', en: 'What is your date of birth?' },
  { key: 'prompt_deceased', icon: 'person', ur: 'مرحوم کا پورا نام کیا تھا؟', en: 'What was his full name?' },
  { key: 'prompt_deceased_cnic', icon: 'id-card', ur: 'مرحوم کا شناختی کارڈ نمبر', en: 'His CNIC number (if you know it)' },
  { key: 'prompt_documents', icon: 'document', ur: 'آپ کے پاس کون سے کاغذات ہیں؟', en: 'Which papers do you have? Tap all that apply.' },
  { key: 'prompt_account', icon: 'bank', ur: 'پنشن کس بینک اکاؤنٹ میں آئے؟', en: 'Which bank account should the pension go to?' },
  { key: 'prompt_review', icon: 'check', ur: 'دعویٰ بھیجنے سے پہلے دیکھ لیں', en: 'Check everything before sending' },
] as const
// Demo prefill so judges can run the golden path quickly (all mock data).
const DEMO_DECEASED = { name: 'Muhammad Aslam', cnic: '9000000000011', iban: 'PK00MOCK0000000000000001' }
// Mock DOB of the demo widow (Zainab Bibi), so her demo claim can auto-approve.
const DEMO_CLAIMANT = { cnic: '9000000000022', dob: '1962-06-01' }
const DOB_PATTERN = /^\d{4}-\d{2}-\d{2}$/
type StepKey = (typeof STEPS)[number]['key']
const stepIndex = (key: StepKey): number => STEPS.findIndex((s) => s.key === key)

function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

// A stored draft comes from the phone's database: check its shape before using it.
function asClaimDraft(value: unknown): ClaimDraft | null {
  if (typeof value !== 'object' || value === null) return null
  const v = value as Record<string, unknown>
  const relation = RELATIONS.find((r) => r.key === v.relation)?.key
  const docs = Array.isArray(v.documents) ? v.documents : null
  if (!relation || !docs || !docs.every((d) => DOCS.some((k) => k.key === d))) return null
  if (typeof v.deceasedName !== 'string' || typeof v.deceasedCnic !== 'string' || typeof v.iban !== 'string') return null
  return {
    relation,
    dob: typeof v.dob === 'string' && DOB_PATTERN.test(v.dob) ? v.dob : '', // older drafts have no DOB
    deceasedName: v.deceasedName.slice(0, 120),
    deceasedCnic: v.deceasedCnic.replace(/\D/g, '').slice(0, 13),
    documents: docs as DocumentKind[],
    iban: v.iban.slice(0, 34),
  }
}

function clampStep(value: number): number {
  return Number.isInteger(value) ? Math.min(Math.max(value, 0), STEPS.length - 1) : 0
}

const snapshot = (step: number, data: ClaimDraft) => JSON.stringify({ step, data })

export function ClaimWizard({ ownerId, claimant, onDone, onQueued, onCancel }: ClaimWizardProps) {
  const [step, setStep] = useState(0)
  const [relation, setRelation] = useState<Relation>('widow')
  const [dob, setDob] = useState('')
  const [deceasedName, setDeceasedName] = useState('')
  const [deceasedCnic, setDeceasedCnic] = useState('')
  const [documents, setDocuments] = useState<DocumentKind[]>([])
  const [iban, setIban] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [created, setCreated] = useState<CaseView | null>(null) // sent: now photograph the papers
  // Draft handling: restore once (inputs stay hidden until then), then save after every real change.
  const [restored, setRestored] = useState(false)
  const [savedOnPhone, setSavedOnPhone] = useState(false)
  const lastSaved = useRef<string | null>(null)

  useEffect(() => {
    let active = true
    void loadDraft(ownerId, claimant.cnic).then((stored) => {
      if (!active) return
      const data = stored ? asClaimDraft(stored.data) : null
      const start = data && stored ? clampStep(stored.step) : 0
      if (data) {
        setRelation(data.relation)
        setDob(data.dob)
        setDeceasedName(data.deceasedName)
        setDeceasedCnic(data.deceasedCnic)
        setDocuments(data.documents)
        setIban(data.iban)
        setStep(start)
        setSavedOnPhone(true)
      }
      lastSaved.current = snapshot(start, data ?? { relation: 'widow', dob: '', deceasedName: '', deceasedCnic: '', documents: [], iban: '' })
      setRestored(true)
    })
    return () => {
      active = false
    }
  }, [ownerId, claimant.cnic])

  useEffect(() => {
    if (!restored) return
    const data: ClaimDraft = { relation, dob, deceasedName, deceasedCnic, documents, iban }
    const current = snapshot(step, data)
    if (current === lastSaved.current) return // nothing changed: do not write an empty draft
    lastSaved.current = current
    let active = true
    void saveDraft(ownerId, claimant.cnic, { step, data }).then((ok) => {
      if (active && ok) setSavedOnPhone(true)
    })
    return () => {
      active = false
    }
  }, [restored, ownerId, claimant.cnic, step, relation, dob, deceasedName, deceasedCnic, documents, iban])

  async function cancel(): Promise<void> {
    // Leaving the claim on purpose: do not keep her details on a shared phone.
    await clearDraft(ownerId, claimant.cnic)
    onCancel()
  }

  const prompt = STEPS[step]
  const isLast = step === STEPS.length - 1
  const canNext = prompt.key !== 'prompt_deceased' || deceasedName.trim().length >= 2
  const toggleDoc = (doc: DocumentKind) =>
    setDocuments((current) => (current.includes(doc) ? current.filter((d) => d !== doc) : [...current, doc]))

  async function submit(): Promise<void> {
    setBusy(true)
    setError(null)
    const claim: ClaimIn = {
      claimant_cnic: claimant.cnic,
      claimant_name: claimant.name,
      claimant_dob: DOB_PATTERN.test(dob) ? dob : null, // blank: the system asks her to confirm it, never rejects
      relation_claimed: relation,
      deceased_cnic: deceasedCnic.trim() || null,
      deceased_name: deceasedName.trim(),
      payout_iban: iban.trim().toUpperCase(),
      documents,
    }
    const data: ClaimDraft = { relation, dob, deceasedName, deceasedCnic, documents, iban }
    try {
      const result = await submitQueued<CaseView>({
        owner: ownerId, subject: claimant.cnic, subjectName: claimant.name, path: '/api/v1/cases', body: claim, draft: { step, data },
      })
      if (result.kind === 'sent') {
        setCreated(result.data) // the outbox removed the draft once the server confirmed the claim
      } else if (result.kind === 'queued') {
        // Saved in the outbox; the draft stays until the claim is confirmed sent.
        onQueued()
      } else if (result.kind === 'duplicate') {
        setError(result.message)
      } else {
        // Refused while she is still here: show why and let her fix it in place.
        if (result.rowId) await takeForFixing(result.rowId)
        setError(result.message)
      }
    } finally {
      setBusy(false)
    }
  }

  function fillDemo(): void {
    setDeceasedName(DEMO_DECEASED.name)
    setDeceasedCnic(DEMO_DECEASED.cnic)
    setIban(DEMO_DECEASED.iban)
    setDocuments(DOCS.map((d) => d.key))
    // Never the DOB: a DOB she left blank stays blank (judges test "leave the DOB blank").
  }

  const relationLabel = RELATIONS.find((r) => r.key === relation)

  if (created) {
    return (
      <Suspense fallback={<Loading label="Opening the camera step" />}>
        <DocumentCapture caseId={created.id} kinds={documents.length ? documents : DOCS.map((d) => d.key)} onDone={() => onDone(created)} />
      </Suspense>
    )
  }
  if (!restored) return <Loading label="Opening your saved claim" />

  return (
    <section className="wizard" aria-labelledby="step-title">
      <div className="wizard-top">
        <ol className="steps" aria-label={`Step ${step + 1} of ${STEPS.length}`}>
          {STEPS.map((s, i) => (
            <li key={s.key} className={i < step ? 'done' : i === step ? 'current' : ''} aria-current={i === step ? 'step' : undefined}>
              <span className="sr-only">Step {i + 1}</span>
            </li>
          ))}
        </ol>
        <span className="wizard-count">{step + 1} / {STEPS.length}</span>
      </div>

      <header className="question">
        <Pictogram name={prompt.icon} size="lg" />
        <h2 id="step-title" className="question-text">
          <Local k={prompt.key} ur={prompt.ur} className="question-ur" />
          <span className="question-en">{prompt.en}</span>
        </h2>
        <ListenButton audioKey={prompt.key} text={prompt.ur} />
      </header>

      <div className="answer">
        {prompt.key === 'prompt_relation' && (
          <div className="choice-grid choice-3">
            {RELATIONS.map((r) => (
              <button key={r.key} type="button" className="choice" aria-pressed={relation === r.key} onClick={() => setRelation(r.key)}>
                <Icon name={r.icon} size={44} />
                <Local k={`rel.${r.key}`} ur={r.ur} className="choice-ur" />
                <span className="choice-en">{r.en}</span>
                {relation === r.key && <span className="choice-tick"><Icon name="check" size={22} /></span>}
              </button>
            ))}
          </div>
        )}

        {prompt.key === 'prompt_dob' && (
          <div className="stack">
            <label className="field">
              <span className="field-label">
                <Icon name="id-card" size={22} />
                <span lang="ur" dir="rtl">تاریخ پیدائش (شناختی کارڈ پر لکھی ہے)</span>
                <span>Date of birth</span>
              </span>
              <span dir="ltr" className="ltr-island">
                <input
                  className="input input-big input-digits"
                  type="date"
                  lang="en"
                  min="1900-01-01"
                  max={todayIso()}
                  value={dob}
                  onChange={(e) => setDob(e.target.value)}
                  aria-describedby="dob-hint"
                />
              </span>
              <span id="dob-hint" className="field-hint">
                <span lang="ur" dir="rtl">یہ آپ کے شناختی کارڈ پر چھپی ہے۔ معلوم نہ ہو تو خالی چھوڑ دیں، ہم بعد میں پوچھ لیں گے۔</span>
                <span>Printed on your CNIC. If you are not sure, leave it empty: we will ask you to confirm it later.</span>
              </span>
            </label>
            {claimant.cnic === DEMO_CLAIMANT.cnic && (
              <button type="button" className="btn btn-quiet btn-sm self-start" onClick={() => setDob(DEMO_CLAIMANT.dob)}>Fill demo DOB (mock)</button>
            )}
          </div>
        )}

        {prompt.key === 'prompt_deceased' && (
          <div className="stack">
            <label className="field">
              <span className="field-label">Name of the deceased</span>
              <input className="input input-big" autoComplete="off" value={deceasedName} onChange={(e) => setDeceasedName(e.target.value)} />
            </label>
            <button type="button" className="btn btn-quiet btn-sm self-start" onClick={fillDemo}>Fill demo data (mock)</button>
          </div>
        )}

        {prompt.key === 'prompt_deceased_cnic' && (
          <label className="field">
            <span className="field-label">13 digits, no dashes. Leave empty if you do not know it.</span>
            <input
              className="input input-big input-digits"
              inputMode="numeric"
              maxLength={13}
              value={deceasedCnic}
              onChange={(e) => setDeceasedCnic(e.target.value.replace(/\D/g, ''))}
            />
          </label>
        )}

        {prompt.key === 'prompt_documents' && (
          <div className="choice-grid choice-2">
            {DOCS.map((d) => {
              const on = documents.includes(d.key)
              return (
                <button key={d.key} type="button" className="choice" aria-pressed={on} onClick={() => toggleDoc(d.key)}>
                  <Icon name={DOC_ICONS[d.key]} size={40} />
                  <Local k={`doc.${d.key}`} ur={d.ur} className="choice-ur" />
                  <span className="choice-en">{d.en}</span>
                  {on && <span className="choice-tick"><Icon name="check" size={22} /></span>}
                </button>
              )
            })}
          </div>
        )}

        {prompt.key === 'prompt_account' && (
          <label className="field">
            <span className="field-label">IBAN of an account in your own name</span>
            <input className="input input-big input-digits" autoComplete="off" autoCapitalize="characters" value={iban} onChange={(e) => setIban(e.target.value)} />
          </label>
        )}

        {prompt.key === 'prompt_review' && (
          <dl className="review">
            <ReviewRow icon="family" label="Relation" value={relationLabel ? `${relationLabel.en} / ${relationLabel.ur}` : relation} onEdit={() => setStep(stepIndex('prompt_relation'))} />
            <ReviewRow icon="calendar" label="Your date of birth" value={dob || 'Not given (we will ask)'} onEdit={() => setStep(stepIndex('prompt_dob'))} />
            <ReviewRow icon="person" label="Deceased" value={deceasedName || '-'} onEdit={() => setStep(stepIndex('prompt_deceased'))} />
            <ReviewRow icon="id-card" label="His CNIC" value={deceasedCnic || 'Not given'} onEdit={() => setStep(stepIndex('prompt_deceased_cnic'))} />
            <ReviewRow icon="document" label="Papers" value={`${documents.length} of ${DOCS.length}`} onEdit={() => setStep(stepIndex('prompt_documents'))} />
            <ReviewRow icon="bank" label="Account" value={iban || 'Not given'} onEdit={() => setStep(stepIndex('prompt_account'))} />
            <ReviewRow icon="helper" label="Claim for" value={claimant.name} />
          </dl>
        )}
      </div>

      <ErrorNote message={error} />
      {savedOnPhone && (
        <p className="fine saved-on-phone" role="status">
          <Icon name="check" size={16} />
          <span lang="ur" dir="rtl">اس فون پر محفوظ</span>
          <span>Saved on this phone</span>
        </p>
      )}
      <nav className="wizard-nav" aria-label="Claim steps">
        <button type="button" className="btn btn-secondary btn-big" onClick={step === 0 ? () => void cancel() : () => setStep(step - 1)}>
          <Icon name="arrow-left" size={24} />
          <Local k="nav.back" ur="واپس" />
          <span className="btn-en">Back</span>
        </button>
        {isLast ? (
          <button type="button" className="btn btn-primary btn-big" onClick={() => void submit()} disabled={busy}>
            <Local k="nav.send" ur="بھیجیں" />
            <span className="btn-en">{busy ? 'Sending…' : 'Send claim'}</span>
            <Icon name="check" size={24} />
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-big" onClick={() => setStep(step + 1)} disabled={!canNext}>
            <Local k="nav.next" ur="آگے" />
            <span className="btn-en">Next</span>
            <Icon name="arrow-right" size={24} />
          </button>
        )}
      </nav>
    </section>
  )
}

interface ReviewRowProps {
  icon: string
  label: string
  value: string
  onEdit?: () => void
}

function ReviewRow({ icon, label, value, onEdit }: ReviewRowProps) {
  return (
    <div className="review-row">
      <Icon name={icon} size={24} />
      <dt>{label}</dt>
      <dd>{value}</dd>
      {onEdit && (
        <button type="button" className="btn btn-quiet btn-sm" onClick={onEdit} aria-label={`Change ${label}`}>
          <Icon name="pen" size={18} />
          <span>Change</span>
        </button>
      )}
    </div>
  )
}
