import { useEffect, useRef, useState } from 'react'
import type { CaseView, ClaimIn, DocumentKind } from '../api/types'
import { ErrorNote, ListenButton, Loading, Pictogram } from '../components/ui'
import { DOC_ICONS, Icon } from '../lib/icons'
import { clearDraft, loadDraft, saveDraft, submit as submitQueued, takeForFixing } from '../lib/outbox'

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
  { key: 'prompt_deceased', icon: 'person', ur: 'مرحوم کا پورا نام کیا تھا؟', en: 'What was his full name?' },
  { key: 'prompt_deceased_cnic', icon: 'id-card', ur: 'مرحوم کا شناختی کارڈ نمبر', en: 'His CNIC number (if you know it)' },
  { key: 'prompt_documents', icon: 'document', ur: 'آپ کے پاس کون سے کاغذات ہیں؟', en: 'Which papers do you have? Tap all that apply.' },
  { key: 'prompt_account', icon: 'bank', ur: 'پنشن کس بینک اکاؤنٹ میں آئے؟', en: 'Which bank account should the pension go to?' },
  { key: 'prompt_review', icon: 'check', ur: 'دعویٰ بھیجنے سے پہلے دیکھ لیں', en: 'Check everything before sending' },
]
// Demo prefill so judges can run the golden path quickly (all mock data).
const DEMO_DECEASED = { name: 'Muhammad Aslam', cnic: '9000000000011', iban: 'PK00MOCK0000000000000001' }

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
  const [deceasedName, setDeceasedName] = useState('')
  const [deceasedCnic, setDeceasedCnic] = useState('')
  const [documents, setDocuments] = useState<DocumentKind[]>([])
  const [iban, setIban] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
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
        setDeceasedName(data.deceasedName)
        setDeceasedCnic(data.deceasedCnic)
        setDocuments(data.documents)
        setIban(data.iban)
        setStep(start)
        setSavedOnPhone(true)
      }
      lastSaved.current = snapshot(start, data ?? { relation: 'widow', deceasedName: '', deceasedCnic: '', documents: [], iban: '' })
      setRestored(true)
    })
    return () => {
      active = false
    }
  }, [ownerId, claimant.cnic])

  useEffect(() => {
    if (!restored) return
    const data: ClaimDraft = { relation, deceasedName, deceasedCnic, documents, iban }
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
  }, [restored, ownerId, claimant.cnic, step, relation, deceasedName, deceasedCnic, documents, iban])

  async function cancel(): Promise<void> {
    // Leaving the claim on purpose: do not keep her details on a shared phone.
    await clearDraft(ownerId, claimant.cnic)
    onCancel()
  }

  const prompt = STEPS[step]
  const isLast = step === STEPS.length - 1
  const canNext = step !== 1 || deceasedName.trim().length >= 2
  const toggleDoc = (doc: DocumentKind) =>
    setDocuments((current) => (current.includes(doc) ? current.filter((d) => d !== doc) : [...current, doc]))

  async function submit(): Promise<void> {
    setBusy(true)
    setError(null)
    const claim: ClaimIn = {
      claimant_cnic: claimant.cnic,
      claimant_name: claimant.name,
      relation_claimed: relation,
      deceased_cnic: deceasedCnic.trim() || null,
      deceased_name: deceasedName.trim(),
      payout_iban: iban.trim().toUpperCase(),
      documents,
    }
    const data: ClaimDraft = { relation, deceasedName, deceasedCnic, documents, iban }
    try {
      const result = await submitQueued<CaseView>({
        owner: ownerId, subject: claimant.cnic, subjectName: claimant.name, path: '/api/v1/cases', body: claim, draft: { step, data },
      })
      if (result.kind === 'sent') {
        onDone(result.data) // the outbox removed the draft once the server confirmed the claim
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
  }

  const relationLabel = RELATIONS.find((r) => r.key === relation)

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
          <span lang="ur" dir="rtl" className="question-ur">{prompt.ur}</span>
          <span className="question-en">{prompt.en}</span>
        </h2>
        <ListenButton audioKey={prompt.key} text={prompt.ur} />
      </header>

      <div className="answer">
        {step === 0 && (
          <div className="choice-grid choice-3">
            {RELATIONS.map((r) => (
              <button key={r.key} type="button" className="choice" aria-pressed={relation === r.key} onClick={() => setRelation(r.key)}>
                <Icon name={r.icon} size={44} />
                <span lang="ur" dir="rtl" className="choice-ur">{r.ur}</span>
                <span className="choice-en">{r.en}</span>
                {relation === r.key && <span className="choice-tick"><Icon name="check" size={22} /></span>}
              </button>
            ))}
          </div>
        )}

        {step === 1 && (
          <div className="stack">
            <label className="field">
              <span className="field-label">Name of the deceased</span>
              <input className="input input-big" autoComplete="off" value={deceasedName} onChange={(e) => setDeceasedName(e.target.value)} />
            </label>
            <button type="button" className="btn btn-quiet btn-sm self-start" onClick={fillDemo}>Fill demo data (mock)</button>
          </div>
        )}

        {step === 2 && (
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

        {step === 3 && (
          <div className="choice-grid choice-2">
            {DOCS.map((d) => {
              const on = documents.includes(d.key)
              return (
                <button key={d.key} type="button" className="choice" aria-pressed={on} onClick={() => toggleDoc(d.key)}>
                  <Icon name={DOC_ICONS[d.key]} size={40} />
                  <span lang="ur" dir="rtl" className="choice-ur">{d.ur}</span>
                  <span className="choice-en">{d.en}</span>
                  {on && <span className="choice-tick"><Icon name="check" size={22} /></span>}
                </button>
              )
            })}
          </div>
        )}

        {step === 4 && (
          <label className="field">
            <span className="field-label">IBAN of an account in your own name</span>
            <input className="input input-big input-digits" autoComplete="off" autoCapitalize="characters" value={iban} onChange={(e) => setIban(e.target.value)} />
          </label>
        )}

        {step === 5 && (
          <dl className="review">
            <ReviewRow icon="family" label="Relation" value={relationLabel ? `${relationLabel.en} / ${relationLabel.ur}` : relation} onEdit={() => setStep(0)} />
            <ReviewRow icon="person" label="Deceased" value={deceasedName || '-'} onEdit={() => setStep(1)} />
            <ReviewRow icon="id-card" label="His CNIC" value={deceasedCnic || 'Not given'} onEdit={() => setStep(2)} />
            <ReviewRow icon="document" label="Papers" value={`${documents.length} of ${DOCS.length}`} onEdit={() => setStep(3)} />
            <ReviewRow icon="bank" label="Account" value={iban || 'Not given'} onEdit={() => setStep(4)} />
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
          <span lang="ur" dir="rtl">واپس</span>
          <span className="btn-en">Back</span>
        </button>
        {isLast ? (
          <button type="button" className="btn btn-primary btn-big" onClick={() => void submit()} disabled={busy}>
            <span lang="ur" dir="rtl">بھیجیں</span>
            <span className="btn-en">{busy ? 'Sending…' : 'Send claim'}</span>
            <Icon name="check" size={24} />
          </button>
        ) : (
          <button type="button" className="btn btn-primary btn-big" onClick={() => setStep(step + 1)} disabled={!canNext}>
            <span lang="ur" dir="rtl">آگے</span>
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
