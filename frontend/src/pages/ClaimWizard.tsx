import { useState } from 'react'
import { errorText, post } from '../api/client'
import type { CaseView, ClaimIn, DocumentKind } from '../api/types'
import { Icon, type IconName } from '../components/Icon'
import { DOC_ICONS } from '../lib/icons'
import { speak } from '../lib/speak'

// One question per screen, big icons, audio on every step (low-literacy first).
// TODO(Kissa, Phase 2): save each step to Dexie so a dropped connection loses nothing.

type Relation = ClaimIn['relation_claimed']

interface Claimant {
  cnic: string
  name: string
}

interface ClaimWizardProps {
  claimant: Claimant
  onDone: (created: CaseView) => void
  onCancel: () => void
}

const RELATIONS: { key: Relation; icon: IconName; ur: string; en: string }[] = [
  { key: 'widow', icon: 'woman', ur: 'بیوہ', en: 'Widow' },
  { key: 'son', icon: 'boy', ur: 'بیٹا', en: 'Son' },
  { key: 'daughter', icon: 'girl', ur: 'بیٹی', en: 'Daughter' },
]
const DOCS: { key: DocumentKind; ur: string; en: string }[] = [
  { key: 'death_certificate', ur: 'وفات کا سرٹیفکیٹ', en: 'Death certificate' },
  { key: 'claimant_cnic', ur: 'آپ کا شناختی کارڈ', en: 'Your CNIC' },
  { key: 'frc', ur: 'خاندانی سرٹیفکیٹ', en: 'Family certificate (FRC)' },
  { key: 'nikah_nama', ur: 'نکاح نامہ', en: 'Nikah nama' },
]
const STEP_PROMPTS = [
  { key: 'prompt_relation', ur: 'آپ مرحوم کی کون ہیں؟' },
  { key: 'prompt_deceased', ur: 'مرحوم کا نام اور شناختی کارڈ نمبر' },
  { key: 'prompt_documents', ur: 'آپ کے پاس کون سے کاغذات ہیں؟' },
  { key: 'prompt_account', ur: 'پنشن کس بینک اکاؤنٹ میں آئے؟' },
  { key: 'prompt_review', ur: 'دعویٰ بھیجنے سے پہلے دیکھ لیں' },
]
// Demo prefill so judges can run the golden path quickly (all mock data).
const DEMO_DECEASED = { name: 'Muhammad Aslam', cnic: '9000000000011', iban: 'PK00MOCK0000000000000001' }

export function ClaimWizard({ claimant, onDone, onCancel }: ClaimWizardProps) {
  const [step, setStep] = useState(0)
  const [relation, setRelation] = useState<Relation>('widow')
  const [deceasedName, setDeceasedName] = useState('')
  const [deceasedCnic, setDeceasedCnic] = useState('')
  const [documents, setDocuments] = useState<DocumentKind[]>([])
  const [iban, setIban] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const prompt = STEP_PROMPTS[step]
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
    try {
      const result = await post<CaseView>('/api/v1/cases', claim)
      onDone(result.data)
    } catch (e) {
      setError(errorText(e))
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

  return (
    <section className="stack" aria-labelledby="step-title">
      <p className="muted">Step {step + 1} / {STEP_PROMPTS.length} · for {claimant.name}</p>
      <div className="row">
        <h2 id="step-title" lang="ur" className="urdu">{prompt.ur}</h2>
        <button type="button" className="audio" aria-label="Listen" onClick={() => void speak(prompt.key, prompt.ur)}><Icon name="speaker" size={32} /></button>
      </div>

      {step === 0 && (
        <div className="role-grid">
          {RELATIONS.map((r) => (
            <button key={r.key} type="button" className={`role-card ${relation === r.key ? 'selected' : ''}`} aria-pressed={relation === r.key} onClick={() => setRelation(r.key)}>
              <Icon name={r.icon} size={56} />
              <span lang="ur">{r.ur}</span>
              <span className="muted">{r.en}</span>
            </button>
          ))}
        </div>
      )}

      {step === 1 && (
        <div className="stack">
          <label>Name of the deceased <input value={deceasedName} onChange={(e) => setDeceasedName(e.target.value)} /></label>
          <label>CNIC of the deceased (13 digits, if known) <input inputMode="numeric" maxLength={13} value={deceasedCnic} onChange={(e) => setDeceasedCnic(e.target.value.replace(/\D/g, ''))} /></label>
          <button type="button" className="link" onClick={fillDemo}>Fill demo data (mock)</button>
        </div>
      )}

      {step === 2 && (
        <div className="role-grid">
          {DOCS.map((d) => (
            <button key={d.key} type="button" className={`role-card ${documents.includes(d.key) ? 'selected' : ''}`} aria-pressed={documents.includes(d.key)} onClick={() => toggleDoc(d.key)}>
              <Icon name={DOC_ICONS[d.key]} size={56} />
              <span lang="ur">{d.ur}</span>
              <span className="muted">{d.en}</span>
            </button>
          ))}
        </div>
      )}

      {step === 3 && (
        <label>Bank account (IBAN, in your own name) <input value={iban} onChange={(e) => setIban(e.target.value)} /></label>
      )}

      {step === 4 && (
        <dl className="review">
          <dt>Relation</dt><dd>{relation}</dd>
          <dt>Deceased</dt><dd>{deceasedName || '-'} {deceasedCnic && `(${deceasedCnic})`}</dd>
          <dt>Documents</dt><dd>{documents.length} of {DOCS.length}</dd>
          <dt>Account</dt><dd>{iban || '-'}</dd>
        </dl>
      )}

      {error && <p className="error" role="alert">{error}</p>}
      <div className="row">
        <button type="button" onClick={step === 0 ? onCancel : () => setStep(step - 1)}><Icon name="arrow-left" size={24} /> Back</button>
        {step < STEP_PROMPTS.length - 1 ? (
          <button type="button" className="primary" onClick={() => setStep(step + 1)} disabled={step === 1 && deceasedName.trim().length < 2}>Next <Icon name="arrow-right" size={24} /></button>
        ) : (
          <button type="button" className="primary" onClick={() => void submit()} disabled={busy}>Send claim <Icon name="check" size={24} /></button>
        )}
      </div>
    </section>
  )
}
